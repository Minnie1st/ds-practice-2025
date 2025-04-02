import sys
import os
import grpc
from concurrent import futures
import google.generativeai as genai
import json
from dotenv import load_dotenv
import re
import uuid
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 全局缓存
order_data_cache = {}  # 存订单数据
vector_clocks = {}     # 存向量时钟

load_dotenv()

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc


class SuggestionsServicer(suggestions_grpc.SuggestionsServicer):
    def CacheOrder(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)
        vc[2] += 1  # suggestions 是第2个位置（从0开始计数），加1

        order_data_cache[order_id] = {
            'user_name': request.user_name,
            'items': [{'name': item.name, 'quantity': item.quantity} for item in request.items]
        }
        vector_clocks[order_id] = [0, 0, 0]
        print(f"Suggestions: Cached OrderID {order_id}, Vector Clock {vector_clocks[order_id]}")
        return suggestions.OrderResponse(
            success=True,
            message="Order cached",
            vector_clock=vector_clocks[order_id]
        )
    
    def GetSuggestions(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)  # 从请求拿向量时钟
        vc[2] += 1  # suggestions 是第2个位置（从0开始），加1
        vector_clocks[order_id] = vc  # 更新全局向量时钟

        logger.info(f"Event GetSuggestions: Received GenerateSuggestions for OrderID {order_id}, Vector Clock {vc}")
        # 设置 API 密钥（从环境变量读取）
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY", ""))
        
        # 构建提示（Prompt），基于用户订单生成推荐
        prompt = f"User {request.user_name} purchased the following books (no genre specified):"
        for item in request.items:
            prompt += f"\n- {item.name} (Quantity: {item.quantity})"
        prompt += """
        First, infer the most likely genre for each book based on its name. Then, recommend 3 related books, including the title and author, in strict JSON format, 
        - The output must be a flat list of 3 books in the format: [['Book1', 'Author1'], ['Book2', 'Author2'], ['Book3', 'Author3']]
        - Example output:
        ```json
        [['The Hobbit', 'J.R.R. Tolkien'], ['Dune', 'Frank Herbert'], ['1984', 'George Orwell']]
        ```"""
        print(prompt)
        logger.info(f"Received items: {[(item.name, item.quantity) for item in request.items]}")
        
        try:
            #  Gemini 2.0 Flash 
            logger.info("Calling Gemini API for Suggestion")
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            logger.info(f"🔍 Gemini API Raw Response: {response.text}")
            
            
            #  response.text 可用（处理可能的 None 或异常）
            if not response.text or not response.text.strip():
                raise ValueError("Received empty response from Gemini API")
            
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response.text, re.DOTALL)
            if json_match:
                books_json = json_match.group(1).strip()  # 提取 JSON 内容
            else:
                # 如果没有找到代码块，尝试直接查找可能的 JSON 部分
                books_json = re.sub(r"[^$$  $$\{\},:\"'\w\s-]", "", response.text.strip())
                # 进一步清理，确保只保留 JSON 相关字符
                books_json = re.sub(r"\s+", " ", books_json).strip()

            # 进一步检查 books_json 是否是有效的 JSON
            try:
                books_list = json.loads(books_json)
            except json.JSONDecodeError as e:
                logger.info(f"Error decoding JSON: {e}")
                # 如果解析失败，使用默认书单
                books_list = []

            # 如果 books_list 为空，使用默认推荐
            if not books_list:
                logger.info("No valid book recommendations found, returning defaults.")
                books_list = [
                    ["Python Crash Course", "Eric Matthes"],
                    ["Introduction to Algorithms", "Thomas H. Cormen"]
                ]

            # 转换为 protobuf 格式的书籍列表
            suggested_books = [
                suggestions.Book( 
                    title=book[0],
                    author=book[1]
                )
                for i, book in enumerate (books_list)
            ]
            
            logger.info(f"Event f: OrderID {order_id}, Generated {len(suggested_books)} suggestions, Vector Clock {vc}")
            return suggestions.OrderResponse(
                success=True,
                message="Suggestions generated",
                suggested_books=suggested_books[:3],  # 最多3本
                vector_clock=vc
            )

        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            default_books = [
                suggestions.Book(title="Python Crash Course", author="Eric Matthes"),
                suggestions.Book(title="Introduction to Algorithms", author="Thomas H. Cormen")
            ]
            return suggestions.OrderResponse(
                success=False,
                message=f"Failed to generate suggestions: {str(e)}",
                suggested_books=default_books,
                vector_clock=vc
            )
    
    def ClearOrder(self, request, context):
        order_id = request.order_id
        final_vc = list(request.final_vector_clock)  # VCf
        local_vc = vector_clocks.get(order_id, [0, 0, 0])  # 本地 VC

        # 检查 VC <= VCf
        is_valid = all(local_vc[i] <= final_vc[i] for i in range(len(local_vc)))
        if is_valid:
            # 清理数据
            if order_id in order_data_cache:
                del order_data_cache[order_id]
            if order_id in vector_clocks:
                del vector_clocks[order_id]
            print(f"Suggestions: Cleared OrderID {order_id}, Local VC {local_vc}, Final VC {final_vc}")
            return suggestions.ClearResponse(
                success=True,
                message="Order data cleared"
            )
        else:
            print(f"Suggestions: Error for OrderID {order_id}, Local VC {local_vc} > Final VC {final_vc}")
            return suggestions.ClearResponse(
                success=False,
                message="Vector clock mismatch"
            )
        
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    suggestions_grpc.add_SuggestionsServicer_to_server(
        SuggestionsServicer(), server
    )
    server.add_insecure_port('[::]:50053')  # 监听端口 50053
    server.start()
    print("Suggestions service started on port 50053")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()