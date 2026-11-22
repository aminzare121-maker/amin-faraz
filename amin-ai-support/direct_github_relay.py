#!/usr/bin/env python3
"""GitHub private issues relay usable from Windows without running an AI server.

The user's own private repository is the transport, NOT a ChatGPT API.
A connected agent or this user's ChatGPT task can read the issue and publish a
reviewed reply in a comment. Never write the token or message to public repos.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import secrets
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
ID_PATTERN = re.compile(r"[a-f0-9]{32}\Z")
API = "https://api.github.com/repos/"
MAX_BYTES = 256000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubPrivateBridge:
    def __init__(self, repo: str, token: str, opener=None):
        if not isinstance(repo, str) or not REPO_PATTERN.fullmatch(repo) or ".." in repo.split("/"):
            raise ValueError("Repo must be an owner/repo pair")
        if not isinstance(token, str) or not re.fullmatch(
                r"(github_pat_|ghp_|gho_)[A-Za-z0-9_-]{20,240}", token):
            raise ValueError("Restricted GitHub access token is required")
        self.repo, self.token = repo, token
        self.opener = opener or build_opener(NoRedirect())

    def request(self, method: str, path: str, payload: dict | None = None):
        if not path.startswith("/") and path:
            raise ValueError("Invalid API path")
        raw = (json.dumps(payload, ensure_ascii=False).encode("utf8")
               if payload is not None else None)
        if raw is not None and len(raw) > 15000:
            raise ValueError("Request body too large")
        req = Request(API + self.repo + path, method=method, data=raw,
                      headers={"Authorization": "Bearer " + self.token,
                               "Accept": "application/vnd.github+json",
                               "X-GitHub-Api-Version": "2022-11-28",
                               "Content-Type": "application/json",
                               "Cache-Control": "no-store",
                               "User-Agent": "AminPrivateSupport/0.2"})
        try:
            with self.opener.open(req, timeout=20) as response:
                if response.status not in (200, 201):
                    raise RuntimeError("GitHub returned HTTP " + str(response.status))
                content = response.read(MAX_BYTES + 1)
                if len(content) > MAX_BYTES:
                    raise RuntimeError("GitHub response too large")
                return json.loads(content.decode("utf8"))
        except HTTPError as error:
            raise RuntimeError("GitHub access failed (HTTP " + str(error.code) + ")") from None
        except URLError:
            raise RuntimeError("GitHub network unavailable") from None

    def require_private(self):
        repo = self.request("GET", "")
        if repo.get("private") is not True:
            raise RuntimeError("PUBLIC repository refused: private text will not be uploaded")
        if repo.get("full_name", "").casefold() != self.repo.casefold():
            raise RuntimeError("Unexpected GitHub repository identity")
        if not repo.get("has_issues", True):
            raise RuntimeError("Issues disabled")
        return repo

    def submit(self, project: str, message: str, device: str = "windows",
               target_environment: str = "none", requested_operation: str = "answer"):
        if target_environment not in {"none", "android", "windows", "web", "github"}:
            raise ValueError("Invalid destination environment")
        if requested_operation not in {"answer", "build", "repair", "analyze", "release"}:
            raise ValueError("Invalid operation")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,50}", project):
            raise ValueError("Invalid project")
        if not message or len(message) > 2500:
            raise ValueError("Message must have 1-2500 characters")
        self.require_private()
        request_id = secrets.token_hex(16)
        body = "AMIN_CHAT_BRIDGE_V1\n" + json.dumps({
            "request_id": request_id, "project": project, "device": device,
            "question": message.strip(), "consent": True,
            "target_environment": target_environment,
            "requested_operation": requested_operation,
            "execution_authorized": False,
            "result_required": "AMIN_CHAT_REPLY_V1"}, ensure_ascii=False)
        result = self.request("POST", "/issues", {
            "title": "[Amin private support] " + request_id[:12], "body": body})
        issue = result.get("number")
        if not isinstance(issue, int) or issue < 1:
            raise RuntimeError("GitHub did not provide an Issue number")
        return {"request_id": request_id, "issue_number": issue,
                "status": "submitted_to_private_github",
                "chatgpt_invoked": False}

    def status(self, issue: int, request_id: str):
        if issue < 1 or not ID_PATTERN.fullmatch(request_id):
            raise ValueError("Invalid issue or request ID")
        owner = self.require_private().get("owner", {}).get("login", "").casefold()
        original = self.request("GET", f"/issues/{issue}")
        body = original.get("body") or ""
        marker = "AMIN_CHAT_BRIDGE_V1\n"
        if not body.startswith(marker):
            raise RuntimeError("Issue is not an Amin private support request")
        envelope = json.loads(body[len(marker):])
        if envelope.get("request_id") != request_id:
            raise RuntimeError("Request ID mismatch")
        comments = self.request("GET", f"/issues/{issue}/comments?per_page=100")
        for comment in reversed(comments):
            if (comment.get("user") or {}).get("login", "").casefold() not in {owner, "github-actions[bot]"}:
                continue
            raw = comment.get("body") or ""
            reply_marker = "AMIN_CHAT_REPLY_V1\n"
            if not raw.startswith(reply_marker):
                continue
            try:
                reply = json.loads(raw[len(reply_marker):])
            except (ValueError, TypeError):
                continue
            answer = reply.get("answer")
            if reply.get("request_id") != request_id or reply.get("status") != "answered":
                continue
            if not isinstance(answer, str) or not (0 < len(answer) <= 4000):
                continue
            return {"status": "answered", "request_id": request_id,
                    "issue_number": issue, "answer": answer,
                    "needs_human": reply.get("needs_human", True) is not False,
                    "action_performed": reply.get("action_performed") is True,
                    "chatgpt_invoked": reply.get("chatgpt_invoked") is True,
                    "source": reply.get("source", "unverified")}
        return {"status": "pending", "request_id": request_id, "issue_number": issue}

    def approve(self, issue: int, request_id: str, project: str):
        """Explicit user acceptance: private, per-project, no self-training."""
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,50}", project):
            raise ValueError("Invalid project")
        result = self.status(issue, request_id)
        if result["status"] != "answered":
            raise RuntimeError("Only answered requests can be approved")
        original = self.request("GET", f"/issues/{issue}")
        envelope = json.loads(original["body"].split("\n", 1)[1])
        if envelope.get("project") != project:
            raise RuntimeError("Project mismatch")
        previous = self.request("GET", f"/issues/{issue}/comments?per_page=100")
        marker = "AMIN_LESSON_APPROVED_V1\n"
        for comment in previous:
            if ((comment.get("user") or {}).get("login", "").casefold()
                    == self.repo.split("/")[0].casefold()
                    and (comment.get("body") or "").startswith(marker)):
                try:
                    details = json.loads(comment["body"][len(marker):])
                except ValueError:
                    continue
                if details.get("request_id") == request_id and details.get("project") == project:
                    return {"approved": True, "already_approved": True}
        body = marker + json.dumps({"request_id": request_id, "project": project,
                                    "approved": True}, ensure_ascii=False)
        self.request("POST", f"/issues/{issue}/comments", {"body": body})
        return {"approved": True, "already_approved": False}

    def list_requests(self):
        self.require_private()
        result = self.request("GET", "/issues?state=all&per_page=100")
        items = []
        for item in result:
            body = item.get("body") or ""
            if not body.startswith("AMIN_CHAT_BRIDGE_V1\n"):
                continue
            try:
                data = json.loads(body[len("AMIN_CHAT_BRIDGE_V1\n"):])
            except ValueError:
                continue
            ident = data.get("request_id")
            if isinstance(ident, str) and ID_PATTERN.fullmatch(ident):
                items.append({"issue_number": item.get("number"),
                              "request_id": ident, "project": data.get("project"),
                              "created_at": item.get("created_at")})
        return items


def main(argv=None):
    parser = argparse.ArgumentParser(description="Amin private GitHub relay (no paid server)")
    parser.add_argument("--repo", required=True, help="Owner-owned PRIVATE owner/repo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    submit = sub.add_parser("submit")
    submit.add_argument("--project", required=True)
    submit.add_argument("--message", required=True)
    sub.add_parser("list")
    approve = sub.add_parser("approve")
    approve.add_argument("--issue", type=int, required=True)
    approve.add_argument("--id", required=True)
    approve.add_argument("--project", required=True)
    status = sub.add_parser("status")
    status.add_argument("--issue", type=int, required=True)
    status.add_argument("--id", required=True)
    args = parser.parse_args(argv)
    token = os.environ.get("AMIN_PRIVATE_GITHUB_TOKEN", "")
    try:
        bridge = GitHubPrivateBridge(args.repo, token)
        if args.command == "verify": result = {"private": bridge.require_private()["private"]}
        elif args.command == "submit": result = bridge.submit(args.project, args.message)
        elif args.command == "list": result = {"requests": bridge.list_requests()}
        elif args.command == "approve": result = bridge.approve(args.issue, args.id, args.project)
        else: result = bridge.status(args.issue, args.id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, RuntimeError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
