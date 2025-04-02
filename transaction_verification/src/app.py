import sys
import os
import grpc
from concurrent import futures
from datetime import datetime
import logging

# 全局缓存
order_data_cache = {}  # 存订单数据
vector_clocks = {}     # 存向量时钟

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_verification_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

class TransactionVerificationServicer(transaction_verification_grpc.TransactionVerificationServicer):
    def CacheOrder(self, request, context):
        order_id = request.order_id
        # 扩展缓存，存储所有用户数据
        order_data_cache[order_id] = {
            'user_name': request.user_name,
            'contact': request.contact if hasattr(request, 'contact') else '',  # 检查 proto 是否包含
            'billing_address': {
                'street': request.billing_address.street if hasattr(request, 'billing_address') else '',
                'city': request.billing_address.city if hasattr(request, 'billing_address') else '',
                'state': request.billing_address.state if hasattr(request, 'billing_address') else '',
                'zip': request.billing_address.zip if hasattr(request, 'billing_address') else '',
                'country': request.billing_address.country if hasattr(request, 'billing_address') else ''
            },
            'card_number': request.card_number,
            'items': [{'name': item.name, 'quantity': item.quantity} for item in request.items],
            'cvv': request.cvv,
            'expirationDate': request.expirationDate
        }
        # 初始化向量时钟
        vector_clocks[order_id] = [0, 0, 0]  # 3个服务，初始都是0
        logger.info(f"Transaction Verification: Cached OrderID {order_id}, Vector Clock {vector_clocks[order_id]}")
        return transaction_verification.OrderResponse(
            success=True,
            message="Order cached",
            vector_clock=vector_clocks[order_id]
        )

    def VerifyItemsNotEmpty(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)
        vc[0] += 1  # 服务0计数加1
        success = len(order_data_cache[order_id]['items']) > 0
        vector_clocks[order_id] = vc
        logger.info(f"Event VerifyItemsNotEmpty: OrderID {order_id}, Success {success}, Vector Clock {vc}")
        return transaction_verification.OrderResponse(success=success, message="Items checked", vector_clock=vc)

    def VerifyUserDataComplete(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)
        vc[0] += 1  # 服务0计数加1

        # 从缓存中获取用户数据
        order_data = order_data_cache.get(order_id, {})
        user_name = order_data.get('user_name', '')
        contact = order_data.get('contact', '')
        billing_address = order_data.get('billing_address', {})

        # 检查所有必填字段
        is_valid_name = bool(user_name)
        is_valid_contact = bool(contact)
        is_valid_address = all([
            bool(billing_address.get('street', '')),
            bool(billing_address.get('city', '')),
            bool(billing_address.get('state', '')),
            bool(billing_address.get('zip', '')),
            bool(billing_address.get('country', ''))
        ])

        # 综合验证结果
        success = is_valid_name and is_valid_contact and is_valid_address
        reasons = []
        if not is_valid_name:
            reasons.append("User name is empty")
        if not is_valid_contact:
            reasons.append("Contact is empty")
        if not is_valid_address:
            reasons.append("Billing address is incomplete")

        # 更新向量时钟
        vector_clocks[order_id] = vc

        # 记录详细日志
        logger.info(
            f"Event VerifyUserDataComplete: OrderID {order_id}, Name={user_name}, Contact={contact}, "
            f"Address={billing_address}, Success={success}, Reasons={reasons}, Vector Clock={vc}"
        )

        # 返回结果
        return transaction_verification.OrderResponse(
            success=success,
            message="User data completeness verified",
            vector_clock=vc,
            reasons=reasons if not success else []  # 需要 proto 支持
        )

    def VerifyCreditCardFormat(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)
        vc[0] += 1
        order_data = order_data_cache.get(order_id, {})
        card_number = order_data.get('card_number', '').replace('-', '')
        cvv = order_data.get('cvv', '')
        expiration_date = order_data.get('expirationDate', '')
        items = order_data.get('items', [])
        is_valid_card = len(card_number) == 16 and card_number.isdigit()
        is_valid_cvv = len(cvv) in [3, 4] and cvv.isdigit()
        is_valid_expiry = False
        if expiration_date:
            try:
                exp_month, exp_year = map(int, expiration_date.split('/'))
                exp_year += 2000
                current_year, current_month = map(int, datetime.now().strftime("%Y-%m").split('-'))
                is_valid_expiry = (exp_year > current_year) or (exp_year == current_year and exp_month >= current_month)
            except ValueError:
                is_valid_expiry = False
        is_valid_items = len(items) > 0
        success = is_valid_card and is_valid_cvv and is_valid_expiry and is_valid_items
        vector_clocks[order_id] = vc
        logger.info(
            "Event VerifyCreditCardFormat: OrderID %s, Card=%s, CVV=%s, Expiration=%s, Items=%d, Success=%s, Vector Clock %s",
            order_id, card_number[-4:] if card_number else "N/A", cvv, expiration_date, len(items), success, vc
        )
        return transaction_verification.OrderResponse(
            success=success,
            message="Credit card format and details verified",
            vector_clock=vc
        )

    def ClearOrder(self, request, context):
        order_id = request.order_id
        final_vc = list(request.final_vector_clock)
        local_vc = vector_clocks.get(order_id, [0, 0, 0])
        is_valid = all(local_vc[i] <= final_vc[i] for i in range(len(local_vc)))
        if is_valid:
            if order_id in order_data_cache:
                del order_data_cache[order_id]
            if order_id in vector_clocks:
                del vector_clocks[order_id]
            print(f"Transaction Verification: Cleared OrderID {order_id}, Local VC {local_vc}, Final VC {final_vc}")
            return transaction_verification.ClearResponse(
                success=True,
                message="Order data cleared"
            )
        else:
            print(f"Transaction Verification: Error for OrderID {order_id}, Local VC {local_vc} > Final VC {final_vc}")
            return transaction_verification.ClearResponse(
                success=False,
                message="Vector clock mismatch"
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    transaction_verification_grpc.add_TransactionVerificationServicer_to_server(
        TransactionVerificationServicer(), server
    )
    server.add_insecure_port('[::]:50052')
    server.start()
    logger.info("Transaction Verification service started on port 50052")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()