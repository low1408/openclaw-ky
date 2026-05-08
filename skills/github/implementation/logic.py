"""RPC mapping logic for GitHub operations."""

from __future__ import annotations

import json
import subprocess
from typing import Iterable, Sequence

import grpc

from . import github_rpc_pb2
from . import github_rpc_pb2_grpc

GH_BIN = "/usr/bin/gh"


class GitHubRpcService(github_rpc_pb2_grpc.GitHubRpcServicer):
    def ListPullRequests(self, request, context):
        args = _base_args(request.repo, ["pr", "list"])
        _append_optional(args, "--state", request.state)
        _append_optional(args, "--limit", _int_to_str(request.limit))
        args.extend(["--json", "number,title,state,author"])
        data = _run_json(args, context)
        items = [
            github_rpc_pb2.PullRequestSummary(
                number=item.get("number", 0),
                title=item.get("title", ""),
                state=item.get("state", ""),
                author_login=(item.get("author") or {}).get("login", ""),
            )
            for item in data
        ]
        return github_rpc_pb2.ListPullRequestsResponse(items=items)

    def ViewPullRequest(self, request, context):
        args = _base_args(request.repo, ["pr", "view", str(request.number)])
        args.extend(["--json", "number,title,body,state,author,additions,deletions,changedFiles"])
        data = _run_json(args, context)
        pr = github_rpc_pb2.PullRequestDetails(
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            state=data.get("state", ""),
            author_login=(data.get("author") or {}).get("login", ""),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changedFiles", 0),
        )
        return github_rpc_pb2.ViewPullRequestResponse(pr=pr)

    def CheckPullRequest(self, request, context):
        args = _base_args(request.repo, ["pr", "checks", str(request.number)])
        args.extend(["--json", "name,status,conclusion"])
        data = _run_json(args, context)
        checks = [
            github_rpc_pb2.CheckSummary(
                name=item.get("name", ""),
                status=item.get("status", ""),
                conclusion=item.get("conclusion", ""),
            )
            for item in data
        ]
        return github_rpc_pb2.CheckPullRequestResponse(checks=checks)

    def CreatePullRequest(self, request, context):
        args = _base_args(request.repo, ["pr", "create"])
        _append_optional(args, "--title", request.title)
        _append_optional(args, "--body", request.body)
        _append_optional(args, "--base", request.base_branch)
        _append_optional(args, "--head", request.head_branch)
        if request.draft:
            args.append("--draft")
        _extend_repeated(args, "--label", request.labels)
        _extend_repeated(args, "--assignee", request.assignees)
        _extend_repeated(args, "--reviewer", request.reviewers)
        args.extend(["--json", "number,url"])
        data = _run_json(args, context)
        return github_rpc_pb2.CreatePullRequestResponse(
            number=data.get("number", 0),
            url=data.get("url", ""),
        )

    def MergePullRequest(self, request, context):
        args = _base_args(request.repo, ["pr", "merge", str(request.number)])
        _append_optional(args, "--method", request.method)
        _append_optional(args, "--subject", request.title)
        _append_optional(args, "--body", request.body)
        args.extend(["--json", "mergedAt,sha"])
        data = _run_json(args, context)
        return github_rpc_pb2.MergePullRequestResponse(
            merged_at=data.get("mergedAt", ""),
            sha=data.get("sha", ""),
        )

    def ListIssues(self, request, context):
        args = _base_args(request.repo, ["issue", "list"])
        _append_optional(args, "--state", request.state)
        _append_optional(args, "--limit", _int_to_str(request.limit))
        args.extend(["--json", "number,title,labels,createdAt"])
        data = _run_json(args, context)
        items = [
            github_rpc_pb2.IssueSummary(
                number=item.get("number", 0),
                title=item.get("title", ""),
                labels=[label.get("name", "") for label in item.get("labels", [])],
                created_at=item.get("createdAt", ""),
            )
            for item in data
        ]
        return github_rpc_pb2.ListIssuesResponse(items=items)

    def CreateIssue(self, request, context):
        args = _base_args(request.repo, ["issue", "create"])
        _append_optional(args, "--title", request.title)
        _append_optional(args, "--body", request.body)
        _extend_repeated(args, "--label", request.labels)
        _extend_repeated(args, "--assignee", request.assignees)
        args.extend(["--json", "number,url"])
        data = _run_json(args, context)
        return github_rpc_pb2.CreateIssueResponse(
            number=data.get("number", 0),
            url=data.get("url", ""),
        )

    def CloseIssue(self, request, context):
        args = _base_args(request.repo, ["issue", "close", str(request.number)])
        args.extend(["--json", "closedAt"])
        data = _run_json(args, context)
        return github_rpc_pb2.CloseIssueResponse(closed_at=data.get("closedAt", ""))

    def ListWorkflowRuns(self, request, context):
        args = _base_args(request.repo, ["run", "list"])
        _append_optional(args, "--limit", _int_to_str(request.limit))
        args.extend(["--json", "databaseId,name,status,conclusion,updatedAt"])
        data = _run_json(args, context)
        items = [
            github_rpc_pb2.WorkflowRunSummary(
                id=item.get("databaseId", 0),
                name=item.get("name", ""),
                status=item.get("status", ""),
                conclusion=item.get("conclusion", ""),
                updated_at=item.get("updatedAt", ""),
            )
            for item in data
        ]
        return github_rpc_pb2.ListWorkflowRunsResponse(items=items)

    def ViewWorkflowRun(self, request, context):
        args = _base_args(request.repo, ["run", "view", str(request.run_id)])
        if request.failed_only:
            args.append("--log-failed")
        args.append("--log")
        result = _run_command(args, context)
        return github_rpc_pb2.ViewWorkflowRunResponse(
            run=github_rpc_pb2.WorkflowRunDetails(
                id=request.run_id,
                name="",
                status="",
                conclusion="",
                log=result.stdout,
            )
        )

    def RerunWorkflowRun(self, request, context):
        args = _base_args(request.repo, ["run", "rerun", str(request.run_id)])
        if request.failed_only:
            args.append("--failed")
        result = _run_command(args, context)
        return github_rpc_pb2.RerunWorkflowRunResponse(requested_at=result.stdout.strip())

    def GitHubApi(self, request, context):
        args = [GH_BIN, "api"]
        args.append(f"repos/{request.repo.owner}/{request.repo.name}/{request.endpoint.lstrip('/')}")
        _append_optional(args, "--method", request.method)
        _append_optional(args, "--input", request.body_json)
        _append_optional(args, "--jq", request.jq_filter)
        if request.cache_one_hour:
            _append_optional(args, "--cache", "1h")
        result = _run_command(args, context)
        return github_rpc_pb2.GitHubApiResponse(
            raw_json=result.stdout,
            filtered=result.stdout,
        )


def _base_args(repo, suffix):
    args = [GH_BIN, "--repo", f"{repo.owner}/{repo.name}"]
    args.extend(suffix)
    return args


def _extend_repeated(args, flag, values: Iterable[str]):
    for value in values:
        if value:
            args.extend([flag, value])


def _append_optional(args, flag, value: str | None):
    if value:
        args.extend([flag, value])


def _int_to_str(value: int) -> str | None:
    return str(value) if value else None


def _run_json(args: Sequence[str], context):
    result = _run_command(args, context)
    try:
        return json.loads(result.stdout) if result.stdout else {}
    except json.JSONDecodeError as exc:
        context.abort(grpc.StatusCode.INTERNAL, f"Invalid JSON from gh: {exc}")


def _run_command(args: Sequence[str], context):
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or "gh returned a non-zero exit code"
        context.abort(grpc.StatusCode.INTERNAL, message)
    return result
