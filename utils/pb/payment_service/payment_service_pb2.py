# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: payment_service.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15payment_service.proto\x12\x0fpayment_service\"2\n\x0ePrepareRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\x12\x0e\n\x06\x61mount\x18\x02 \x01(\x01\"3\n\x0fPrepareResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"!\n\rCommitRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\"2\n\x0e\x43ommitResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\" \n\x0c\x41\x62ortRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\"1\n\rAbortResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t2\xf1\x01\n\x0ePaymentService\x12L\n\x07Prepare\x12\x1f.payment_service.PrepareRequest\x1a .payment_service.PrepareResponse\x12I\n\x06\x43ommit\x12\x1e.payment_service.CommitRequest\x1a\x1f.payment_service.CommitResponse\x12\x46\n\x05\x41\x62ort\x12\x1d.payment_service.AbortRequest\x1a\x1e.payment_service.AbortResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'payment_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_PREPAREREQUEST']._serialized_start=42
  _globals['_PREPAREREQUEST']._serialized_end=92
  _globals['_PREPARERESPONSE']._serialized_start=94
  _globals['_PREPARERESPONSE']._serialized_end=145
  _globals['_COMMITREQUEST']._serialized_start=147
  _globals['_COMMITREQUEST']._serialized_end=180
  _globals['_COMMITRESPONSE']._serialized_start=182
  _globals['_COMMITRESPONSE']._serialized_end=232
  _globals['_ABORTREQUEST']._serialized_start=234
  _globals['_ABORTREQUEST']._serialized_end=266
  _globals['_ABORTRESPONSE']._serialized_start=268
  _globals['_ABORTRESPONSE']._serialized_end=317
  _globals['_PAYMENTSERVICE']._serialized_start=320
  _globals['_PAYMENTSERVICE']._serialized_end=561
# @@protoc_insertion_point(module_scope)
