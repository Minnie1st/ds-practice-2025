import sys
import os
import grpc
from concurrent import futures
import openai
import os

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc


class SuggestionsServicer(suggestions_grpc.SuggestionsServicer):
    def GetSuggestions(self, request, context):
        # 设置 OpenAI API 密钥（从环境变量读取）
        openai.api_key = os.getenv("OPENAI_API_KEY", "REDACTED<==WFDPw7htq_vtrudgXQmA0SFCWiwgFt4wg3x5EEHJ5vLbovzwmYp0vjHCQt6Szfvl8jVP24SmzoT3BlbkFJfjPJBu2QVAcB0L5Xa5SY3awg8sdg1GyE9L2JYvOpMH19pfF6PopNGTsEFJuBaqd08yhjDFcUoA")
        
        # 构建提示（Prompt），基于用户订单生成推荐
        prompt = f"用户 {request.user_name} 购买了以下书籍："
        for item in request.items:
            prompt += f"\n- {item.name}（数量：{item.quantity}）"
        prompt += "\n请推荐3本相关书籍，包括书名和作者，用JSON格式返回，例如：[['书名1', '作者1'], ['书名2', '作者2'], ['书名3', '作者3']]"

        try:
            # 调用 ChatGPT API（使用 gpt-3.5-turbo 模型）
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )
            
            # 解析 ChatGPT 返回的 JSON 字符串
            books_json = response.choices[0].message['content'].strip()
            # 假设 ChatGPT 返回类似 "[['Python进阶', '王五'], ['算法入门', '李四'], ['数据科学', '张三']]"
            books_list = eval(books_json)  # 简单解析（注意安全，生产环境用 json.loads）

            # 转换为 protobuf 格式的书籍列表
            suggested_books = [
                suggestions.Book(
                    book_id=f"book_{i}",  # 简单生成 ID
                    title=book[0],
                    author=book[1]
                )
                for i, book in enumerate(books_list, 1)
            ]
            
            return suggestions.OrderResponse(suggested_books=suggested_books[:3])

        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            # 如果 API 调用失败，返回默认推荐
            default_books = [
                suggestions.Book(book_id="123", title="Python进阶", author="王五"),
                suggestions.Book(book_id="456", title="算法入门", author="李四")
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