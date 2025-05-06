import grpc
from concurrent import futures
import threading
import os
import json
import logging
import sys

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
database_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/database'))
sys.path.insert(0, database_grpc_path)
import database_pb2
import database_pb2_grpc


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
    Implementation of the Books Database service, supporting the Primary-Backup consistency protocol and the 2PC distributed commit protocol.
    - Primary-Backup: The primary replica (replica_id=1) handles all write operations and synchronizes them to backup replicas.
    - 2PC: Acts as a participant, supporting Prepare/Commit/Abort operations to ensure transactional consistency for orders.
    - Recovery Mechanism: Uses a log file to persist 2PC states, enabling fault recovery.
"""
class BooksDatabaseServicer(database_pb2_grpc.BooksDatabaseServicer):
    def __init__(self):
        # 键值存储：{book_title: {"stock": int, "price": float, "threshold": int}}
        self.db = {}
        # 2PC 待处理更新：{order_id: [(book_title, new_stock, price)]}
        self.pending_updates = {}
        # 本地锁，确保线程安全
        self.lock = threading.Lock()
        # 副本 ID，主副本为 1
        self.replica_id = int(os.getenv("REPLICA_ID", "1"))
        # 备份副本地址，仅主副本使用
        self.backup_addresses = ["database_2:50062", "database_3:50063"] if self.replica_id == 1 else []
        # 日志文件，用于故障恢复
        self.log_file = f"db_log_{self.replica_id}.json"
        self._load_log()
        logger.info(f"Database replica {self.replica_id} initialized")

    def _load_log(self):
        """加载日志，恢复未完成事务"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    self.pending_updates = json.load(f)
                logger.info(f"Loaded log from {self.log_file}")
            except Exception as e:
                logger.error(f"Failed to load log: {e}")

    def _save_log(self):
        """保存待处理更新到日志"""
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.pending_updates, f)
            logger.info(f"Saved log to {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to save log: {e}")

    def _sync_to_backups(self, book_title, stock, price, threshold):
        """主副本同步写操作到备份副本"""
        if self.replica_id != 1:
            return True
        for addr in self.backup_addresses:
            try:
                with grpc.insecure_channel(addr) as channel:
                    stub = database_pb2_grpc.BooksDatabaseStub(channel)
                    response = stub.Write(database_pb2.WriteRequest(
                        book_title=book_title,
                        stock=stock,
                        price=price,
                        threshold=threshold
                    ))
                    if not response.success:
                        logger.error(f"Failed to sync to {addr}")
                        return False
            except grpc.RpcError as e:
                logger.error(f"gRPC error syncing to {addr}: {e}")
                return False
        return True
    
    def Read(self, request, context):
        """读取书籍的库存和价格"""
        book_title = request.book_title
        with self.lock:
            if book_title in self.db:
                book = self.db[book_title]
                logger.info(f"Read {book_title}: stock={book['stock']}, price={book['price']}")
                return database_pb2.ReadResponse(
                    success=True,
                    message="Read successful",
                    stock=book["stock"],
                    price=book["price"]
                )
            logger.warning(f"Book not found: {book_title}")
            return database_pb2.ReadResponse(
                success=False,
                message="Book not found",
                stock=0,
                price=0.0
            )

    def Write(self, request, context):
        """写入书籍的库存、价格和阈值"""
        book_title = request.book_title
        stock = request.stock
        price = request.price
        threshold = request.threshold
        with self.lock:
            self.db[book_title] = {
                "stock": stock,
                "price": price,
                "threshold": threshold
            }
            if self.replica_id == 1:  # 主副本同步
                if not self._sync_to_backups(book_title, stock, price, threshold):
                    logger.error(f"Write failed: sync to backups failed for {book_title}")
                    return database_pb2.WriteResponse(
                        success=False,
                        message="Failed to sync to backups"
                    )
            logger.info(f"Write {book_title}: stock={stock}, price={price}, threshold={threshold}")
            return database_pb2.WriteResponse(
                success=True,
                message="Write successful"
            )

    def DecrementStock(self, request, context):
        """减少书籍库存"""
        book_title = request.book_title
        quantity = request.quantity
        with self.lock:
            if book_title in self.db and self.db[book_title]["stock"] >= quantity:
                self.db[book_title]["stock"] -= quantity
                new_stock = self.db[book_title]["stock"]
                price = self.db[book_title]["price"]
                threshold = self.db[book_title]["threshold"]
                if self.replica_id == 1:  # 主副本同步
                    if not self._sync_to_backups(book_title, new_stock, price, threshold):
                        logger.error(f"DecrementStock failed: sync to backups failed for {book_title}")
                        return database_pb2.DecrementStockResponse(
                            success=False,
                            message="Failed to sync to backups",
                            new_stock=new_stock
                        )
                logger.info(f"Decremented {book_title}: new_stock={new_stock}")
                return database_pb2.DecrementStockResponse(
                    success=True,
                    message="Stock decremented",
                    new_stock=new_stock
                )
            logger.warning(f"DecrementStock failed: insufficient stock or book not found: {book_title}")
            return database_pb2.DecrementStockResponse(
                success=False,
                message="Insufficient stock or book not found",
                new_stock=0
            )

    def IncrementStock(self, request, context):
        """增加书籍库存"""
        book_title = request.book_title
        quantity = request.quantity
        with self.lock:
            if book_title not in self.db:
                self.db[book_title] = {"stock": 0, "price": 0.0, "threshold": 0}
            self.db[book_title]["stock"] += quantity
            new_stock = self.db[book_title]["stock"]
            price = self.db[book_title]["price"]
            threshold = self.db[book_title]["threshold"]
            if self.replica_id == 1:  # 主副本同步
                if not self._sync_to_backups(book_title, new_stock, price, threshold):
                    logger.error(f"IncrementStock failed: sync to backups failed for {book_title}")
                    return database_pb2.IncrementStockResponse(
                        success=False,
                        message="Failed to sync to backups",
                        new_stock=new_stock
                    )
            logger.info(f"Incremented {book_title}: new_stock={new_stock}")
            return database_pb2.IncrementStockResponse(
                success=True,
                message="Stock incremented",
                new_stock=new_stock
            )

    def SetStockThreshold(self, request, context):
        """设置书籍库存阈值"""
        book_title = request.book_title
        threshold = request.threshold
        with self.lock:
            if book_title not in self.db:
                self.db[book_title] = {"stock": 0, "price": 0.0, "threshold": 0}
            self.db[book_title]["threshold"] = threshold
            stock = self.db[book_title]["stock"]
            price = self.db[book_title]["price"]
            if self.replica_id == 1:  # 主副本同步
                if not self._sync_to_backups(book_title, stock, price, threshold):
                    logger.error(f"SetStockThreshold failed: sync to backups failed for {book_title}")
                    return database_pb2.SetStockThresholdResponse(
                        success=False,
                        message="Failed to sync to backups"
                    )
            logger.info(f"Set threshold for {book_title}: threshold={threshold}")
            return database_pb2.SetStockThresholdResponse(
                success=True,
                message="Threshold set successfully"
            )

    def CheckStockThreshold(self, request, context):
        """检查书籍库存是否低于阈值"""
        book_title = request.book_title
        with self.lock:
            if book_title in self.db:
                book = self.db[book_title]
                is_below = book["stock"] < book["threshold"]
                logger.info(f"Checked {book_title}: stock={book['stock']}, threshold={book['threshold']}, below={is_below}")
                return database_pb2.CheckStockThresholdResponse(
                    success=True,
                    message="Check successful",
                    is_below=is_below
                )
            logger.warning(f"CheckStockThreshold failed: book not found: {book_title}")
            return database_pb2.CheckStockThresholdResponse(
                success=False,
                message="Book not found",
                is_below=False
            )

    def Prepare(self, request, context):
        """
        2PC Prepare Phase: Check if there is enough stock and record the pending update.
         - If stock is not enough, return failure.
         - Otherwise, save the update in pending_updates and write it to the log.
        """

        order_id = request.order_id
        updates = [(update.book_title, update.quantity) for update in request.updates]
        with self.lock:
            # 检查库存
            for book_title, quantity in updates:
                if book_title not in self.db or self.db[book_title]["stock"] < quantity:
                    logger.warning(f"Prepare failed: insufficient stock for {book_title}")
                    return database_pb2.PrepareResponse(
                        success=False,
                        message=f"Insufficient stock for {book_title}"
                    )
            # 记录待处理更新
            self.pending_updates[order_id] = [
                (book_title, self.db[book_title]["stock"] - quantity, self.db[book_title]["price"], self.db[book_title]["threshold"])
                for book_title, quantity in updates
            ]
            self._save_log()
            logger.info(f"Prepared order {order_id}")
            return database_pb2.PrepareResponse(
                success=True,
                message="Database prepared"
            )

    def Commit(self, request, context):
        """2PC 提交阶段"""
        order_id = request.order_id
        with self.lock:
            if order_id in self.pending_updates:
                for book_title, new_stock, price, threshold in self.pending_updates[order_id]:
                    self.db[book_title] = {"stock": new_stock, "price": price, "threshold": threshold}
                    if self.replica_id == 1:  # 主副本同步
                        self._sync_to_backups(book_title, new_stock, price, threshold)
                del self.pending_updates[order_id]
                self._save_log()
                logger.info(f"Committed order {order_id}")
                return database_pb2.CommitResponse(
                    success=True,
                    message="Database committed"
                )
            logger.warning(f"Commit failed: no pending updates for {order_id}")
            return database_pb2.CommitResponse(
                success=False,
                message="No pending updates"
            )

    def Abort(self, request, context):
        """2PC 中止阶段"""
        order_id = request.order_id
        with self.lock:
            if order_id in self.pending_updates:
                del self.pending_updates[order_id]
                self._save_log()
            logger.info(f"Aborted order {order_id}")
            return database_pb2.AbortResponse(
                success=True,
                message="Database aborted"
            )

def serve(port):
    """启动 gRPC 服务器"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    database_pb2_grpc.add_BooksDatabaseServicer_to_server(BooksDatabaseServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting server on port {port}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    port = os.getenv("PORT", "50061")
    serve(port)