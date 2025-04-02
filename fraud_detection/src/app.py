import sys
import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
import grpc
from concurrent import futures
import json
import logging
from datetime import datetime

# 全局缓存
order_data_cache = {}  # 存订单数据
vector_clocks = {}     # 存向量时钟

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)

import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

load_dotenv()

class FraudDetectionServicer(fraud_detection_grpc.FraudDetectionServicer):
    def CacheOrder(self, request, context):
        order_id = request.order_id
        # 存订单数据
        order_data_cache[order_id] = {
            'user_name': request.user_name,
            'card_number': request.card_number,
            'expirationDate': request.expirationDate,
            'items': [{'name': item.name, 'quantity': item.quantity} for item in request.items]
        }
        # 初始化向量时钟
        vector_clocks[order_id] = [0, 0, 0]  # 3个服务，初始都是0
        logger.info(f"Fraud Detection: Cached OrderID {order_id}, Vector Clock {vector_clocks[order_id]}")
        return fraud_detection.OrderResponse(
            success=True,
            message="Order cached",
            vector_clock=vector_clocks[order_id]
        )
    
    def CheckUserFraud(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)  # 从请求中拿当前的向量时钟
        vc[1] += 1  # fraud-detection 是第1个位置（从0开始计数），加1
        
        # 拿缓存数据
        data = order_data_cache[order_id]
        user_name = data['user_name']
        items = data['items']
        
        # 判断逻辑
        reasons = []
        # 1. 用户名太短或有重复字符
        if len(user_name) < 3 or any(user_name.count(char) >= 3 for char in user_name):
            reasons.append("Suspicious username: too short or repeated chars")
        # 2. 订单项数量异常
        total_quantity = sum(item['quantity'] for item in items)
        if total_quantity > 100:
            reasons.append(f"High order quantity: {total_quantity}")
        
        # 有任何问题就认为是欺诈
        success = len(reasons) == 0
        vector_clocks[order_id] = vc
        logger.info(f"Event CheckUserFraud: OrderID {order_id}, User {user_name}, Success {success}, Reasons {reasons}, Vector Clock {vc}")
        return fraud_detection.OrderResponse(
            success=success,
            message="User fraud checked" if success else f"User fraud detected: {', '.join(reasons)}",
            vector_clock=vc
        )

    def CheckCardFraud(self, request, context):
        order_id = request.order_id
        vc = list(request.vector_clock)
        vc[1] += 1  # fraud-detection 是第1个位置，更新向量时钟
        vector_clocks[order_id] = vc
        api_key = os.getenv("GOOGLE_API_KEY", "")
        genai.configure(api_key=api_key)

        logger.info(f"Event CheckCardFraud: Received CheckCardFraud for OrderID {order_id}, Vector Clock {vc}")
        
        # 从缓存拿数据
        order_data = order_data_cache.get(order_id)
        if not order_data:
           logger.error(f"No data found for OrderID {order_id}")
           return fraud_detection.OrderResponse(success=False, message="No order data found", vector_clock=vc)

        card_number = order_data['card_number']
        expiration_date = order_data.get('expirationDate', '')  # 从缓存取，默认空字符串
        current_date = datetime.now().strftime("%m/%y")
        masked_card = f"{card_number[:6]}******{card_number[-4:]}" if card_number else "None"
        
        exp_month, exp_year = map(int, expiration_date.split('/'))
        exp_year += 2000
        current_year, current_month = map(int, datetime.now().strftime("%Y-%m").split('-'))
        
        # 构建提示，只检查信用卡相关数据
        prompt = f"""Act as a payment fraud analyst. Below is the credit card data for an order. Analyze it and determine if it indicates potential fraud based on your expertise.

        **Credit Card Data**:
        - Total Items: {len(order_data['items'])}
        - Card: {masked_card}
        - Items: {', '.join([f"{item['name']} (quantity: {item['quantity']})" for item in order_data['items']])}

        **Instructions**:
        - Analyze the data for signs of fraud (e.g., suspicious card patterns, unusual order sizes).
        - **Check test cards**:
          - If the card number starts with 4111, 4242, or 5555, it’s a test card.
          - If it’s a test card, set "is_fraudulent": true and add "TEST_CARD" to reasons.
        - Return a JSON object:
          {{
            "is_fraudulent": true | false,
            "reasons": [string]
          }}
        - Provide clear reasons for your decision. Do not ignore the test card rules.
        """
        print(prompt)
        try:
            logger.info("Calling Gemini API for Card Fraud Check, card=%s", masked_card)
            model = genai.GenerativeModel("gemini-2.0-flash")  
            response = model.generate_content(prompt)
            logger.info("Gemini API call completed")
            
            # 提取 JSON
            raw_text = response.text
            logger.debug("Raw Gemini response: %s", raw_text)
            json_str = re.search(r'\{.*\}', raw_text, re.DOTALL).group()
            result = json.loads(json_str)
            
            # 验证响应结构
            is_fraudulent = result.get("is_fraudulent", False)
            reasons = result.get("reasons", [])
            
            # 最终决定（成功是无欺诈）
            success = not is_fraudulent
            logger.info(f"Event CheckCardFraud: OrderID {order_id}, Card {masked_card}, Success {success}, Reasons {reasons}, Vector Clock {vc}")
            return fraud_detection.OrderResponse(
                success=success,
                message="Card fraud checked" if success else f"Card fraud detected: {', '.join(reasons)}",
                vector_clock=vc
            )
            
        except Exception as e:
            logger.error(f"Error calling Gemini API for OrderID {order_id}: {str(e)}")
            print(f"""
            [ERROR] Card Fraud Detection Failed:
            Error: {str(e)}
            Request Data: {{card: {masked_card}}}
            """)
            return fraud_detection.OrderResponse(
                success=False,
                message=f"Failed to check card fraud: {str(e)}",
                vector_clock=vc
            )
    def ClearOrder(self, request, context):
        order_id = request.order_id
        final_vc = list(request.final_vector_clock)  # VCf
        local_vc = vector_clocks.get(order_id, [0, 0, 0])  # 本地 VC

        # 检查 VC <= VCf
        is_valid = all(local_vc[i] <= final_vc[i] for i in range(len(local_vc)))
        if is_valid:
            # 清理数据
            if order_id in order_data_cache:
                del order_data_cache[order_id]
            if order_id in vector_clocks:
                del vector_clocks[order_id]
            print(f"Fraud Detection: Cleared OrderID {order_id}, Local VC {local_vc}, Final VC {final_vc}")
            return fraud_detection.ClearResponse(
                success=True,
                message="Order data cleared"
            )
        else:
            print(f"Fraud Detection: Error for OrderID {order_id}, Local VC {local_vc} > Final VC {final_vc}")
            return fraud_detection.ClearResponse(
                success=False,
                message="Vector clock mismatch"
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    fraud_detection_grpc.add_FraudDetectionServicer_to_server(
        FraudDetectionServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Fraud Detection service started on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()