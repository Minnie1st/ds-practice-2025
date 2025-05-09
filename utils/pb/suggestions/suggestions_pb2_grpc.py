# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import suggestions_pb2 as suggestions__pb2


class SuggestionsStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.CacheOrder = channel.unary_unary(
                '/suggestions.Suggestions/CacheOrder',
                request_serializer=suggestions__pb2.OrderRequest.SerializeToString,
                response_deserializer=suggestions__pb2.OrderResponse.FromString,
                )
        self.GetSuggestions = channel.unary_unary(
                '/suggestions.Suggestions/GetSuggestions',
                request_serializer=suggestions__pb2.OrderRequest.SerializeToString,
                response_deserializer=suggestions__pb2.OrderResponse.FromString,
                )
        self.ClearOrder = channel.unary_unary(
                '/suggestions.Suggestions/ClearOrder',
                request_serializer=suggestions__pb2.ClearRequest.SerializeToString,
                response_deserializer=suggestions__pb2.ClearResponse.FromString,
                )


class SuggestionsServicer(object):
    """Missing associated documentation comment in .proto file."""

    def CacheOrder(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetSuggestions(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ClearOrder(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_SuggestionsServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'CacheOrder': grpc.unary_unary_rpc_method_handler(
                    servicer.CacheOrder,
                    request_deserializer=suggestions__pb2.OrderRequest.FromString,
                    response_serializer=suggestions__pb2.OrderResponse.SerializeToString,
            ),
            'GetSuggestions': grpc.unary_unary_rpc_method_handler(
                    servicer.GetSuggestions,
                    request_deserializer=suggestions__pb2.OrderRequest.FromString,
                    response_serializer=suggestions__pb2.OrderResponse.SerializeToString,
            ),
            'ClearOrder': grpc.unary_unary_rpc_method_handler(
                    servicer.ClearOrder,
                    request_deserializer=suggestions__pb2.ClearRequest.FromString,
                    response_serializer=suggestions__pb2.ClearResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'suggestions.Suggestions', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class Suggestions(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def CacheOrder(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/suggestions.Suggestions/CacheOrder',
            suggestions__pb2.OrderRequest.SerializeToString,
            suggestions__pb2.OrderResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetSuggestions(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/suggestions.Suggestions/GetSuggestions',
            suggestions__pb2.OrderRequest.SerializeToString,
            suggestions__pb2.OrderResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ClearOrder(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/suggestions.Suggestions/ClearOrder',
            suggestions__pb2.ClearRequest.SerializeToString,
            suggestions__pb2.ClearResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
