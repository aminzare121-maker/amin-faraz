#!/usr/bin/env python3
"""Prepare a PRIVATE GitHub pull-request event for ChatGPT Work, never Codex.

This only creates the supported event that ChatGPT Work *can* observe.
It does not authenticate to ChatGPT, invoke a model, or activate a Work task.
The user must explicitly configure an event-triggered GitHub task in ChatGPT
Work and authorize the same private repo. No OpenAI API credentials or charges.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.parse import quote
from direct_github_relay import GitHubPrivateBridge, ID_PATTERN

MARKER = "AMIN_CHAT_BRIDGE_V1\n"
TITLE = "[Amin ChatGPT Work] "
DEFAULT_BRANCH = re.compile(r"[A-Za-z0-9_./-]{1,100}\Z")


def prepare_work_event(bridge: GitHubPrivateBridge, issue: int, request_id: str) -> dict:
    if not isinstance(issue, int) or issue <= 0 or not isinstance(request_id, str) or not ID_PATTERN.fullmatch(request_id):
        raise ValueError("Invalid private request reference")
    repo = bridge.require_private()
    owner = (repo.get("owner") or {}).get("login", "")
    if not owner or not isinstance(owner, str):
        raise RuntimeError("Private repo owner is unknown")
    original = bridge.request("GET", f"/issues/{issue}")
    body = original.get("body") or ""
    if (original.get("pull_request") or not body.startswith(MARKER)
            or (original.get("user") or {}).get("login", "").casefold() != owner.casefold()):
        raise RuntimeError("Only an owner-authored private Amin Issue can trigger ChatGPT Work")
    try:
        request = json.loads(body[len(MARKER):])
    except (TypeError, ValueError):
        raise RuntimeError("Invalid private request envelope") from None
    if (request.get("request_id") != request_id or request.get("consent") is not True
            or request.get("test_only") is True):
        raise RuntimeError("Request mismatch or user consent absent")
    project = request.get("project")
    if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,50}", project):
        raise RuntimeError("Invalid program scope")
    base = repo.get("default_branch", "main")
    if (not isinstance(base, str) or not DEFAULT_BRANCH.fullmatch(base)
            or base.startswith(".") or base.startswith("/") or ".." in base
            or "//" in base):
        raise RuntimeError("Unsafe default branch name")
    head = f"amin-chatgpt-work/{request_id}"
    base_ref = bridge.request("GET", "/git/ref/heads/" + quote(base, safe="/"))
    sha = (base_ref.get("object") or {}).get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise RuntimeError("Cannot verify base commit SHA")
    # No private question in code commits or PR diff; only the private Issue holds it.
    marker = {"protocol": "AMIN_CHATGPT_WORK_PR_V1", "request_id": request_id,
              "issue_number": issue, "project": project, "consent": True,
              "personal_chatgpt_invoked": False, "execution_authorized": False}
    bridge.request("POST", "/git/refs", {"ref": "refs/heads/" + head, "sha": sha})
    path = f".amin-chatgpt-work/requests/{request_id}.json"
    bridge.request("PUT", "/contents/" + path, {
        "message": "chore: request private ChatGPT Work review " + request_id[:12],
        "branch": head,
        "content": base64.b64encode(
            (json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        ).decode("ascii")})
    created = bridge.request("POST", "/pulls", {
        "title": TITLE + request_id[:12],
        "body": ("AMIN_CHATGPT_WORK_PR_V1\n"
                 + json.dumps({"request_id": request_id, "issue_number": issue,
                               "project": project, "question_location": "private_issue",
                               "permission": "read_and_respond_only",
                               "execution_authorized": False}, ensure_ascii=False)),
        "base": base, "head": head, "draft": False})
    number = created.get("number")
    if not isinstance(number, int) or number < 1:
        raise RuntimeError("GitHub did not return a Pull Request number")
    return {
        "issue_number": issue, "request_id": request_id, "pull_request_number": number,
        "private_pr_event_created": True, "chatgpt_invoked": False,
        "chatgpt_task_configured": False, "reply_delivered": False,
        "execution_authorized": False,
    }
