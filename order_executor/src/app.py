import grpc
from concurrent import futures
import logging
import threading
import time
import os
import sys
import heapq
import random

# 设置 gRPC 相关路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_executor_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_executor'))
sys.path.insert(0, order_executor_grpc_path)
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)

import order_executor_pb2
import order_executor_pb2_grpc
import order_queue_pb2
import order_queue_pb2_grpc

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

queue_channel = grpc.insecure_channel(QUEUE_SERVICE_ADDR)
queue_stub = order_queue_pb2_grpc.OrderQueueStub(queue_channel)

class LeaderState:
    def __init__(self):
        self.id = REPLICA_ID
        self.lock = threading.Lock()
        self.last_heartbeat = time.time()

leader_state = LeaderState()

class OrderExecutorService(order_executor_pb2_grpc.OrderExecutorServicer):
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
            leader_state.last_heartbeat = time.time()  # 每次心跳都更新
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
                            logger.info(f"Found higher ID {leader_state.id} at {service_name}:{port}")
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
                        stub.Heartbeat(order_executor_pb2.HeartbeatMsg(leader_id=REPLICA_ID), timeout=10)  # 增加超时
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

def process_orders():
    for attempt in range(5):
        try:
            grpc.channel_ready_future(queue_channel).result(timeout=5)
            break
        except grpc.FutureTimeoutError:
            logger.warning(f"Waiting for order_queue to be ready (attempt {attempt + 1}/5)...")
            time.sleep(2)
    
    while True:
        with leader_state.lock:
            is_leader = leader_state.id == REPLICA_ID
        if is_leader:
            try:
                response = queue_stub.Dequeue(order_queue_pb2.DequeueRequest(), timeout=5)
                if response.success:
                    logger.info(f"Processing order {response.order_id}")
                    time.sleep(1)
                else:
                    time.sleep(0.1)
            except grpc.RpcError as e:
                logger.error(f"Order dequeue error: {e}")
                time.sleep(5)
        else:
            time.sleep(1)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    order_executor_pb2_grpc.add_OrderExecutorServicer_to_server(OrderExecutorService(), server)
    server.add_insecure_port(f'[::]:{PORT}')
    logger.info(f"Starting order executor replica {REPLICA_ID} on port {PORT}")
    server.start()
    
    wait_for_replicas()
    
    time.sleep(random.uniform(0, 2))
    threading.Thread(target=run_election, daemon=True).start()
    threading.Thread(target=monitor_leader, daemon=True).start()
    threading.Thread(target=process_orders, daemon=True).start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
    