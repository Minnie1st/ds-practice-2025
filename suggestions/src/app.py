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

load_dotenv()

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc


class SuggestionsServicer(suggestions_grpc.SuggestionsServicer):
    def GetSuggestions(self, request, context):
        # 设置 API 密钥（从环境变量读取）
        logger.info("Received Suggestion request from user: %s", request.user_name)
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
        
        try:
            # 使用 Gemini 2.0 Flash 模型生成内容
            logger.info("Calling Gemini API for fraud Suggestion")
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(prompt)
            logger.info(f"🔍 Gemini API Raw Response: {response.text}")  # 打印原始响应内容
            
            
            # 确保 response.text 可用（处理可能的 None 或异常）
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
            
            return suggestions.OrderResponse(suggested_books=suggested_books[:3])

        except Exception as e:
            logger.info(f"Error calling Gemini API: {e}")
            # 如果出现其他错误，返回默认推荐
            default_books = [
                suggestions.Book(title="Python Crash Course", author="Eric Matthes"),
                suggestions.Book(title="Introduction to Algorithms", author="Thomas H. Cormen")
            ]

            return suggestions.OrderResponse(suggested_books=default_books)
        
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