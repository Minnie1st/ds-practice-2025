import grpc

import os
import sys


FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
sys.path.insert(0, database_grpc_path)
import database_pb2
import database_pb2_grpc

with grpc.insecure_channel('localhost:50061') as channel:
    stub = database_pb2_grpc.BooksDatabaseStub(channel)
    books = [
        ("Book A", 10,20,5),
        ("Book B", 5,10,2),
        ("Book C", 10,20,5),
        ("Book D", 1,10,1)
    ]
    for title, stock, price, threshold in books:
        stub.Write(database_pb2.WriteRequest(
            book_title=title,
            stock=stock,
            price=price,
            threshold=threshold
        ))
        print(f"Initialized {title}: stock={stock}, price={price}, threshold={threshold}")