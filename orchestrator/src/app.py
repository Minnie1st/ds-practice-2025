import sys
import os
import threading  # 用于多线程
import queue  # 用于线程间通信
import grpc
from flask import Flask, request
from flask_cors import CORS
import json
import uuid
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# This set of lines are needed to import the gRPC stubs.
# The path of the stubs is relative to the current file, or absolute inside the container.
# Change these lines only if strictly needed.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)
import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_verification_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)
import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc


def greet(name='you'):
    # Establish a connection with the fraud-detection gRPC service.
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        # Create a stub object.
        stub = fraud_detection_grpc.HelloServiceStub(channel)
        # Call the service through the stub object.
        response = stub.SayHello(fraud_detection.HelloRequest(name=name))
    return response.greeting

# Import Flask.
# Flask is a web framework for Python.
# It allows you to build a web application quickly.
# For more information, see https://flask.palletsprojects.com/en/latest/
# Create a simple Flask app.
app = Flask(__name__)
# Enable CORS for the app.
CORS(app, resources={r'/*': {'origins': '*'}})  # 是为了允许前端跨域访问后端（比如前端跑在 localhost:3000，后端跑在 localhost:5000）

# 定义 worker 函数：调用各微服务
def call_fraud_detection(order_data, queue):
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionStub(channel)
        response = stub.CheckFraud(fraud_detection.OrderRequest(
            user_name=order_data['user_name'],
            contact=order_data.get('contact', ''),
            card_number=order_data['card_number'],
            expirationDate=order_data.get('expirationDate', ''),
            cvv=order_data.get('cvv', ''),
            items=[fraud_detection.Item(name=item['name'], quantity=item['quantity']) for item in order_data['items']],
            user_comment=order_data.get('user_comment', ''),
            billing_address=fraud_detection.BillingAddress(
                street=order_data['billing_address'].get('street', ''),
                city=order_data['billing_address'].get('city', ''),
                state=order_data['billing_address'].get('state', ''),
                zip=order_data['billing_address'].get('zip', ''),
                country=order_data['billing_address'].get('country', '')
            ) if order_data.get('billing_address') else None,
            device=fraud_detection.Device(
                type=order_data['device'].get('type', ''),
                model=order_data['device'].get('model', ''),
                os=order_data['device'].get('os', '')
            ) if order_data.get('device') else None,
            browser=fraud_detection.Browser(
                name=order_data['browser'].get('name', ''),
                version=order_data['browser'].get('version', '')
            ) if order_data.get('browser') else None,
            deviceLanguage=order_data.get('deviceLanguage', ''),
            screenResolution=order_data.get('screenResolution', ''),
            referrer=order_data.get('referrer', '')
        ))
        queue.put(('fraud', response.is_fraudulent))

def call_transaction_verification(order_data, queue):
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationStub(channel)
        response = stub.VerifyTransaction(transaction_verification.OrderRequest(
            user_name=order_data['user_name'],
            card_number=order_data['card_number'],
            cvv=order_data.get('cvv', ''),
            expirationDate=order_data.get('expirationDate', ''),
            items=[transaction_verification.Item(name=item['name'], quantity=item['quantity']) for item in order_data['items']]
        ))
        queue.put(('transaction', response.is_valid))

def call_suggestions(order_data, queue):
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsStub(channel)
        response = stub.GetSuggestions(suggestions.OrderRequest(
            user_name=order_data['user_name'],
            items=[suggestions.Item(name=item['name'], quantity=item['quantity']) for item in order_data['items']]
        ))
        queue.put(('suggestions', response.suggested_books))
# Define a GET endpoint.这是一个简单的 GET 端点，当你访问 http://localhost:5000/ 时，会调用 greet 函数，返回一个问候语。
# 它主要是用来测试 gRPC 是否能正常连接到欺诈检测服务。

@app.route('/', methods=['GET'])
def index():
    """
    Responds with 'Hello, [name]' when a GET request is made to '/' endpoint.
    """
    # Test the fraud-detection gRPC service.
    response = greet(name='orchestrator')
    # Return the response.
    return response

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Responds with a JSON object containing the order ID, status, and suggested books.
    """
    # Get request object data to json
    request_data = json.loads(request.data)
    logger.info("Received request data: %s", request_data)
    # Print request object data
    # print("Request Data:", request_data.get('items'))
    if 'user' not in request_data or 'creditCard' not in request_data or 'items' not in request_data:
        error_response = {
            'error': {
                'code': '400',
                'message': 'Missing required fields: user, creditCard, or items'
            }
        }
        return error_response, 400
    
    user_info = request_data['user']
    user_name = user_info.get('name', 'Unknown')
    credit_card = request_data['creditCard']
    card_number = credit_card.get('number', '')
    items = request_data['items']
    
    logger.info("User Name: %s, Credit Card: %s, CVV: %s, Expiration Date: %s, Items: %s", 
                user_name, card_number, credit_card.get('cvv', ''), credit_card.get('expirationDate', ''), items)
    
    # 生成一个随机订单 ID
    order_id = str(uuid.uuid4())  # uuid4 生成一个随机唯一 ID
    # 准备订单数据，转换为 gRPC 需要的格式
    order_data = {
        'user_name': user_info.get('name', 'Unknown'),
        'contact': user_info.get('contact', ''),
        'card_number': credit_card.get('number', ''),
        'expirationDate': credit_card.get('expirationDate', ''),
        'cvv': credit_card.get('cvv', ''),
        'user_comment': request_data.get('userComment', ''),
        'items': items,  # 保持为 [{'name': str, 'quantity': int}]，在 call_fraud_detection 中转换
        'billing_address': request_data.get('billingAddress', {}),
        'device': request_data.get('device', {}),
        'browser': request_data.get('browser', {}),
        'deviceLanguage': request_data.get('deviceLanguage', ''),
        'screenResolution': request_data.get('screenResolution', ''),
        'referrer': request_data.get('referrer', '')

    }
    
    # 创建结果队列
    result_queue = queue.Queue()

    # 创建并启动线程
    threads = [
        threading.Thread(target=call_fraud_detection, args=(order_data, result_queue)),
        threading.Thread(target=call_transaction_verification, args=(order_data, result_queue)),
        threading.Thread(target=call_suggestions, args=(order_data, result_queue))
    ]
    
    # 启动所有线程
    for thread in threads:
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    # 收集结果
    fraud_result = None
    transaction_result = None
    suggestions_result = None
    
    results = {}
    for _ in range(3):  # 等待 3 个结果
        service_type, result = result_queue.get()
        results[service_type] = result
    fraud_result = results['fraud']
    transaction_result = results['transaction']
    suggestions_result = results['suggestions']
    
    # 综合判断订单状态
    if fraud_result or not transaction_result:  # 如果有欺诈或交易无效
        status = 'Order Rejected'
        suggested_books = []  # 订单被拒绝时不返回推荐书籍
    else:
        status = 'Order Approved'
        suggested_books = [book for book in suggestions_result] if suggestions_result else []

    # Dummy response following the provided YAML specification for the bookstore
    order_status_response = {
        'orderId': order_id,
        'status': status,
        'suggestedBooks': [
            {
                'title': book.title,
                'author': book.author
            }
            for book in suggested_books
        ]
    }
    logger.info("Returning response: %s", order_status_response)
    return order_status_response

if __name__ == '__main__':
    # Run the app in debug mode to enable hot reloading.
    # This is useful for development.
    # The default port is 5000.
    app.run(host='0.0.0.0')