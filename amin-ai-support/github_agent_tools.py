#!/usr/bin/env python3
"""Scoped GitHub *execution* tools for the owner-hosted SIWC ChatGPT agent.

Every job gets a unique branch and an immutable allowlisted repository.
The model never sees PATs, cannot merge/delete branches, and cannot execute
shell commands, deploy, release, or install software. Nothing writes to main.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from urllib.parse import quote
from direct_github_relay import GitHubPrivateBridge, REPO_PATTERN, ID_PATTERN

SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]{1,180}\Z")
REF = re.compile(r"[0-9a-f]{40}\Z", re.I)
FORBIDDEN_PARTS = {
    ".git", ".ssh", ".aws", ".npmrc", ".pypirc", "__pycache__",
    ".env", "id_rsa", "id_ed25519", "credentials", "secrets",
}
MAX_FILE = 8500           # Conservatively fit existing GitHub REST adapter.
MAX_READ = 60000
MAX_FILES = 16
MAX_WRITE_CALLS = 12
MAX_ACTIONS = 30
MAX_MODEL_OUTPUT = 8500
BRANCH_PREFIX = "amin-ai-plan/"


class AgentToolError(RuntimeError):
    pass


def checked_path(path):
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path):
        raise AgentToolError("Invalid repository path")
    if (path.startswith("/") or path.endswith("/") or "//" in path or
            any(part in {".", ".."} for part in path.split("/"))):
        raise AgentToolError("Unsafe path")
    pieces = path.split("/")
    if (any(p.lower() in FORBIDDEN_PARTS or p.lower().startswith(".env")
            for p in pieces) or
        path.startswith(".github/workflows/") or
        path.startswith(".github/actions/") or
        path.startswith(".amin-chatgpt-work/") or
        any(word in path.lower() for word in (".pem", ".p12", ".pfx", ".key", "private_key"))):
        raise AgentToolError("Sensitive or executable policy files are off limits")
    return path


def schema(name, description, props, required):
    return {"type": "function", "name": name, "description": description,
            "parameters": {"type": "object", "properties": props,
                           "required": required, "additionalProperties": False},
            "strict": True}


def tool_namespace(writable):
    s = lambda d: {"type": "string", "description": d}
    available = [
        schema("repository_info", "Inspect the assigned repository and current job branch.",
               {}, []),
        schema("list_files", "List entries of a directory in the assigned repository (not another repo).",
               {"path": s("Relative directory; empty string for repository root.")}, ["path"]),
        schema("read_file", "Read a source file and its GitHub SHA; read before editing.",
               {"path": s("Relative source-file path")}, ["path"]),
        schema("check_ci", "Inspect GitHub Actions runs for the current branch or PR.",
               {}, []),
    ]
    if writable:
        available.extend([
            schema("create_branch", "Create this job's isolated GitHub branch from the default branch.",
                   {}, []),
            schema("write_file", "Create or replace one file on this isolated branch; existing files MUST provide the SHA returned by read_file, new files use empty expected_sha. Never edit main.",
                   {"path": s("Relative file path; no secrets or GitHub workflows."),
                    "content": s("Complete UTF-8 file contents, at most 8500 bytes."),
                    "expected_sha": s("Exact SHA from read_file; empty only for a new file."),
                    "message": s("Short descriptive commit message.")},
                   ["path", "content", "expected_sha", "message"]),
            schema("create_pull_request", "Open a draft Pull Request to the base branch after code changes; never merge it.",
                   {"title": s("Proposed change title, at most 140 characters."),
                    "body": s("Summary of actual changes and still-unverified tests.")},
                   ["title", "body"]),
        ])
    return [{"type": "namespace", "name": "github",
             "description": "Explicitly authorized repository-scoped GitHub code tools. "
                            "No shell, merge, install, deployment or secrets.",
             "tools": available}]


class ScopedGitHubAgent:
    def __init__(self, repository: str, token: str, request_id: str, *,
                 allow_write=False, allow_public=False, bridge=None):
        if not isinstance(repository, str) or not REPO_PATTERN.fullmatch(repository):
            raise AgentToolError("Specify a single valid owner/repository")
        if not isinstance(request_id, str) or not ID_PATTERN.fullmatch(request_id):
            raise AgentToolError("A 128-bit per-job id is required")
        self.bridge = bridge or GitHubPrivateBridge(repository, token)
        self.repository = repository
        self.id = request_id
        self.allow_write = allow_write is True
        self.actions = 0
        self.writes = 0
        self.changed = []
        self.pr_number = None
        self.branch_started = False
        metadata = self._api("GET", "")
        if (metadata.get("full_name", "").casefold() != repository.casefold()):
            raise AgentToolError("GitHub repository does not match the operator allowlist")
        if metadata.get("private") is not True and not allow_public:
            raise AgentToolError("Public repository requires explicit opt-in; private data stays private")
        self.private = metadata.get("private") is True
        self.base = metadata.get("default_branch") or "main"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,75}", self.base):
            raise AgentToolError("Unsupported base branch")
        self.branch = BRANCH_PREFIX + request_id

    def _api(self, method, path, payload=None):
        return self.bridge.request(method, path, payload)

    def _ref(self):
        return self._api("GET", "/git/ref/heads/" + self.branch)["object"]["sha"]

    def _read_raw(self, path, branch):
        path = checked_path(path)
        item = self._api("GET", "/contents/" + quote(path, safe="/") +
                         "?ref=" + quote(branch, safe="/"))
        if item.get("type") != "file" or item.get("encoding") != "base64":
            raise AgentToolError("Path is not a readable text file")
        try:
            data = base64.b64decode(item.get("content", ""), validate=False)
            text = data.decode("utf8")
        except (ValueError, UnicodeError):
            raise AgentToolError("Binary files cannot be edited with this tool") from None
        if len(data) > MAX_READ:
            raise AgentToolError("File exceeds read limit")
        sha = item.get("sha")
        if not isinstance(sha, str) or not REF.fullmatch(sha):
            raise AgentToolError("GitHub content SHA is invalid")
        return {"path": path, "content": text, "sha": sha, "size": len(data)}

    def create_branch(self):
        if not self.allow_write:
            raise AgentToolError("Owner has not authorized source changes")
        if self.branch_started:
            return {"branch": self.branch, "already_created_in_session": True}
        ref = self._api("GET", "/git/ref/heads/" + self.base)
        sha = (ref.get("object") or {}).get("sha")
        if not isinstance(sha, str) or not REF.fullmatch(sha):
            raise AgentToolError("Unable to validate base SHA")
        result = self._api("POST", "/git/refs", {
            "ref": "refs/heads/" + self.branch, "sha": sha})
        if result.get("ref") != "refs/heads/" + self.branch:
            raise AgentToolError("GitHub did not confirm the isolated branch")
        self.branch_started = True
        return {"branch": self.branch, "base": self.base, "base_sha": sha}

    def list_files(self, path=""):
        if path:
            checked_path(path + "/placeholder")
        target = "/contents/" + quote(path, safe="/") if path else "/contents"
        ref = self.branch if self.branch_started else self.base
        result = self._api("GET", target + "?ref=" + quote(ref, safe="/"))
        if not isinstance(result, list):
            raise AgentToolError("Expected directory listing")
        entries = []
        for item in result[:100]:
            p = item.get("path", "")
            try:
                checked_path(p)
            except AgentToolError:
                continue
            if item.get("type") in {"file", "dir"}:
                entries.append({"path": p, "type": item["type"],
                                "size": item.get("size", 0)})
        return {"repository": self.repository, "ref": ref,
                "entries": entries, "truncated": len(result) > 100}

    def read_file(self, path):
        ref = self.branch if self.branch_started else self.base
        result = self._read_raw(path, ref)
        return {"ref": ref, **result}

    def write_file(self, path, content, expected_sha, message):
        if not self.allow_write:
            raise AgentToolError("Owner must authorize write access")
        checked_path(path)
        if (not isinstance(content, str) or not content or
                len(content.encode("utf8")) > MAX_FILE):
            raise AgentToolError("Complete file must be 1-8500 bytes")
        if not isinstance(expected_sha, str) or (
                expected_sha and not REF.fullmatch(expected_sha)):
            raise AgentToolError("Invalid expected content SHA")
        if not isinstance(message, str) or not message.strip() or len(message) > 120:
            raise AgentToolError("Commit message must be 1-120 characters")
        if self.writes >= MAX_WRITE_CALLS or len(set(self.changed)) >= MAX_FILES:
            raise AgentToolError("Write limit reached; review this batch first")
        if not self.branch_started:
            self.create_branch()
        target = "/contents/" + quote(path, safe="/")
        try:
            current = self._read_raw(path, self.branch)
        except RuntimeError as error:
            if "HTTP 404" not in str(error):
                raise
            current = None
        if current is None:
            if expected_sha:
                raise AgentToolError("File does not exist on this branch; cannot replace")
        elif expected_sha != current["sha"]:
            raise AgentToolError("Stale SHA: reread the current branch before editing")
        args = {
            "branch": self.branch,
            "message": message.strip(),
            "content": base64.b64encode(content.encode("utf8")).decode("ascii"),
        }
        if current is not None:
            args["sha"] = current["sha"]
        result = self._api("PUT", target, args)
        commit = (result.get("commit") or {}).get("sha")
        newsha = (result.get("content") or {}).get("sha")
        if not isinstance(commit, str) or not REF.fullmatch(commit):
            raise AgentToolError("GitHub did not confirm file write")
        self.writes += 1
        self.changed.append(path)
        return {"file": path, "branch": self.branch, "commit_sha": commit,
                "content_sha": newsha, "source_changed": True,
                "production_deployed": False, "tests_passed": False}

    def create_pull_request(self, title, body):
        if not self.allow_write:
            raise AgentToolError("User did not approve creating a Pull Request")
        if not self.changed:
            raise AgentToolError("No confirmed changes were written")
        if self.pr_number is not None:
            return {"pr_number": self.pr_number, "already_created": True}
        if (not isinstance(title, str) or not title.strip() or len(title) > 140
                or not isinstance(body, str) or not body.strip() or len(body) > 3000):
            raise AgentToolError("Invalid PR description")
        result = self._api("POST", "/pulls", {
            "title": title.strip(), "body": body.strip(),
            "base": self.base, "head": self.branch, "draft": True})
        number = result.get("number")
        if not isinstance(number, int) or number <= 0:
            raise AgentToolError("GitHub did not confirm Pull Request")
        self.pr_number = number
        return {"pr_number": number, "url": result.get("html_url"),
                "draft": True, "merged": False, "tests_passed": False,
                "repository": self.repository}

    def check_ci(self):
        if not self.branch_started:
            return {"status": "not_started", "tests_passed": False}
        sha = self._ref()
        if not isinstance(sha, str) or not REF.fullmatch(sha):
            raise AgentToolError("GitHub branch does not have a valid head SHA")
        runs = self._api("GET", "/actions/runs?head_sha=" + sha + "&per_page=10")
        items = [
            {"id": r.get("id"), "name": r.get("name"),
             "status": r.get("status"), "conclusion": r.get("conclusion")}
            for r in runs.get("workflow_runs", [])[:10]
        ]
        # No runs != success. A success from one job doesn't certify the whole app.
        success = bool(items) and all(i["status"] == "completed" and
                                      i["conclusion"] == "success" for i in items)
        return {"branch": self.branch, "head_sha": sha, "runs": items,
                "ci_runs_successful": success, "real_device_tested": False}

    def execute(self, name, arguments):
        self.actions += 1
        if self.actions > MAX_ACTIONS:
            raise AgentToolError("Agent tool operation budget exhausted")
        if not isinstance(arguments, dict):
            raise AgentToolError("Tool arguments must be an object")
        # Accept the model's namespaced names but never arbitrary method names.
        op = name.rsplit(".", 1)[-1].rsplit("__", 1)[-1]
        handlers = {
            "repository_info": lambda: {
                "repository": self.repository, "base": self.base,
                "job_branch": self.branch, "private": self.private,
                "write_authorized": self.allow_write,
                "changed_files": list(dict.fromkeys(self.changed)),
                "pr_number": self.pr_number},
            "list_files": lambda: self.list_files(arguments["path"]),
            "read_file": lambda: self.read_file(arguments["path"]),
            "check_ci": self.check_ci,
        }
        if self.allow_write:
            handlers.update({
                "create_branch": self.create_branch,
                "write_file": lambda: self.write_file(
                    arguments["path"], arguments["content"],
                    arguments["expected_sha"], arguments["message"]),
                "create_pull_request": lambda: self.create_pull_request(
                    arguments["title"], arguments["body"]),
            })
        if op not in handlers or not isinstance(name, str) or not (
                name.startswith("github.") or name.startswith("github__") or name in handlers):
            raise AgentToolError("Tool is not on the authorized allowlist")
        try:
            result = handlers[op]()
        except KeyError:
            raise AgentToolError("Missing required tool argument") from None
        return result
