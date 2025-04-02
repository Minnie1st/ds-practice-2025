# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: fraud_detection.proto
# Protobuf Python Version: 4.25.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15\x66raud_detection.proto\x12\x0f\x66raud_detection\"\xa2\x03\n\x0cOrderRequest\x12\x11\n\tuser_name\x18\x01 \x01(\t\x12\x0f\n\x07\x63ontact\x18\x02 \x01(\t\x12\x13\n\x0b\x63\x61rd_number\x18\x03 \x01(\t\x12\x16\n\x0e\x65xpirationDate\x18\x04 \x01(\t\x12\x0b\n\x03\x63vv\x18\x05 \x01(\t\x12$\n\x05items\x18\x06 \x03(\x0b\x32\x15.fraud_detection.Item\x12\x14\n\x0cuser_comment\x18\x07 \x01(\t\x12\x38\n\x0f\x62illing_address\x18\x08 \x01(\x0b\x32\x1f.fraud_detection.BillingAddress\x12\'\n\x06\x64\x65vice\x18\t \x01(\x0b\x32\x17.fraud_detection.Device\x12)\n\x07\x62rowser\x18\n \x01(\x0b\x32\x18.fraud_detection.Browser\x12\x16\n\x0e\x64\x65viceLanguage\x18\x0b \x01(\t\x12\x18\n\x10screenResolution\x18\x0c \x01(\t\x12\x10\n\x08referrer\x18\r \x01(\t\x12\x14\n\x0cvector_clock\x18\x0e \x03(\x05\x12\x10\n\x08order_id\x18\x0f \x01(\t\"&\n\x04Item\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x08quantity\x18\x02 \x01(\x05\"[\n\x0e\x42illingAddress\x12\x0e\n\x06street\x18\x01 \x01(\t\x12\x0c\n\x04\x63ity\x18\x02 \x01(\t\x12\r\n\x05state\x18\x03 \x01(\t\x12\x0b\n\x03zip\x18\x04 \x01(\t\x12\x0f\n\x07\x63ountry\x18\x05 \x01(\t\"1\n\x06\x44\x65vice\x12\x0c\n\x04type\x18\x01 \x01(\t\x12\r\n\x05model\x18\x02 \x01(\t\x12\n\n\x02os\x18\x03 \x01(\t\"(\n\x07\x42rowser\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x0f\n\x07version\x18\x02 \x01(\t\"G\n\rOrderResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x14\n\x0cvector_clock\x18\x03 \x03(\x05\"<\n\x0c\x43learRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\x12\x1a\n\x12\x66inal_vector_clock\x18\x02 \x03(\x05\"1\n\rClearResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t2\xd4\x02\n\x0e\x46raudDetection\x12M\n\nCacheOrder\x12\x1d.fraud_detection.OrderRequest\x1a\x1e.fraud_detection.OrderResponse\"\x00\x12Q\n\x0e\x43heckUserFraud\x12\x1d.fraud_detection.OrderRequest\x1a\x1e.fraud_detection.OrderResponse\"\x00\x12Q\n\x0e\x43heckCardFraud\x12\x1d.fraud_detection.OrderRequest\x1a\x1e.fraud_detection.OrderResponse\"\x00\x12M\n\nClearOrder\x12\x1d.fraud_detection.ClearRequest\x1a\x1e.fraud_detection.ClearResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'fraud_detection_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_ORDERREQUEST']._serialized_start=43
  _globals['_ORDERREQUEST']._serialized_end=461
  _globals['_ITEM']._serialized_start=463
  _globals['_ITEM']._serialized_end=501
  _globals['_BILLINGADDRESS']._serialized_start=503
  _globals['_BILLINGADDRESS']._serialized_end=594
  _globals['_DEVICE']._serialized_start=596
  _globals['_DEVICE']._serialized_end=645
  _globals['_BROWSER']._serialized_start=647
  _globals['_BROWSER']._serialized_end=687
  _globals['_ORDERRESPONSE']._serialized_start=689
  _globals['_ORDERRESPONSE']._serialized_end=760
  _globals['_CLEARREQUEST']._serialized_start=762
  _globals['_CLEARREQUEST']._serialized_end=822
  _globals['_CLEARRESPONSE']._serialized_start=824
  _globals['_CLEARRESPONSE']._serialized_end=873
  _globals['_FRAUDDETECTION']._serialized_start=876
  _globals['_FRAUDDETECTION']._serialized_end=1216
# @@protoc_insertion_point(module_scope)
