"""Thin HTTP/JSON gateway over the gRPC service.

Exposes POST /rpc/<action> endpoints that accept JSON, call the
corresponding gRPC servicer method directly (in-process), and
return the result as JSON. This lets the Node.js tool use plain
fetch() instead of requiring a Node gRPC client dependency.
"""

from __future__ import annotations

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent import futures

import grpc

from . import github_rpc_pb2
from . import github_rpc_pb2_grpc
from .logic import GitHubRpcService

# Maps HTTP action names to (request_class, grpc_method_name) tuples.
ACTION_MAP = {
    "list_pull_requests": (github_rpc_pb2.ListPullRequestsRequest, "ListPullRequests"),
    "view_pull_request": (github_rpc_pb2.ViewPullRequestRequest, "ViewPullRequest"),
    "check_pull_request": (github_rpc_pb2.CheckPullRequestRequest, "CheckPullRequest"),
    "create_pull_request": (github_rpc_pb2.CreatePullRequestRequest, "CreatePullRequest"),
    "merge_pull_request": (github_rpc_pb2.MergePullRequestRequest, "MergePullRequest"),
    "list_issues": (github_rpc_pb2.ListIssuesRequest, "ListIssues"),
    "create_issue": (github_rpc_pb2.CreateIssueRequest, "CreateIssue"),
    "close_issue": (github_rpc_pb2.CloseIssueRequest, "CloseIssue"),
    "list_workflow_runs": (github_rpc_pb2.ListWorkflowRunsRequest, "ListWorkflowRuns"),
    "view_workflow_run": (github_rpc_pb2.ViewWorkflowRunRequest, "ViewWorkflowRun"),
    "rerun_workflow_run": (github_rpc_pb2.RerunWorkflowRunRequest, "RerunWorkflowRun"),
    "github_api": (github_rpc_pb2.GitHubApiRequest, "GitHubApi"),
}


def _proto_to_dict(msg) -> dict:
    """Convert a protobuf message to a dict (simple recursive)."""
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(msg, preserving_proto_field_name=True)


def _dict_to_proto(data: dict, msg_class):
    """Convert a dict to a protobuf message."""
    from google.protobuf.json_format import ParseDict
    return ParseDict(data, msg_class())


class _FakeContext:
    """Minimal gRPC context stub for in-process calls."""

    def __init__(self):
        self._code = None
        self._message = None

    def abort(self, code, message):
        raise Exception(f"gRPC {code}: {message}")

    def set_code(self, code):
        self._code = code

    def set_details(self, message):
        self._message = message


class GatewayHandler(BaseHTTPRequestHandler):
    """Handle POST /rpc/<action> requests."""

    service = GitHubRpcService()

    def log_message(self, format, *args):
        # Silence per-request logs in dev.
        pass

    def do_POST(self):
        # Parse action from URL: /rpc/<action>
        path_parts = self.path.strip("/").split("/")
        if len(path_parts) != 2 or path_parts[0] != "rpc":
            self._error(404, "Not found. Use POST /rpc/<action>.")
            return

        action = path_parts[1]
        if action not in ACTION_MAP:
            self._error(400, f"Unknown action: {action}")
            return

        # Read JSON body.
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._error(400, f"Invalid JSON: {exc}")
            return

        request_class, method_name = ACTION_MAP[action]
        try:
            request_msg = _dict_to_proto(body, request_class)
            method = getattr(self.service, method_name)
            context = _FakeContext()
            response_msg = method(request_msg, context)
            result = _proto_to_dict(response_msg)
            self._json(200, result)
        except Exception as exc:
            self._error(500, str(exc))

    def _json(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str):
        self._json(status, {"error": message})


def serve() -> None:
    """Start the HTTP/JSON gateway (also starts gRPC on a separate port)."""
    addr = os.getenv("GITHUB_RPC_ADDR", "127.0.0.1:50051")
    host, port_str = addr.rsplit(":", 1)
    port = int(port_str)

    # Also start the raw gRPC server on port+1 for direct gRPC clients.
    grpc_port = port + 1
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    github_rpc_pb2_grpc.add_GitHubRpcServicer_to_server(GitHubRpcService(), grpc_server)
    grpc_server.add_insecure_port(f"{host}:{grpc_port}")
    grpc_server.start()
    print(f"gRPC server listening on {host}:{grpc_port}")

    # HTTP/JSON gateway on the main port.
    httpd = HTTPServer((host, port), GatewayHandler)
    print(f"HTTP/JSON gateway listening on {host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        grpc_server.stop(0)
        httpd.server_close()


if __name__ == "__main__":
    serve()
