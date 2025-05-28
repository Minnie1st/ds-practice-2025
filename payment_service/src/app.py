import os
import sys
import grpc
from concurrent import futures
import threading
import json
import logging
import time
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.metrics import Observation

# 设置 gRPC 路径
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
payment_service_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/payment_service'))
sys.path.insert(0, payment_service_grpc_path)

import payment_service_pb2
import payment_service_pb2_grpc

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置 OpenTelemetry
resource = Resource.create(attributes={SERVICE_NAME: "payment-service"})

# 配置追踪
tracer_provider = TracerProvider(resource=resource)
trace_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://observability:4318/v1/traces"))
tracer_provider.add_span_processor(trace_processor)
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

# 配置指标
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://observability:4318/v1/metrics")
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

class PaymentServiceServicer(payment_service_pb2_grpc.PaymentServiceServicer):
    # 类属性：共享的指标对象
    _meter = meter

    @classmethod
    def init_metrics(cls):
        """初始化指标（只调用一次）"""
        cls.prepare_counter = cls._meter.create_counter(
            name="payment_prepare_requests_total",
            description="Total number of Prepare requests",
            unit="1"
        )
        cls.commit_counter = cls._meter.create_counter(
            name="payment_commit_requests_total",
            description="Total number of Commit requests",
            unit="1"
        )
        cls.active_sessions = cls._meter.create_up_down_counter(
            name="active_payment_sessions",
            description="Number of active payment sessions",
            unit="1"
        )
        cls.prepare_latency_histogram = cls._meter.create_histogram(
            name="payment_prepare_latency_seconds",
            description="Latency of Prepare requests in seconds",
            unit="s"
        )
        cls.error_counter = cls._meter.create_counter(
            name="payment_errors_total",
            description="Total number of errors in payment operations",
            unit="1"
        )
        cls.pending_payments_gauge = cls._meter.create_observable_gauge(
            name="pending_payments_count",
            description="Number of pending payments",
            unit="1",
            callbacks=[cls.pending_payments_callback]
        )

    @classmethod
    def pending_payments_callback(cls, options):
        """回调函数，用于 ObservableGauge，访问全局实例的 pending_payments"""
        return [Observation(value=len(cls._instance.pending_payments), attributes={})]

    def __init__(self):
        self.pending_payments = {}
        self.lock = threading.Lock()
        self.log_file = "payment_log.json"
        # 初始化指标（仅在第一次实例化时调用）
        if not hasattr(self.__class__, 'prepare_counter'):
            self.__class__.init_metrics()
        # 存储全局实例以供回调使用
        self.__class__._instance = self
        self._load_log()
        logger.info("Payment service initialized")

    def _load_log(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    self.pending_payments = json.load(f)
                logger.info(f"Loaded log from {self.log_file}")
            except Exception as e:
                logger.error(f"Failed to load log: {e}")
                self.__class__.error_counter.add(1, {"operation": "load_log"})

    def _save_log(self):
        try:
            with open(self.log_file, "w") as f:
                json.dump(self.pending_payments, f)
            logger.info(f"Saved log to {self.log_file}")
        except Exception as e:
            logger.error(f"Failed to save log: {e}")
            self.__class__.error_counter.add(1, {"operation": "save_log"})

    def Prepare(self, request, context):
        with tracer.start_as_current_span("Prepare") as span:
            span.set_attribute("order_id", request.order_id)
            span.set_attribute("amount", request.amount)
            start_time = time.time()

            order_id = request.order_id
            amount = request.amount
            if order_id == "order_payment_fail_trigger":
                logger.error(f"Prepare failed for order {order_id}: simulated failure")
                self.__class__.error_counter.add(1, {"operation": "prepare"})
                span.set_attribute("error", True)
                return payment_service_pb2.PrepareResponse(success=False, message="Simulated failure")

            with self.lock:
                self.pending_payments[order_id] = amount
                self._save_log()
                logger.info(f"Prepared payment for order {order_id}: amount={amount}")
                self.__class__.prepare_counter.add(1, {"status": "success"})
                self.__class__.active_sessions.add(1, {"status": "success"})
                self.__class__.prepare_latency_histogram.record(time.time() - start_time)
                span.set_attribute("status", "success")
                return payment_service_pb2.PrepareResponse(success=True, message="Payment prepared")

    def Commit(self, request, context):
        with tracer.start_as_current_span("Commit") as span:
            span.set_attribute("order_id", request.order_id)
            order_id = request.order_id
            with self.lock:
                if order_id in self.pending_payments:
                    amount = self.pending_payments[order_id]
                    del self.pending_payments[order_id]
                    self._save_log()
                    logger.info(f"Committed payment for order {order_id}: amount={amount}")
                    self.__class__.commit_counter.add(1, {"status": "success"})
                    self.__class__.active_sessions.add(-1, {"status": "success"})
                    span.set_attribute("status", "success")
                    return payment_service_pb2.CommitResponse(success=True, message="Payment committed")
                logger.warning(f"Commit failed: no pending payment for {order_id}")
                self.__class__.error_counter.add(1, {"operation": "commit"})
                span.set_attribute("error", True)
                return payment_service_pb2.CommitResponse(success=False, message="No pending payment")

    def Abort(self, request, context):
        with tracer.start_as_current_span("Abort") as span:
            span.set_attribute("order_id", request.order_id)
            order_id = request.order_id
            with self.lock:
                if order_id in self.pending_payments:
                    del self.pending_payments[order_id]
                    self._save_log()
                logger.info(f"Aborted payment for order {order_id}")
                self.__class__.active_sessions.add(-1, {"status": "success"})
                span.set_attribute("status", "success")
                return payment_service_pb2.AbortResponse(success=True, message="Payment aborted")

payment_service = PaymentServiceServicer()  # 全局实例

def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_service_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    logger.info(f"Starting payment service on port {port}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    port = os.getenv("PORT", "50064")
    serve(port)