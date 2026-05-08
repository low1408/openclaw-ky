---
name: github
description: "Use structured RPC intents for GitHub issues, PRs, CI/logs, comments, reviews, releases, and API queries."
metadata: { "openclaw": { "emoji": "🐙" } }
---

# GitHub Skill (RPC)

Use structured intents and gRPC responses. The agent never emits shell commands and never assumes local binaries.

## When to Use

- Checking PR status, reviews, or merge readiness
- Viewing CI/workflow run status and logs
- Creating, closing, or commenting on issues
- Creating or merging pull requests
- Querying GitHub API for repository data
- Listing repos, releases, or collaborators

## When NOT to Use

- Local git operations (commit, push, pull, branch)
- Non-GitHub repos (GitLab, Bitbucket, self-hosted)
- Cloning repositories
- Reviewing actual code changes (use coding-agent)
- Complex multi-file diffs (use coding-agent or read files)

## RPC Model

Container A (the agent) emits intent messages only. It waits for the gRPC response and then proceeds.

Container B receives the Protobuf request and maps it to a binary invocation using an array-based execve call. Example mapping for CreatePullRequestRequest:

["/usr/bin/gh", "pr", "create", "--title", request.title, "--body", request.body, "--base", request.base_branch, "--head", request.head_branch]

## Strict Typing

- The agent generates data, not code.
- Field values are literal strings or typed values and are never interpreted as shell input.
- Any metacharacters included in fields (for example $(), |, >) are treated as literal text.

## Available Intents

### Pull Requests

- ListPullRequestsRequest
- ViewPullRequestRequest
- CheckPullRequestRequest
- CreatePullRequestRequest
- MergePullRequestRequest

### Issues

- ListIssuesRequest
- CreateIssueRequest
- CloseIssueRequest

### CI and Workflow Runs

- ListWorkflowRunsRequest
- ViewWorkflowRunRequest
- RerunWorkflowRunRequest

### API Queries

- GitHubApiRequest

## Protobuf Definition

See the RPC schema in skills/github/github_rpc.proto.
