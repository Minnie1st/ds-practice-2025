import os
import sys
import grpc
from concurrent import futures
import threading
import json
import logging

# 设置 gRPC 路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
payment_service_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/payment_service'))
sys.path.insert(0, payment_service_grpc_path)

import payment_service_pb2
import payment_service_pb2_grpc

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
    Implementation of the Payment Service, acting as a participant in the 2PC protocol.
    - Supports Prepare/Commit/Abort operations to coordinate order payments.
    - Uses a log file (payment_log.json) to persist pending payments and support failure recovery.
    - Provides a simulated failure trigger (order_payment_fail_trigger) for testing purposes.
"""
class PaymentServiceServicer(payment_service_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        # 待处理支付：{order_id: amount}
        self.pending_payments = {}
        # 本地锁，确保线程安全
        self.lock = threading.Lock()
        # 日志文件，用于故障恢复
        self.log_file = "payment_log.json"
        self._load_log()
        logger.info("Payment service initialized")

    def _load_log(self):
        """加载日志，恢复未完成支付"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    self.pending_payments = json.load(f)
                logger.info(f"Loaded log from {self.log_file}")
            except Exception as e:
                logger.error(f"Failed to load log: {e}")

    def _save_log(self):
        """保存待处理支付到日志"""
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.pending_payments, f)
            logger.info(f"Saved log to {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to save log: {e}")

        """
    2PC Prepare Phase: Record the payment operation.
    - Check if the order_id matches the simulated failure trigger.
    - Record the payment amount in pending_payments and write it to the log.
    - Return a success or simulated failure response.
        """
    def Prepare(self, request, context):
        """2PC 准备阶段：记录支付操作"""
        order_id = request.order_id
        amount = request.amount
        # 检查特定订单 ID 以模拟失败
        if order_id == "order_payment_fail_trigger":
            logger.error(f"Prepare failed for order {order_id}: simulated failure")
            return payment_service_pb2.PrepareResponse(success=False, message="Simulated failure")
        with self.lock:
            # 模拟检查账户余额（总是成功）
            self.pending_payments[order_id] = amount
            self._save_log()
            logger.info(f"Prepared payment for order {order_id}: amount={amount}")
            return payment_service_pb2.PrepareResponse(
                success=True,
                message="Payment prepared"
            )

    def Commit(self, request, context):
        """2PC 提交阶段：确认支付"""
        order_id = request.order_id
        with self.lock:
            if order_id in self.pending_payments:
                # 模拟支付执行（确认支付）
                amount = self.pending_payments[order_id]
                del self.pending_payments[order_id]
                self._save_log()
                logger.info(f"Committed payment for order {order_id}: amount={amount}")
                return payment_service_pb2.CommitResponse(
                    success=True,
                    message="Payment committed"
                )
            logger.warning(f"Commit failed: no pending payment for {order_id}")
            return payment_service_pb2.CommitResponse(
                success=False,
                message="No pending payment"
            )

    def Abort(self, request, context):
        """2PC 中止阶段：取消支付"""
        order_id = request.order_id
        with self.lock:
            if order_id in self.pending_payments:
                del self.pending_payments[order_id]
                self._save_log()
            logger.info(f"Aborted payment for order {order_id}")
            return payment_service_pb2.AbortResponse(
                success=True,
                message="Payment aborted"
            )

def serve(port):
    """启动 gRPC 服务器"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_service_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting payment service on port {port}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    port = os.getenv("PORT", "50064")
    serve(port)