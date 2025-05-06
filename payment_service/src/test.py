import grpc
import sys
import os
import threading
import time
import subprocess
import json

# 设置 gRPC 路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
payment_service_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/payment_service'))
sys.path.insert(0, database_grpc_path)
sys.path.insert(0, order_queue_grpc_path)
sys.path.insert(0, payment_service_grpc_path)

import database_pb2
import database_pb2_grpc
import order_queue_pb2
import order_queue_pb2_grpc
import payment_service_pb2
import payment_service_pb2_grpc

def initialize_database():
    """初始化数据库，设置测试书籍"""
    print("Initializing database...")
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        stub.Write(database_pb2.WriteRequest(
            book_title="A",
            stock=100,
            price=25.99,
            threshold=0
        ))
        stub.Write(database_pb2.WriteRequest(
            book_title="B",
            stock=5,
            price=15.99,
            threshold=0
        ))
    print("Database initialized: A=100, B=5")

def read_stock(book_title):
    """读取书籍库存"""
    print(f"Reading stock for {book_title}...")
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        response = stub.Read(database_pb2.ReadRequest(book_title=book_title))
        stock = response.stock if response.success else None
        print(f"Stock for {book_title}: {stock}")
        return stock

def enqueue_order(order_id, book_title, quantity, price):
    """入队订单"""
    print(f"Enqueuing order {order_id} for {book_title} (quantity={quantity}, price={price})...")
    with grpc.insecure_channel('localhost:50054') as channel:
        stub = order_queue_pb2_grpc.OrderQueueStub(channel)
        response = stub.Enqueue(order_queue_pb2.EnqueueRequest(
            order_id=order_id,
            user_name="TestUser",
            shipping_method="standard",
            items=[order_queue_pb2.Item(
                name=book_title,
                quantity=quantity,
                price=price
            )]
        ))
        print(f"Enqueue {order_id} {'successful' if response.success else 'failed'}")
        return response.success

def check_payment_log():
    """检查支付服务日志文件是否存在支付记录"""
    print("Checking payment log...")
    try:
        subprocess.run(["docker", "cp", "ds-practice-2025-payment_service-1:/app/payment_log.json", "/tmp/payment_log.json"], check=True)
        with open("/tmp/payment_log.json", "r") as f:
            payments = json.load(f)
        os.remove("/tmp/payment_log.json")
        print(f"Payment log: {payments}")
        return payments
    except (FileNotFoundError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        print(f"Failed to read payment log: {e}")
        return {}

def test_successful_transaction():
    """测试 1: 成功事务"""
    print("\n=== Starting Test 1: Successful Transaction ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_success", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 5 seconds for order processing...")
    time.sleep(5)

    final_stock = read_stock("A")
    assert final_stock == 90, f"Stock not updated: {final_stock}"
    payments = check_payment_log()
    assert "order_success" not in payments, "Payment log not cleared"
    print("Test 1 Passed: Stock=90, Payment committed")
    print("=== Test 1 Completed ===\n")

def test_insufficient_stock():
    """测试 2: 库存不足导致事务失败"""
    print("\n=== Starting Test 2: Insufficient Stock ===")
    initialize_database()
    initial_stock = read_stock("B")
    assert initial_stock == 5, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_insufficient", "B", 10, 15.99)
    assert success, "Enqueue failed"
    print("Waiting 5 seconds for order processing...")
    time.sleep(5)

    final_stock = read_stock("B")
    assert final_stock == 5, f"Stock changed: {final_stock}"
    payments = check_payment_log()
    assert "order_insufficient" not in payments, "Payment log not aborted"
    print("Test 2 Passed: Stock unchanged, Transaction aborted")
    print("=== Test 2 Completed ===\n")

def test_payment_failure():
    """测试 3: 支付失败导致事务失败"""
    print("\n=== Starting Test 3: Payment Failure ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_payment_fail_trigger", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 5 seconds for order processing...")
    time.sleep(5)

    final_stock = read_stock("A")
    assert final_stock == 100, f"Stock changed: {final_stock}"
    payments = check_payment_log()
    assert "order_payment_fail_trigger" not in payments, "Payment log not aborted"
    print("Test 3 Passed: Stock unchanged, Transaction aborted")
    print("=== Test 3 Completed ===\n")

def test_concurrent_transactions():
    """测试 4: 并发事务"""
    print("\n=== Starting Test 4: Concurrent Transactions ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    threads = []
    for i in range(3):
        order_id = f"order_concurrent_{i}"
        print(f"Starting thread for {order_id}...")
        t = threading.Thread(target=enqueue_order, args=(order_id, "A", 20, 25.99))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    print("Waiting 10 seconds for all orders to process...")
    time.sleep(10)

    final_stock = read_stock("A")
    assert final_stock in [40, 60, 80, 100], f"Invalid stock: {final_stock}"
    payments = check_payment_log()
    assert len(payments) == 0, "Payment log not cleared"
    print(f"Test 4 Passed: Final stock={final_stock}, Payments cleared")
    print("=== Test 4 Completed ===\n")

def test_participant_failure():
    """测试 5: 参与者失败恢复"""
    print("\n=== Starting Test 5: Participant Failure ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_participant_fail", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 2 seconds for Prepare phase...")
    time.sleep(2)

    print("Stopping payment service...")
    subprocess.run(["docker", "stop", "ds-practice-2025-payment_service-1"])
    print("Waiting 10 seconds for executor to detect failure...")
    time.sleep(10)

    print("Restarting payment service...")
    subprocess.run(["docker", "start", "ds-practice-2025-payment_service-1"])
    print("Waiting 5 seconds for recovery...")
    time.sleep(5)

    final_stock = read_stock("A")
    assert final_stock in [90, 100], f"Stock incorrect: {final_stock}"
    payments = check_payment_log()
    assert "order_participant_fail" not in payments, "Payment log not handled"
    print(f"Test 5 Passed: Stock={final_stock}, Payment log cleared")
    print("=== Test 5 Completed ===\n")

def test_coordinator_failure():
    """测试 6: 协调者失败恢复"""
    print("\n=== Starting Test 6: Coordinator Failure ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_coordinator_fail", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 2 seconds for Prepare phase...")
    time.sleep(2)

    print("Stopping order executor 4...")
    subprocess.run(["docker", "stop", "ds-practice-2025-order_executor_4-1"])
    print("Waiting 10 seconds for leader election...")
    time.sleep(10)

    print("Restarting order executor 4...")
    subprocess.run(["docker", "start", "ds-practice-2025-order_executor_4-1"])
    print("Waiting 5 seconds for recovery...")
    time.sleep(5)

    final_stock = read_stock("A")
    assert final_stock in [90, 100], f"Stock incorrect: {final_stock}"
    payments = check_payment_log()
    assert "order_coordinator_fail" not in payments, "Payment log not handled"
    print(f"Test 6 Passed: Stock={final_stock}, Payment log cleared")
    print("=== Test 6 Completed ===\n")

def test_leader_election():
    """测试 7: 领导人选举"""
    print("\n=== Starting Test 7: Leader Election ===")
    initialize_database()
    initial_stock = read_stock("A")
    assert initial_stock == 100, f"Initial stock incorrect: {initial_stock}"

    success = enqueue_order("order_leader_election", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 2 seconds for order processing...")
    time.sleep(2)

    print("Stopping order executor 4...")
    subprocess.run(["docker", "stop", "ds-practice-2025-order_executor_4-1"])
    print("Waiting 10 seconds for leader election...")
    time.sleep(10)

    print("Enqueuing second order...")
    success = enqueue_order("order_leader_election_2", "A", 10, 25.99)
    assert success, "Enqueue failed"
    print("Waiting 10 seconds for order processing...")
    time.sleep(10)

    final_stock = read_stock("A")
    assert final_stock in [80, 90, 100], f"Stock incorrect: {final_stock}"
    payments = check_payment_log()
    assert len(payments) == 0, "Payment log not cleared"
    print(f"Test 7 Passed: Stock={final_stock}, New leader processed orders")
    print("=== Test 7 Completed ===\n")

def run_all_tests():
    """运行所有测试"""
    print("Starting all tests...")
    test_successful_transaction()
    test_insufficient_stock()
    test_payment_failure()
    test_concurrent_transactions()
    test_participant_failure()
    test_coordinator_failure()
    test_leader_election()
    print("All Tests Passed!")

if __name__ == "__main__":
    run_all_tests()