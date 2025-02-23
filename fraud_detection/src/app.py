import sys
import os
import google.generativeai as genai
from dotenv import load_dotenv
import re
import grpc
from concurrent import futures
import json
import logging

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
    def CheckFraud(self, request, context):
        api_key = os.getenv("GOOGLE_API_KEY", "")
        genai.configure(api_key=api_key)
        logger.info("Loaded GOOGLE_API_KEY: %s", api_key if api_key else "Not set")
        logger.info("Received CheckFraud request from user: %s", request.user_name)
        """Fraud detection core logic using AI analysis"""
        try:
            # Mask sensitive data
            masked_card = f"{request.card_number[:6]}******{request.card_number[-4:]}" if request.card_number else "None"
            total_items = sum(item.quantity for item in request.items)
            
            # 构建订单数据字符串
            items_str = ", ".join([f"{item.name} (quantity: {item.quantity})" for item in request.items])
            billing_address_str = (
                f"street: {request.billing_address.street}, city: {request.billing_address.city}, "
                f"state: {request.billing_address.state}, zip: {request.billing_address.zip}, "
                f"country: {request.billing_address.country}" if request.billing_address else "No Address"
            )
            
            # Build prompt with enhanced instructions
            prompt = f"""Act as a payment fraud analyst. Below is the raw data captured for an order. Analyze it and determine if it indicates potential fraud based on your expertise.

            **Order Data**:
            - User Name: {request.user_name}
            - Card Number: {masked_card}
            - CVV: {request.cvv or 'Not Provided'}
            - Expiration Date: {request.expirationDate or 'Not Provided'}
            - Total Items: {total_items}
            - Items: {items_str}
            - Billing Address: {billing_address_str}
            - Device Language: {request.deviceLanguage or 'Unknown'}
            - User Comment: {request.user_comment or 'None'}
            - Contact: {request.contact or 'Not Provided'}

            **Instructions**:
            - Analyze the data for signs of fraud (e.g., suspicious card patterns, inconsistent locations, unusual order sizes, invalid payment details).
            - **Ensure test cards are identified as fraudulent**: If the card number starts with 4111, 4242, or 5555, it is a known test card pattern commonly used in fraud attempts. In such cases, set "is_fraudulent": true and include "TEST_CARD" in the reasons list. Treat these prefixes as critical indicators of fraud (e.g., "test card", "known fraud pattern", "invalid payment method").
            - Consider other fraud indicators such as expired cards, invalid CVV, geographic mismatches, or unusual order behaviors.
            - Return a JSON object:
            {{
              "is_fraudulent": boolean,  # True if fraud is detected (including test cards), False otherwise
              "reasons": [string]       # List of specific reasons (e.g., "TEST_CARD", "Expired Card", "Geo Mismatch")
            }}
            - Provide clear, specific reasons for your decision. Do not ignore the test card rule.
            """

            model = genai.GenerativeModel("gemini-2.0-flash")  # 使用有效模型
            logger.info("Calling Gemini API with order data: user=%s, card=%s, total_items=%d", 
                        request.user_name, masked_card, total_items)
            response = model.generate_content(prompt)
            logger.info("Gemini API call completed")
            
            # Extract JSON response
            raw_text = response.text
            logger.debug("Raw Gemini response: %s", raw_text)
            json_str = re.search(r'\{.*\}', raw_text, re.DOTALL).group()
            result = json.loads(json_str)
            
            # Validate response structure
            is_fraudulent = result.get("is_fraudulent", False)
            reasons = result.get("reasons", [])
            
            # Final decision
            final_decision = is_fraudulent
            
            # Logging
            logger.info("Returning response: is_fraudulent=%s, reasons=%s", final_decision, reasons)
            return fraud_detection.OrderResponse(is_fraudulent=final_decision)
            
        except Exception as e:
            logger.error("Fraud Detection Failed for user: %s, error: %s", request.user_name, str(e))
            masked_card = f"{request.card_number[:6]}******{request.card_number[-4:]}" if request.card_number else "None"
            print(f"""
            [ERROR] Fraud Detection Failed:
            Error: {str(e)}
            Request Data: {{user: {request.user_name}, card: {masked_card}}}
            """)
            return fraud_detection.OrderResponse(is_fraudulent=True)

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