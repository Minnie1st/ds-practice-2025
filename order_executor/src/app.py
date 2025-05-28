import grpc
from concurrent import futures
import logging
import threading
import time
import os
import sys
import heapq
import random
import json
import psutil

# 设置 gRPC 相关路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_executor_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_executor'))
sys.path.insert(0, order_executor_grpc_path)
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
sys.path.insert(0, database_grpc_path)
payment_service_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/payment_service'))
sys.path.insert(0, payment_service_grpc_path)

import order_executor_pb2
import order_executor_pb2_grpc
import order_queue_pb2
import order_queue_pb2_grpc
import database_pb2
import database_pb2_grpc
import payment_service_pb2
import payment_service_pb2_grpc

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# OpenTelemetry 配置
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

resource = Resource.create(attributes={
    SERVICE_NAME: "order_executor"
})

tracer_provider = TracerProvider(resource=resource)
span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://observability:4318/v1/traces"))
tracer_provider.add_span_processor(span_processor)
trace.set_tracer_provider(tracer_provider)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://observability:4318/v1/metrics")
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

REPLICA_ID = int(os.getenv('REPLICA_ID', '1'))
PORT = int(os.getenv('PORT', '50055'))
REPLICA_SERVICES = {
    50055: 'order_executor_1',
    50056: 'order_executor_2',
    50057: 'order_executor_3',
    50058: 'order_executor_4'
}
REPLICA_PORTS = list(REPLICA_SERVICES.keys())
QUEUE_SERVICE_ADDR = 'order_queue:50054'
HEARTBEAT_INTERVAL = 60
HEARTBEAT_TIMEOUT = 120
DATABASE_ADDR = 'database_1:50061'
PAYMENT_ADDR = 'payment_service:50064'

# 初始化 gRPC 通道
queue_channel = grpc.insecure_channel(QUEUE_SERVICE_ADDR)
queue_stub = order_queue_pb2_grpc.OrderQueueStub(queue_channel)
db_channel = grpc.insecure_channel(DATABASE_ADDR)
db_stub = database_pb2_grpc.BooksDatabaseStub(db_channel)
payment_channel = grpc.insecure_channel(PAYMENT_ADDR)
payment_stub = payment_service_pb2_grpc.PaymentServiceStub(payment_channel)

class LeaderState:
    def __init__(self):
        self.id = REPLICA_ID
        self.lock = threading.Lock()
        self.last_heartbeat = time.time()

leader_state = LeaderState()

class TransactionState:
    def __init__(self):
        self.transactions = {}  # {order_id: {state, updates, amount}}
        self.lock = threading.Lock()
        self.log_file = f"executor_log_{REPLICA_ID}.json"
        self._load_log()
        logger.info(f"Transaction state initialized for Replica {REPLICA_ID}")

    def _load_log(self):
        """加载事务日志，恢复未完成事务"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    self.transactions = json.load(f)
                logger.info(f"Loaded transaction log from {self.log_file}")
            except Exception as e:
                logger.error(f"Failed to load transaction log: {e}")

    def _save_log(self):
        """保存事务状态到日志"""
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.transactions, f)
            logger.info(f"Saved transaction log to {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to save transaction log: {e}")

    def add_transaction(self, order_id, state, updates, amount):
        """添加事务记录"""
        with self.lock:
            self.transactions[order_id] = {
                "state": state,
                "updates": updates,
                "amount": amount
            }
            self._save_log()

    def update_transaction_state(self, order_id, state):
        """更新事务状态"""
        with self.lock:
            if order_id in self.transactions:
                self.transactions[order_id]["state"] = state
                self._save_log()

    def remove_transaction(self, order_id):
        """删除事务记录"""
        with self.lock:
            if order_id in self.transactions:
                del self.transactions[order_id]
                self._save_log()

transaction_state = TransactionState()

"""
    Implementation of the Order Executor service, acting as the 2PC coordinator to coordinate the Books Database and Payment Service.
    - Uses a leader election mechanism to ensure only one active coordinator.
    - Implements the two-phase commit protocol to ensure transactional consistency of orders.
    - Supports coordinator failure recovery by restoring unfinished transactions from the transaction log.
"""
class OrderExecutorService(order_executor_pb2_grpc.OrderExecutorServicer):
    # 获取 Tracer 和 Meter
    tracer = trace.get_tracer(__name__)
    meter = metrics.get_meter(__name__)

    # 指标定义
    order_counter = meter.create_counter(
        name="order_executor.order_count",
        description="Total number of processed orders",
        unit="1"
    )

    active_transactions = meter.create_up_down_counter(
        name="order_executor.active_transactions",
        description="Number of active transactions",
        unit="1"
    )

    order_duration = meter.create_histogram(
        name="order_executor.order_duration",
        description="Duration of order processing",
        unit="ms"
    )

    def __init__(self):
        # 定义内存使用率的 ObservableGauge
        self.memory_usage_value = psutil.virtual_memory().percent  # 初始值
        self.meter.create_observable_gauge(
            name="order_executor.memory_usage",
            description="Memory usage percentage",
            unit="%",
            callbacks=[self.memory_usage_callback]
        )
        # 在独立线程中更新内存使用率
        self.memory_thread = threading.Thread(target=self._run_memory_gauge, daemon=True)
        self.memory_thread.start()

    def memory_usage_callback(self, options):
        return [metrics.Observation(value=self.memory_usage_value)]

    def _run_memory_gauge(self):
        while True:
            self.memory_usage_value = psutil.virtual_memory().percent  # 更新值
            time.sleep(5)  # 每 5 秒更新一次

    def process_order(self, order):
        """
        Process orders using 2PC to coordinate the database and payment service.
        - Phase 1 (Prepare): Check stock and prepare both the database and payment service.
        - Phase 2 (Commit): If Prepare succeeds, commit the transaction; otherwise, abort it.
        - Use TransactionState to record the transaction status and support failure recovery.
        """
        order_id = order.order_id
        items = order.items
        total_amount = sum(item.quantity * item.price for item in items)

        start_time = time.time()
        with self.tracer.start_as_current_span(f"process_order_{order_id}") as span:
            span.set_attribute("order.id", order_id)
            span.set_attribute("order.total_amount", total_amount)

            # 检查库存（非 2PC，直接读取）
            for item in items:
                book_title = item.name
                quantity = item.quantity
                try:
                    read_response = db_stub.Read(database_pb2.ReadRequest(book_title=book_title))
                    if not read_response.success or read_response.stock < quantity:
                        logger.error(f"Order {order_id} failed: insufficient stock for {book_title}")
                        span.set_status(trace.Status(trace.StatusCode.ERROR, "Insufficient stock"))
                        return False
                except grpc.RpcError as e:
                    logger.error(f"Read error for {book_title}: {e}")
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    return False

            # 2PC Phase 1: Prepare
            updates = [(item.name, item.quantity) for item in items]
            with transaction_state.lock:
                self.active_transactions.add(1)  # 增加活动事务数
            transaction_state.add_transaction(order_id=order_id, state="PREPARING", updates=updates, amount=total_amount)

            with self.tracer.start_as_current_span(f"prepare_phase_{order_id}") as prepare_span:
                try:
                    db_prepare = db_stub.Prepare(database_pb2.PrepareRequest(
                        order_id=order_id,
                        updates=[database_pb2.BookUpdate(book_title=name, quantity=qty) for name, qty in updates]
                    ), timeout=10)
                    if not db_prepare.success:
                        transaction_state.remove_transaction(order_id)
                        logger.error(f"Order {order_id} failed: database prepare failed - {db_prepare.message}")
                        prepare_span.set_status(trace.Status(trace.StatusCode.ERROR, db_prepare.message))
                        with transaction_state.lock:
                            self.active_transactions.add(-1)  # 减少活动事务数
                        return False
                    logger.info(f"Order {order_id}: Database prepared successfully")
                    payment_prepare = payment_stub.Prepare(payment_service_pb2.PrepareRequest(
                        order_id=order_id,
                        amount=total_amount
                    ))
                    if not payment_prepare.success:
                        db_stub.Abort(database_pb2.AbortRequest(order_id=order_id))
                        transaction_state.remove_transaction(order_id)
                        logger.error(f"Order {order_id} failed: payment prepare failed - {payment_prepare.message}")
                        prepare_span.set_status(trace.Status(trace.StatusCode.ERROR, payment_prepare.message))
                        with transaction_state.lock:
                            self.active_transactions.add(-1)  # 减少活动事务数
                        return False

                except grpc.RpcError as e:
                    db_stub.Abort(database_pb2.AbortRequest(order_id=order_id))
                    transaction_state.remove_transaction(order_id)
                    logger.error(f"Order {order_id} failed due to gRPC error: {e}")
                    prepare_span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    with transaction_state.lock:
                        self.active_transactions.add(-1)  # 减少活动事务数
                    return False

            # 2PC Phase 2: Commit
            transaction_state.update_transaction_state(order_id, "COMMITTING")

            db_commit = db_stub.Commit(database_pb2.CommitRequest(order_id=order_id))
            payment_commit = payment_stub.Commit(payment_service_pb2.CommitRequest(order_id=order_id))

            if db_commit.success and payment_commit.success:
                transaction_state.remove_transaction(order_id)
                logger.info(f"Order {order_id} processed successfully")
                span.set_status(trace.Status(trace.StatusCode.OK))
                with transaction_state.lock:
                    self.active_transactions.add(-1)  # 减少活动事务数
                self.order_counter.add(1)  # 增加订单计数
                self.order_duration.record((time.time() - start_time) * 1000)  # 记录处理时间（毫秒）
                return True
            else:
                db_stub.Abort(database_pb2.AbortRequest(order_id=order_id))
                payment_stub.Abort(payment_service_pb2.AbortRequest(order_id=order_id))
                transaction_state.remove_transaction(order_id)
                logger.error(f"Order {order_id} failed during commit")
                span.set_status(trace.Status(trace.StatusCode.ERROR, "Commit failed"))
                with transaction_state.lock:
                    self.active_transactions.add(-1)  # 减少活动事务数
                return False

    def Ping(self, request, context):
        with leader_state.lock:
            logger.info(f"Received Ping request at Replica {REPLICA_ID}")
            return order_executor_pb2.PingResponse(
                leader_id=leader_state.id,
                timestamp=time.time()
            )
    
    def Heartbeat(self, request, context):
        with leader_state.lock:
            logger.info(f"Received Heartbeat from Leader {request.leader_id} at Replica {REPLICA_ID}")
            leader_state.last_heartbeat = time.time()
            if request.leader_id != leader_state.id and request.leader_id > REPLICA_ID:
                leader_state.id = request.leader_id
                logger.info(f"Updated leader to {leader_state.id} via heartbeat")
        return order_executor_pb2.HeartbeatAck()

def wait_for_replicas():
    logger.info(f"Replica {REPLICA_ID} waiting for other replicas to be ready...")
    for attempt in range(10):
        all_ready = True
        for port in REPLICA_PORTS:
            if port == PORT:
                continue
            service_name = REPLICA_SERVICES[port]
            try:
                with grpc.insecure_channel(f'{service_name}:{port}') as channel:
                    grpc.channel_ready_future(channel).result(timeout=3)
                    stub = order_executor_pb2_grpc.OrderExecutorStub(channel)
                    stub.Ping(order_executor_pb2.PingRequest(), timeout=3)
                    logger.info(f"Replica {service_name}:{port} is fully ready")
            except (grpc.FutureTimeoutError, grpc.RpcError) as e:
                logger.warning(f"Replica {service_name}:{port} not ready (attempt {attempt + 1}/10): {e}")
                all_ready = False
        if all_ready:
            logger.info("All replicas are fully ready")
            break
        time.sleep(2)

def run_election():
    logger.info(f"Replica {REPLICA_ID} initiating election...")
    with leader_state.lock:
        current_leader = leader_state.id
    if current_leader != REPLICA_ID:
        logger.info(f"Replica {REPLICA_ID} aborted election, current leader is {current_leader}")
        return
    for attempt in range(5):
        all_responded = True
        for port in REPLICA_PORTS:
            if port == PORT:
                continue
            service_name = REPLICA_SERVICES[port]
            try:
                with grpc.insecure_channel(f'{service_name}:{port}') as channel:
                    stub = order_executor_pb2_grpc.OrderExecutorStub(channel)
                    response = stub.Ping(order_executor_pb2.PingRequest(), timeout=5)
                    logger.info(f"Ping response from {service_name}:{port} - Leader ID: {response.leader_id}")
                    with leader_state.lock:
                        if response.leader_id > leader_state.id:
                            leader_state.id = response.leader_id
                            logger.info(f"Found higher ID {response.leader_id} at {service_name}:{port}")
                            all_responded = False
            except grpc.RpcError as e:
                logger.warning(f"Replica at {service_name}:{port} not responding: {e}")
                all_responded = False
        if all_responded:
            break
        logger.info(f"Retrying election (attempt {attempt + 1}/5)...")
        time.sleep(2)
    with leader_state.lock:
        logger.info(f"Election concluded, Leader ID: {leader_state.id}")
        if leader_state.id == REPLICA_ID:
            start_heartbeat()

def start_heartbeat():
    def _send_heartbeats():
        while True:
            with leader_state.lock:
                if leader_state.id != REPLICA_ID:
                    break
            for port in REPLICA_PORTS:
                if port == PORT:
                    continue
                service_name = REPLICA_SERVICES[port]
                try:
                    with grpc.insecure_channel(f'{service_name}:{port}') as channel:
                        stub = order_executor_pb2_grpc.OrderExecutorStub(channel)
                        stub.Heartbeat(order_executor_pb2.HeartbeatMsg(leader_id=REPLICA_ID), timeout=10)
                        logger.info(f"Heartbeat sent to {service_name}:{port}")
                except grpc.RpcError as e:
                    logger.warning(f"Heartbeat to {service_name}:{port} failed: {e}")
            time.sleep(HEARTBEAT_INTERVAL)
    threading.Thread(target=_send_heartbeats, daemon=True).start()

def monitor_leader():
    while True:
        with leader_state.lock:
            time_since_last = time.time() - leader_state.last_heartbeat
            logger.debug(f"Replica {REPLICA_ID} - Time since last heartbeat: {time_since_last:.2f}s")
            if leader_state.id != REPLICA_ID and time_since_last > HEARTBEAT_TIMEOUT:
                logger.warning(f"Leader heartbeat timeout (last heartbeat {time_since_last:.2f}s ago), initiating election")
                run_election()
        time.sleep(HEARTBEAT_TIMEOUT / 2)

def recover_transactions():
    """恢复未完成的事务"""
    with transaction_state.lock:
        for order_id, tx in list(transaction_state.transactions.items()):
            state = tx["state"]
            if state == "PREPARING":
                logger.info(f"Recovering transaction {order_id}: aborting")
                try:
                    db_stub.Abort(database_pb2.AbortRequest(order_id=order_id))
                    payment_stub.Abort(payment_service_pb2.AbortRequest(order_id=order_id))
                    transaction_state.remove_transaction(order_id)
                except grpc.RpcError as e:
                    logger.error(f"Failed to abort transaction {order_id} during recovery: {e}")
            elif state == "COMMITTING":
                logger.info(f"Recovering transaction {order_id}: retrying commit")
                try:
                    db_commit = db_stub.Commit(database_pb2.CommitRequest(order_id=order_id))
                    payment_commit = payment_stub.Commit(payment_service_pb2.CommitRequest(order_id=order_id))
                    if db_commit.success and payment_commit.success:
                        transaction_state.remove_transaction(order_id)
                        logger.info(f"Transaction {order_id} committed during recovery")
                    else:
                        db_stub.Abort(database_pb2.AbortRequest(order_id=order_id))
                        payment_stub.Abort(payment_service_pb2.AbortRequest(order_id=order_id))
                        transaction_state.remove_transaction(order_id)
                        logger.error(f"Transaction {order_id} failed during recovery commit")
                except grpc.RpcError as e:
                    logger.error(f"Failed to recover transaction {order_id}: {e}")
                    transaction_state.remove_transaction(order_id)

def process_orders(service):
    """从队列获取订单并处理"""
    # 等待队列服务就绪
    for attempt in range(5):
        try:
            grpc.channel_ready_future(queue_channel).result(timeout=5)
            logger.info("Order queue service is ready")
            break
        except grpc.FutureTimeoutError:
            logger.warning(f"Waiting for order_queue to be ready (attempt {attempt + 1}/5)...")
            time.sleep(2)
    
    # 恢复未完成事务
    recover_transactions()

    while True:
        with leader_state.lock:
            is_leader = leader_state.id == REPLICA_ID
        if is_leader:
            try:
                response = queue_stub.Dequeue(order_queue_pb2.DequeueRequest(), timeout=5)
                if response.success:
                    logger.info(f"Dequeued order {response.order_id}")
                    service.process_order(response)
                else:
                    time.sleep(0.1)  # 队列为空，短暂等待
            except grpc.RpcError as e:
                logger.error(f"Order dequeue error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)  # 非领导者等待

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    service = OrderExecutorService()
    order_executor_pb2_grpc.add_OrderExecutorServicer_to_server(service, server)
    server.add_insecure_port(f'[::]:{PORT}')
    logger.info(f"Starting order executor replica {REPLICA_ID} on port {PORT}")
    server.start()
    
    wait_for_replicas()
    
    time.sleep(random.uniform(0, 2))
    threading.Thread(target=run_election, daemon=True).start()
    threading.Thread(target=monitor_leader, daemon=True).start()
    threading.Thread(target=process_orders, args=(service,), daemon=True).start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()