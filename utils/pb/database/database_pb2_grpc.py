# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import database_pb2 as database__pb2


class BooksDatabaseStub(object):
    """The Books Database service
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Read = channel.unary_unary(
                '/database.BooksDatabase/Read',
                request_serializer=database__pb2.ReadRequest.SerializeToString,
                response_deserializer=database__pb2.ReadResponse.FromString,
                )
        self.Write = channel.unary_unary(
                '/database.BooksDatabase/Write',
                request_serializer=database__pb2.WriteRequest.SerializeToString,
                response_deserializer=database__pb2.WriteResponse.FromString,
                )
        self.DecrementStock = channel.unary_unary(
                '/database.BooksDatabase/DecrementStock',
                request_serializer=database__pb2.DecrementStockRequest.SerializeToString,
                response_deserializer=database__pb2.DecrementStockResponse.FromString,
                )
        self.IncrementStock = channel.unary_unary(
                '/database.BooksDatabase/IncrementStock',
                request_serializer=database__pb2.IncrementStockRequest.SerializeToString,
                response_deserializer=database__pb2.IncrementStockResponse.FromString,
                )
        self.SetStockThreshold = channel.unary_unary(
                '/database.BooksDatabase/SetStockThreshold',
                request_serializer=database__pb2.SetStockThresholdRequest.SerializeToString,
                response_deserializer=database__pb2.SetStockThresholdResponse.FromString,
                )
        self.CheckStockThreshold = channel.unary_unary(
                '/database.BooksDatabase/CheckStockThreshold',
                request_serializer=database__pb2.CheckStockThresholdRequest.SerializeToString,
                response_deserializer=database__pb2.CheckStockThresholdResponse.FromString,
                )
        self.Prepare = channel.unary_unary(
                '/database.BooksDatabase/Prepare',
                request_serializer=database__pb2.PrepareRequest.SerializeToString,
                response_deserializer=database__pb2.PrepareResponse.FromString,
                )
        self.Commit = channel.unary_unary(
                '/database.BooksDatabase/Commit',
                request_serializer=database__pb2.CommitRequest.SerializeToString,
                response_deserializer=database__pb2.CommitResponse.FromString,
                )
        self.Abort = channel.unary_unary(
                '/database.BooksDatabase/Abort',
                request_serializer=database__pb2.AbortRequest.SerializeToString,
                response_deserializer=database__pb2.AbortResponse.FromString,
                )


class BooksDatabaseServicer(object):
    """The Books Database service
    """

    def Read(self, request, context):
        """Read the stock of a book
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Write(self, request, context):
        """Write the stock of a book
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def DecrementStock(self, request, context):
        """Decrement the stock of a book 
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def IncrementStock(self, request, context):
        """Increment the stock of a book
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SetStockThreshold(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CheckStockThreshold(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Prepare(self, request, context):
        """2PC Operations
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Commit(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Abort(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_BooksDatabaseServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Read': grpc.unary_unary_rpc_method_handler(
                    servicer.Read,
                    request_deserializer=database__pb2.ReadRequest.FromString,
                    response_serializer=database__pb2.ReadResponse.SerializeToString,
            ),
            'Write': grpc.unary_unary_rpc_method_handler(
                    servicer.Write,
                    request_deserializer=database__pb2.WriteRequest.FromString,
                    response_serializer=database__pb2.WriteResponse.SerializeToString,
            ),
            'DecrementStock': grpc.unary_unary_rpc_method_handler(
                    servicer.DecrementStock,
                    request_deserializer=database__pb2.DecrementStockRequest.FromString,
                    response_serializer=database__pb2.DecrementStockResponse.SerializeToString,
            ),
            'IncrementStock': grpc.unary_unary_rpc_method_handler(
                    servicer.IncrementStock,
                    request_deserializer=database__pb2.IncrementStockRequest.FromString,
                    response_serializer=database__pb2.IncrementStockResponse.SerializeToString,
            ),
            'SetStockThreshold': grpc.unary_unary_rpc_method_handler(
                    servicer.SetStockThreshold,
                    request_deserializer=database__pb2.SetStockThresholdRequest.FromString,
                    response_serializer=database__pb2.SetStockThresholdResponse.SerializeToString,
            ),
            'CheckStockThreshold': grpc.unary_unary_rpc_method_handler(
                    servicer.CheckStockThreshold,
                    request_deserializer=database__pb2.CheckStockThresholdRequest.FromString,
                    response_serializer=database__pb2.CheckStockThresholdResponse.SerializeToString,
            ),
            'Prepare': grpc.unary_unary_rpc_method_handler(
                    servicer.Prepare,
                    request_deserializer=database__pb2.PrepareRequest.FromString,
                    response_serializer=database__pb2.PrepareResponse.SerializeToString,
            ),
            'Commit': grpc.unary_unary_rpc_method_handler(
                    servicer.Commit,
                    request_deserializer=database__pb2.CommitRequest.FromString,
                    response_serializer=database__pb2.CommitResponse.SerializeToString,
            ),
            'Abort': grpc.unary_unary_rpc_method_handler(
                    servicer.Abort,
                    request_deserializer=database__pb2.AbortRequest.FromString,
                    response_serializer=database__pb2.AbortResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'database.BooksDatabase', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class BooksDatabase(object):
    """The Books Database service
    """

    @staticmethod
    def Read(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/Read',
            database__pb2.ReadRequest.SerializeToString,
            database__pb2.ReadResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Write(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/Write',
            database__pb2.WriteRequest.SerializeToString,
            database__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def DecrementStock(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/DecrementStock',
            database__pb2.DecrementStockRequest.SerializeToString,
            database__pb2.DecrementStockResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def IncrementStock(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/IncrementStock',
            database__pb2.IncrementStockRequest.SerializeToString,
            database__pb2.IncrementStockResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def SetStockThreshold(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/SetStockThreshold',
            database__pb2.SetStockThresholdRequest.SerializeToString,
            database__pb2.SetStockThresholdResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def CheckStockThreshold(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/CheckStockThreshold',
            database__pb2.CheckStockThresholdRequest.SerializeToString,
            database__pb2.CheckStockThresholdResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Prepare(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/Prepare',
            database__pb2.PrepareRequest.SerializeToString,
            database__pb2.PrepareResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Commit(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/Commit',
            database__pb2.CommitRequest.SerializeToString,
            database__pb2.CommitResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Abort(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/database.BooksDatabase/Abort',
            database__pb2.AbortRequest.SerializeToString,
            database__pb2.AbortResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
