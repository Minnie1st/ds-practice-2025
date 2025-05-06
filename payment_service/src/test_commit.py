import grpc
import os
import sys
import time

# 设置 gRPC 路径

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, database_grpc_path)
sys.path.insert(0, order_queue_grpc_path)

import database_pb2
import database_pb2_grpc
import order_queue_pb2
import order_queue_pb2_grpc

# 服务地址
BOOKS_DATABASE_ADDR = 'localhost:50061'
ORDER_QUEUE_ADDR = 'localhost:50054'

def test_commitment():
    # 初始化 Books Database 数据
    with grpc.insecure_channel(BOOKS_DATABASE_ADDR) as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        print("Initializing Books Database...")
        write_response = stub.Write(database_pb2.WriteRequest(
            book_title="Book A",
            stock=10,
            price=29.99
        ))
        print(f"Write Response: success={write_response.success}, message={write_response.message}")

    # 向订单队列添加订单
    with grpc.insecure_channel(ORDER_QUEUE_ADDR) as channel:
        stub = order_queue_pb2_grpc.OrderQueueStub(channel)
        print("\nEnqueuing order...")
        enqueue_request = order_queue_pb2.EnqueueRequest(
            order_id="order_1",
            user_name="test_user",
            items=[order_queue_pb2.Item(name="Book A", quantity=2)],
            shipping_method="standard"
        )
        enqueue_response = stub.Enqueue(enqueue_request)
        print(f"Enqueue Response: success={enqueue_response.success}, message={enqueue_response.message}")

    # 等待订单处理
    time.sleep(5)

    # 验证库存更新
    with grpc.insecure_channel(BOOKS_DATABASE_ADDR) as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        print("\nChecking updated stock...")
        read_response = stub.Read(database_pb2.ReadRequest(book_title="Book A"))
print(f"Read Response: success={read_response.success}, stock={read_response.stock}")

if __name__ == '__main__':
    time.sleep(5)  # 等待服务启动
    test_commitment()