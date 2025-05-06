import grpc
import os
import sys
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
sys.path.insert(0, database_grpc_path)
import database_pb2
import database_pb2_grpc


def read_stock(port, books):
    with grpc.insecure_channel(f'localhost:{port}') as channel:
        stub = database_pb2_grpc.BooksDatabaseStub(channel)
        print(f"Replica on port {port}:")
        for book in books:
            response = stub.Read(database_pb2.ReadRequest(book_title=book))
            print(f"  {book}: stock={response.stock}, price={response.price}")

if __name__ == "__main__":
    books = ["Book A", "Book B"]
    for port in ["50061", "50062", "50063"]:
        read_stock(port, books)