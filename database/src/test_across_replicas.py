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
        price=19.99,
        threshold=10
    ))
    print(f"Thread {thread_id} Write: success={response.success}, stock={stock}")

def decrement_stock(stub, book_title, quantity, thread_id):
    response = stub.DecrementStock(database_pb2.DecrementStockRequest(
        book_title=book_title,
        quantity=quantity
    ))
    print(f"Thread {thread_id} DecrementStock: success={response.success}, new_stock={response.new_stock}")

def test_database_concurrent_decrement_cross_replicas():
    book_title = "Catch-22"
    initial_stock = 100

    # Step 1: Initialize the book on primary
    with grpc.insecure_channel('localhost:50061') as primary_channel:
        primary_stub = database_pb2_grpc.BooksDatabaseStub(primary_channel)
        write_response = primary_stub.Write(database_pb2.WriteRequest(
            book_title=book_title,
            stock=initial_stock,
            price=14.99,
            threshold=10
        ))
        assert write_response.success, "Initial write failed"

    # Wait for replication to complete
    time.sleep(0.5)

    # Step 2: Prepare two stubs to different replicas
    replica_addresses = ['localhost:50061', 'localhost:50062']
    stubs = [
        database_pb2_grpc.BooksDatabaseStub(grpc.insecure_channel(replica_addresses[0])),
        database_pb2_grpc.BooksDatabaseStub(grpc.insecure_channel(replica_addresses[1])),
    ]

    # Step 3: Concurrently call DecrementStock on different replicas
    threads = []
    for i in range(2):
        t = threading.Thread(target=decrement_stock, args=(stubs[i], book_title, 60, i))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    time.sleep(0.5)

    # Step 4: Read from all replicas and validate final stock
    final_stocks = []
    for replica in replica_addresses:
        with grpc.insecure_channel(replica) as channel:
            stub = database_pb2_grpc.BooksDatabaseStub(channel)
            read_response = stub.Read(database_pb2.ReadRequest(book_title=book_title))
            final_stocks.append(read_response.stock)
            print(f"Final stock on {replica}: {read_response.stock}")

    # Step 5: Validate the correctness (either 40 or 100, not -20 or other invalid state)
    assert all(stock in [40, 100] for stock in final_stocks), "Stock inconsistency or invalid concurrent decrement"
    assert len(set(final_stocks)) == 1, "Replicas are inconsistent after concurrent writes"

    print(" Concurrent Decrement across Replicas Test passed!")

if __name__ == "__main__":
    test_database_concurrent_decrement_cross_replicas()
    print("Test passed.")