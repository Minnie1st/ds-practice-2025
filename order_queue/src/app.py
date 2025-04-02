import grpc
from concurrent import futures
import logging
import heapq
import threading
import os
import sys
import time
import google.generativeai as genai
import re

# Add order_queue to sys.path
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)

import order_queue_pb2
import order_queue_pb2_grpc

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')  

class PriorityOrderQueue:
    def __init__(self):
        self.queue = []  # Priority queue using heapq
        self.lock = threading.Lock()  # Lock for thread safety
        self.order_map = {}  # Store order details with enqueue timestamp

    def get_ai_priority(self, user_name, items, shipping_method):
        """Get priority score from Gemini API"""
        # // 将订单信息格式化为 Gemini 的输入提示
        items_str = ", ".join(f"{item.name} (x{item.quantity})" for item in items)
        prompt = (
            f"This is a bookstore order: User {user_name}, purchased {items_str}, "
            f"shipping method is {shipping_method or 'standard'}. "
            f"Please evaluate the urgency of this order and return only an integer from 0 to 100."
        )
        try:
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            # 修改 2: 添加正则表达式提取整数
            match = re.search(r'\d+', response_text)
            if match:
                ai_score = int(match.group(0))
                if 0 <= ai_score <= 100:
                    logger.info(f"Gemini AI priority score: {ai_score}")
                    return ai_score
                else:
                    logger.warning(f"Invalid AI score {ai_score}, using default 50")
                    return 50
            else:
                logger.warning(f"No integer found in response: {response_text}, using default 50")
                return 50
        except Exception as e:
            logger.error(f"Gemini API error: {e}, using default 50")
            return 50  # Default score on failure

    def calculate_priority(self, user_name, items, shipping_method, enqueue_time):
        """Calculate dynamic priority for an order"""
        # Factor 1: Books quantity
        num_items = len(items)
        item_score = num_items * 10  # 10 points per book

        # Factor 2: Shipping method
        shipping_score = 50 if shipping_method == "express" else 0  # 快递加 50 分

        # Factor 3: Waiting time (in seconds since enqueue)
        current_time = time.time()
        waiting_time = current_time - enqueue_time
        waiting_score = min(waiting_time * 2, 100)  # 每秒 2 分，最高 100 分

        # Factor 4: AI heuristic score
        ai_score = self.get_ai_priority(user_name, items, shipping_method)

        # Total priority
        priority = item_score + shipping_score + waiting_score + ai_score
        logger.info(f"Priority details: items={num_items}, shipping={shipping_score}, ai={ai_score}")
        
        return priority

    def enqueue(self, order_id, user_name, items, shipping_method):
        with self.lock:
            enqueue_time = time.time()  # Record enqueue timestamp
            # // 初始优先级不考虑等待时间，因为刚入队时为 0
            priority = self.calculate_priority(user_name, items, shipping_method, enqueue_time)
            heapq.heappush(self.queue, (-priority, order_id))  # Negative for max heap
            self.order_map[order_id] = (user_name, items, shipping_method, enqueue_time)
            logger.info(f"Enqueued OrderID {order_id} with initial priority {priority}")

    def dequeue(self):
        with self.lock:
            if not self.queue:
                return None, None, None, None
            # // 重新计算优先级，考虑等待时间
            current_priorities = []
            for neg_priority, order_id in self.queue:
                user_name, items, shipping_method, enqueue_time = self.order_map[order_id]
                updated_priority = self.calculate_priority(user_name, items, shipping_method, enqueue_time)
                current_priorities.append((-updated_priority, order_id))
            if not current_priorities:
                return None, None, None, None
            
            # // 清空旧队列，重新构建
            self.queue.clear()
            for prio, oid in current_priorities:
                heapq.heappush(self.queue, (prio, oid))

            # Dequeue the highest priority order
            priority, order_id = heapq.heappop(self.queue)
            user_name, items, shipping_method, enqueue_time = self.order_map.pop(order_id)
            logger.info(f"Dequeued OrderID {order_id} with priority {-priority}")
            return order_id, user_name, items, shipping_method

queue = PriorityOrderQueue()

class OrderQueueServicer(order_queue_pb2_grpc.OrderQueueServicer):
    def Enqueue(self, request, context):
        order_id = request.order_id
        user_name = request.user_name
        items = request.items  # 保持为 order_queue_pb2.Item 对象列表
        shipping_method = request.shipping_method or "standard"
        queue.enqueue(order_id, user_name, items, shipping_method)
        return order_queue_pb2.EnqueueResponse(
            success=True,
            message=f"Order {order_id} enqueued"
        )

    def Dequeue(self, request, context):
        order_id, user_name, items, shipping_method = queue.dequeue()
        if order_id is None:
            return order_queue_pb2.DequeueResponse(
                success=False,
                message="Queue is empty"
            )
        return order_queue_pb2.DequeueResponse(
            success=True,
            message=f"Order {order_id} dequeued",
            order_id=order_id,
            user_name=user_name,
            items=items  # 直接返回原始 items
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_queue_pb2_grpc.add_OrderQueueServicer_to_server(OrderQueueServicer(), server)
    server.add_insecure_port('[::]:50054')
    logger.info("Order Queue service started on port 50054")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()