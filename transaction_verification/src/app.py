import sys
import os
import grpc
from concurrent import futures
from datetime import datetime
import logging

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
transaction_verification_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_verification_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

class TransactionVerificationServicer(transaction_verification_grpc.TransactionVerificationServicer):
    def VerifyTransaction(self, request, context):
        card_number = request.card_number.replace('-', '')
        is_valid_card = len(card_number) == 16 and card_number.isdigit()
        is_valid_cvv = len(request.cvv) in [3, 4] and request.cvv.isdigit()
        is_valid_expiry = False
        if request.expirationDate:
            try:
                exp_month, exp_year = map(int, request.expirationDate.split('/'))
                exp_year += 2000
                current_year, current_month = map(int, datetime.now().strftime("%Y-%m").split('-'))
                is_valid_expiry = (exp_year > current_year) or (exp_year == current_year and exp_month >= current_month)
            except ValueError:
                is_valid_expiry = False
        is_valid_items = len(request.items) > 0
        is_valid = is_valid_card and is_valid_cvv and is_valid_expiry and is_valid_items
        
        # 添加 cvv 和 expirationDate 到日志
        logger.info("Transaction verification for user %s: card=%s, cvv=%s, expirationDate=%s, items=%d, is_valid=%s",
                    request.user_name, card_number[-4:], request.cvv, request.expirationDate, len(request.items), is_valid)
        return transaction_verification.OrderResponse(is_valid=is_valid)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    transaction_verification_grpc.add_TransactionVerificationServicer_to_server(
        TransactionVerificationServicer(), server
    )
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Transaction Verification service started on port 50052")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()