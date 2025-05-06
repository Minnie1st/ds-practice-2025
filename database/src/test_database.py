import grpc
import sys
import os
import threading
import time

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
sys.path.insert(0, database_grpc_path)
import database_pb2
import database_pb2_grpc

def write_book(stub, book_title, stock, thread_id):
    response = stub.Write(database_pb2.WriteRequest(
        book_title=book_title,
        stock=stock,
        price=19.99,  # 使用默认价格
        threshold=10
    ))
    print(f"Thread {thread_id} Write: success={response.success}, stock={stock}")

def decrement_stock(stub, book_title, quantity, thread_id):
    response = stub.DecrementStock(database_pb2.DecrementStockRequest(
        book_title=book_title,
        quantity=quantity
    ))
    print(f"Thread {thread_id} DecrementStock: success={response.success}, new_stock={response.new_stock}")

def test_database_combined():
    replicas = ['localhost:50061', 'localhost:50062', 'localhost:50063']
    book_title = "B"
    
    # Test 1: Read/Write on Primary
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        write_response = stub.Write(database_pb2.WriteRequest(
            book_title=book_title,
            stock=100,
            price=15.99,
            threshold=10
        ))
        assert write_response.success, "Write failed"
        read_response = stub.Read(database_pb2.ReadRequest(book_title=book_title))
        assert read_response.success and read_response.stock == 100, "Read failed"
        print(f"Read/Write Test: stock={read_response.stock}, price={read_response.price}")

    # Wait for replication
    time.sleep(0.5)

    # Test 2: Replication
    final_stocks = []
    for replica in replicas:
        with grpc.insecure_channel(replica) as channel:
            stub = database_pb2_grpc.BooksDatabaseStub(channel)
            read_response = stub.Read(database_pb2.ReadRequest(book_title=book_title))
            assert read_response.success, f"Read failed on {replica}"
            final_stocks.append(read_response.stock)
            print(f"Replication Test ({replica}): stock={read_response.stock}")
    assert len(set(final_stocks)) == 1, "Replication inconsistent"

    # Test 3: Concurrent Writes (Consistency)
    book_title_concurrent = "A"
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        # Initial write
        stub.Write(database_pb2.WriteRequest(book_title=book_title_concurrent, stock=50, price=20.0, threshold=10))
        threads = []
        for i in range(3):
            t = threading.Thread(target=write_book, args=(stub, book_title_concurrent, 50 + i * 10, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    time.sleep(0.5)  # 等待副本同步

    final_stocks = []
    for replica in replicas:
        with grpc.insecure_channel(replica) as channel:
            stub = database_pb2_grpc.BooksDatabaseStub(channel)
            read_response = stub.Read(database_pb2.ReadRequest(book_title=book_title_concurrent))
            final_stocks.append(read_response.stock)
            print(f"Consistency Test ({replica}): stock={read_response.stock}")
    assert len(set(final_stocks)) == 1, "Consistency failed"

    # Test 4: Concurrent DecrementStock (Bonus)
    book_title_decrement = "Catch-22"
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        stub.Write(database_pb2.WriteRequest(book_title=book_title_decrement, stock=100, price=14.99, threshold=10))
        threads = []
        for i in range(2):
            t = threading.Thread(target=decrement_stock, args=(stub, book_title_decrement, 60, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        # 检查最终库存
        read_response = stub.Read(database_pb2.ReadRequest(book_title=book_title_decrement))
        print(f"Concurrent Decrement Test: final_stock={read_response.stock}")
        assert read_response.stock in [40, 100], "Concurrent decrements failed (both succeeded or both failed)"

if __name__ == "__main__":
    test_database_combined()
    print("Database Combined Test passed (Read/Write, Replication, Consistency, Concurrent Writes)!")
