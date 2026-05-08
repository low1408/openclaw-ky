"""gRPC server entrypoint for the GitHub RPC service."""

from __future__ import annotations

import os
from concurrent import futures

import grpc

from . import github_rpc_pb2_grpc
from .logic import GitHubRpcService


def serve() -> None:
    address = os.getenv("GITHUB_RPC_ADDR", "127.0.0.1:50051")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    github_rpc_pb2_grpc.add_GitHubRpcServicer_to_server(GitHubRpcService(), server)
    server.add_insecure_port(address)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
