import sys
import os
import json
import uuid
import threading
import queue
import grpc
import logging
from flask import Flask, request
from flask_cors import CORS

# 调整模块搜索路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
# 分别指向 transaction_verification、fraud_detection 和 suggestions 的子目录
transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
# 添加到 sys.path
sys.path.insert(0, transaction_verification_grpc_path)
sys.path.insert(0, fraud_detection_grpc_path)
sys.path.insert(0, suggestions_grpc_path)
sys.path.insert(0, order_queue_grpc_path)

# 现在可以正确导入
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc
import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc
import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc
import order_queue_pb2 as order_queue
import order_queue_pb2_grpc as order_queue_grpc

# Import Flask.
# Flask is a web framework for Python.
# It allows you to build a web application quickly.
# For more information, see https://flask.palletsprojects.com/en/latest/
# Create a simple Flask app.
app = Flask(__name__)
# Enable CORS for the app.
CORS(app, resources={r'/*': {'origins': '*'}})  # 是为了允许前端跨域访问后端（比如前端跑在 localhost:3000，后端跑在 localhost:5000）

order_queue_channel = grpc.insecure_channel('order_queue:50054')
order_queue_stub = order_queue_grpc.OrderQueueStub(order_queue_channel)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 初始化 gRPC 通道和 stub
transaction_channel = grpc.insecure_channel('transaction_verification:50052')
fraud_channel = grpc.insecure_channel('fraud_detection:50051')
suggestions_channel = grpc.insecure_channel('suggestions:50053')

transaction_stub = transaction_verification_grpc.TransactionVerificationStub(transaction_channel)
fraud_stub = fraud_detection_grpc.FraudDetectionStub(fraud_channel)
suggestions_stub = suggestions_grpc.SuggestionsStub(suggestions_channel)

@app.route('/checkout', methods=['POST'])
def checkout():
    # 解析前端请求
    request_data = json.loads(request.data)
    if 'user' not in request_data or 'creditCard' not in request_data or 'items' not in request_data:
        logger.error("Missing required fields in request")
        return {'error': {'code': '400', 'message': 'Missing required fields'}}, 400
    
    user_info = request_data['user']
    user_name = user_info.get('name', 'Unknown')
    credit_card = request_data['creditCard']
    card_number = credit_card.get('number', '')
    items = request_data['items']
    contact = user_info.get('contact', '')
    billing_address = request_data.get('billingAddress', {})
    user_comment = request_data.get('user_comment', '')
    expirationDate = credit_card.get('expirationDate', '')
    shipping_method = request_data.get('shippingMethod', 'standard')
    
    # 生成 OrderID
    order_id = str(uuid.uuid4())
    order_data = {
        'order_id': order_id,
        'user_name': user_name,
        'contact': contact,
        'expirationDate': expirationDate,
        'card_number': card_number,
        'items': items,
        'user_comment': user_comment,
        'billing_address': billing_address
    }
    logger.info(f"Generated OrderID: {order_id}")
    logger.info(f"Extracted billing_address: {billing_address}")
    
    # 步骤 1：缓存订单数据到三个服务
    result_queue = queue.Queue()
    
    # 清理函数：调用 fraud_detection 的 ClearOrder
    def call_fraud_clear(order_id, final_vc, result_queue):
        with grpc.insecure_channel('fraud_detection:50051') as channel:
            stub = fraud_detection_grpc.FraudDetectionStub(channel)
            response = stub.ClearOrder(fraud_detection.ClearRequest(
                order_id=order_id,
                final_vector_clock=final_vc
            ))
            result_queue.put(('fraud_clear', response))

    # 清理函数：调用 transaction_verification 的 ClearOrder
    def call_transaction_clear(order_id, final_vc, result_queue): 
        with grpc.insecure_channel('transaction_verification:50052') as channel:
            stub = transaction_verification_grpc.TransactionVerificationStub(channel)
            response = stub.ClearOrder(transaction_verification.ClearRequest(
                order_id=order_id,
                final_vector_clock=final_vc
            ))
            result_queue.put(('transaction_clear', response))

    # 清理函数：调用 suggestions 的 ClearOrder
    def call_suggestions_clear(order_id, final_vc, result_queue):
        with grpc.insecure_channel('suggestions:50053') as channel:
            stub = suggestions_grpc.SuggestionsStub(channel)
            response = stub.ClearOrder(suggestions.ClearRequest(
                order_id=order_id,
                final_vector_clock=final_vc
            ))
            result_queue.put(('suggestions_clear', response))
    
    def check_clear_results(order_id, result_queue):
        clear_results = {}
        for _ in range(3):
            service, resp = result_queue.get()
            clear_results[service] = resp
        for service, resp in clear_results.items():
            if not resp.success:
                logger.warning(f"Warning: {service} failed to clear OrderID {order_id}: {resp.message}")
            else:
                logger.info(f"{service} successfully cleared OrderID {order_id}")
    
    def broadcast_clear(order_id, final_vc):
        result_queue = queue.Queue()
        clear_threads = [
            threading.Thread(target=call_fraud_clear, args=(order_id, final_vc, result_queue)),
            threading.Thread(target=call_transaction_clear, args=(order_id, final_vc, result_queue)),
            threading.Thread(target=call_suggestions_clear, args=(order_id, final_vc, result_queue))
        ]
        for t in clear_threads:
            t.start()
        threading.Thread(target=check_clear_results, args=(order_id, result_queue)).start()

    def cache_transaction():
        response = transaction_stub.CacheOrder(transaction_verification.OrderRequest(
            order_id=order_id,
            user_name=user_name,
            card_number=card_number,
            contact=contact,
            billing_address=transaction_verification.OrderRequest.BillingAddress(
            street=billing_address.get('street', ''),
            city=billing_address.get('city', ''),
            state=billing_address.get('state', ''),
            zip=billing_address.get('zip', ''),
            country=billing_address.get('country', '')
        ),
            cvv=credit_card.get('cvv', ''),  # 添加 cvv
            expirationDate=expirationDate,  # 添加 expirationDate
            items=[transaction_verification.Item(name=item['name'], quantity=item['quantity']) for item in items],
            vector_clock=[0, 0, 0]
        ))
        result_queue.put(('transaction_cache', response))

    
    def cache_fraud():
        response = fraud_stub.CacheOrder(fraud_detection.OrderRequest(
            order_id=order_id,
            user_name=user_name,
            card_number=card_number,
            expirationDate=order_data['expirationDate'],

            
            items=[fraud_detection.Item(name=item['name'], quantity=item['quantity']) for item in items],
            vector_clock=[0, 0, 0]
        ))
        result_queue.put(('fraud_cache', response))
    
    def cache_suggestions():
        response = suggestions_stub.CacheOrder(suggestions.OrderRequest(
            order_id=order_id,
            user_name=user_name,
            items=[suggestions.Item(name=item['name'], quantity=item['quantity']) for item in items],
            vector_clock=[0, 0, 0]
        ))
        result_queue.put(('suggestions_cache', response))
    
    threads = [
        threading.Thread(target=cache_transaction),
        threading.Thread(target=cache_fraud),
        threading.Thread(target=cache_suggestions)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 检查缓存结果
    for _ in range(3):
        service, response = result_queue.get()
        if not response.success:
            logger.error(f"Cache failed at {service}")
            final_vc = [0, 0, 0]  # 缓存失败时用初始向量时钟
            response = {'orderId': order_id, 'status': 'Order Rejected', 'suggestedBooks': []}
            broadcast_clear(order_id, final_vc)
            return response
        logger.info(f"Cache succeeded at {service}")
    
    # 步骤 2：事件 a 和 b 并行
    vc = [0, 0, 0]
    event_queue = queue.Queue()
    
    def event_a(): # 订单项目检查
        response = transaction_stub.VerifyItemsNotEmpty(transaction_verification.OrderRequest(
            order_id=order_id,
            vector_clock=vc
        ))
        event_queue.put(('a', response))
    
    def event_b(): # 用户数据检查
        response = transaction_stub.VerifyUserDataComplete(transaction_verification.OrderRequest(
            order_id=order_id,
            vector_clock=vc
        ))
        event_queue.put(('b', response))
    
    t_a = threading.Thread(target=event_a)
    t_b = threading.Thread(target=event_b)
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()
    
    # 获取 a 和 b 的结果
    results = {}
    for _ in range(2):
        event, response = event_queue.get()
        results[event] = response
        logger.info(f"Event {event} completed with Vector Clock {response.vector_clock}")
    
    if not results['a'].success:
        logger.error("Failed at event a: Items check failed")
        final_vc = results['a'].vector_clock
        response = {
            'orderId': order_id,
            'status': 'Order Rejected',
            'reason': "Looks like your order doesn't have any items. Please add some books to proceed!",
            'suggestedBooks': []

        }
        broadcast_clear(order_id, final_vc)
        return response

    if not results['b'].success:
        logger.error(f"Failed at event b: {results['b'].message}")
        reasons = results['b'].message.split("; ")
        friendly_reasons = []
        for reason in reasons:
            if "User name" in reason:
                friendly_reasons.append("your name")
            elif "Contact information" in reason:
                friendly_reasons.append("your contact information")
            elif "Order items" in reason:
                friendly_reasons.append("order items")
            elif "User comment" in reason:
                friendly_reasons.append("a comment")
            elif "Billing address" in reason:
                if "street" in reason:
                    friendly_reasons.append("your billing address street")
                elif "city" in reason:
                    friendly_reasons.append("your billing address city")
                elif "state" in reason:
                    friendly_reasons.append("your billing address state")
                elif "zip" in reason:
                    friendly_reasons.append("your billing address zip code")
                elif "country" in reason:
                    friendly_reasons.append("your billing address country")
                else:
                    friendly_reasons.append("your billing address")
        friendly_message = "We need " + ", ".join(friendly_reasons) + " to process your order. Please fill in the missing information and try again!"
        final_vc = results['b'].vector_clock
        response = {
            'orderId': order_id,
            'status': 'Order Rejected',
            'reason': friendly_message,
            'suggestedBooks': []
        }
        broadcast_clear(order_id, final_vc)
        return response
    
    # 步骤 3：事件 c（依赖 a）# 信用卡格式检查
    vc = results['a'].vector_clock
    result_c = transaction_stub.VerifyCreditCardFormat(transaction_verification.OrderRequest(
        order_id=order_id,
        vector_clock=vc
    ))
    logger.info(f"Event c completed with Vector Clock {result_c.vector_clock}")
    if not result_c.success:
        logger.error("Failed at event c: Credit card format check failed")
        final_vc = result_c.vector_clock
        response = {
            'orderId': order_id,
            'status': 'Order Rejected',
            'reason': "The credit card number seems invalid. Please check and try again!",
            'suggestedBooks': []  # 添加空数组
        }
        broadcast_clear(order_id, final_vc)
        return response
    
    # 步骤 4：事件 d（依赖 b）# 用户欺诈检查
    vc = results['b'].vector_clock
    result_d = fraud_stub.CheckUserFraud(fraud_detection.OrderRequest(
        order_id=order_id,
        vector_clock=vc
    ))
    logger.info(f"Event d completed with Vector Clock {result_d.vector_clock}")
    if not result_d.success:
        final_vc = result_d.vector_clock
        logger.error("Failed at event d: User fraud detected")
        response = {
            'orderId': order_id,
            'status': 'Order Rejected',
            'reason': "We detected a potential issue with your account. Please check and try again!",
            'suggestedBooks': []  # 添加空数组
        }
        broadcast_clear(order_id, final_vc)
        return response
    # 步骤 5：事件 e（依赖 c 和 d） # 信用卡欺诈检查
    vc = [max(result_c.vector_clock[i], result_d.vector_clock[i]) for i in range(3)]
    result_e = fraud_stub.CheckCardFraud(fraud_detection.OrderRequest(
        order_id=order_id,
        vector_clock=vc
    ))
    logger.info(f"Event e completed with Vector Clock {result_e.vector_clock}")
    if not result_e.success:
        logger.error("Failed at event e: Credit card fraud detected")
        final_vc = result_e.vector_clock
        response = {
            'orderId': order_id,
            'status': 'Order Rejected',
            'reason': "We detected a potential issue with your credit card. Please use a different card or contact support.",
            'suggestedBooks': []  # 添加空数组
        }
        broadcast_clear(order_id, final_vc)
        return response
    # 步骤 6：事件 f（依赖 e）# 获取推荐书籍
    vc = result_e.vector_clock
    result_f = suggestions_stub.GetSuggestions(suggestions.OrderRequest(
        order_id=order_id,
        user_name=user_name,
        items=[suggestions.Item(name=item['name'], quantity=item['quantity']) for item in order_data['items']],
        vector_clock=vc
    ))
    logger.info(f"Event f completed with Vector Clock {result_f.vector_clock}")

    
    # 步骤 7：返回结果 
    status = 'Order Approved' if result_f.success else 'Order Rejected'
    suggested_books = [
        {'title': b.title, 'author': b.author}
        for b in result_f.suggested_books
    ] if result_f.success else []

    # 拿到最终向量时钟 VCf（用事件 f 的结果）
    final_vc = result_f.vector_clock
    logger.info(f"Final Vector Clock for OrderID {order_id}: {final_vc}")
    response = {'orderId': order_id, 'status': status, 'suggestedBooks': suggested_books}
    logger.info(f"Final response: status={status}, suggestedBooks={suggested_books}")
    
    # 如果订单通过验证，入队
    if result_f.success:
        enqueue_response = order_queue_stub.Enqueue(order_queue.EnqueueRequest(
            order_id=order_id,
            user_name=user_name,
            items=[order_queue.Item(name=item['name'], quantity=item['quantity']) for item in items],
            shipping_method=shipping_method
        ))
        if not enqueue_response.success:
            logger.error(f"Failed to enqueue OrderID {order_id}")
            response['status'] = 'Order Rejected'
            response['reason'] = 'Failed to process order queue'
        else:
            logger.info(f"OrderID {order_id} enqueued successfully")

    # 步骤 8：广播清理
    broadcast_clear(order_id, final_vc)
    
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)