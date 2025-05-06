import grpc
import sys
import os
import time

# Adjust sys.path for gRPC stubs
FILE = __file__
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, database_grpc_path)
sys.path.insert(0, order_queue_grpc_path)

import database_pb2
import database_pb2_grpc
import order_queue_pb2
import order_queue_pb2_grpc

def test_order_and_operations():
    # Initialize database
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        stub.Write(database_pb2.WriteRequest(
            book_title="A",
            stock=100,
            price=25.99,
            threshold=0
        ))

    # Test 1: Additional Operations (Bonus)
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)

        # DecrementStock
        dec_response = stub.DecrementStock(database_pb2.DecrementStockRequest(
            book_title="A",
            quantity=10
        ))
        assert dec_response.success and dec_response.new_stock == 90, "DecrementStock failed"
        print(f"DecrementStock: new_stock={dec_response.new_stock}")
        
        # IncrementStock
        inc_response = stub.IncrementStock(database_pb2.IncrementStockRequest(
            book_title="A",
            quantity=5
        ))
        assert inc_response.success and inc_response.new_stock == 95, "IncrementStock failed"
        print(f"IncrementStock: new_stock={inc_response.new_stock}")
        
        # SetStockThreshold
        thresh_response = stub.SetStockThreshold(database_pb2.SetStockThresholdRequest(
            book_title="A",
            threshold=100
        ))
        assert thresh_response.success, "SetStockThreshold failed"
        print(f"SetStockThreshold: success={thresh_response.success}")
        
        # CheckStockThreshold
        check_response = stub.CheckStockThreshold(database_pb2.CheckStockThresholdRequest(
            book_title="A"
        ))
        assert check_response.is_below, "CheckStockThreshold failed"
        print(f"CheckStockThreshold: is_below={check_response.is_below}")

    # Test 2: Order Executor
    with grpc.insecure_channel('localhost:50054') as channel:
        queue_stub = order_queue_pb2_grpc.OrderQueueStub(channel)

        enqueue_request = order_queue_pb2.EnqueueRequest(
            order_id="order_1",
            user_name="Alice",
            shipping_method="express",
            items=[
                order_queue_pb2.Item(
                    name="A",
                    quantity=10,
                    price=25.99
                )
            ]
        )

        response = queue_stub.Enqueue(enqueue_request)
        assert response.success, "Enqueue failed"
        print(f"Enqueue Order: success={response.success}")

    # Wait for order processing
    time.sleep(5)

    # Verify stock update
    with grpc.insecure_channel('localhost:50061') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        read_response = stub.Read(database_pb2.ReadRequest(book_title="A"))
        assert read_response.stock == 85, "Order Executor failed to update stock"
        print(f"Order Executor Test: final_stock={read_response.stock}")

if __name__ == "__main__":
    test_order_and_operations()
    print("Order Executor and Additional Operations Test passed!")
