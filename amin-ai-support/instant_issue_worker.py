#!/usr/bin/env python3
"""Event-driven private GitHub Issue response. NO ChatGPT session is invoked.

Run by GitHub Actions on the 'issues.opened' event. Uses public, approved project
documentation for a fast evidence-only first response; no paid model or secret
AI service. If there is insufficient evidence the result is marked unresolved.
Never runs issue text as code or treats it as privileged instructions.
"""
from __future__ import annotations
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MARKER = "AMIN_CHAT_BRIDGE_V1\n"
REPLY = "AMIN_CHAT_REPLY_V1\n"
REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
PROJECT = re.compile(r"^[a-z][a-z0-9_-]{1,50}$")
ISSUE_TITLE = re.compile(r"^\[Amin private support\] [a-f0-9]{12}$")


def inspect_event(event: dict, expected_repo: str) -> tuple[dict, int] | None:
    """Validate trusted GitHub envelope, not just arbitrary JSON from Issue."""
    if not isinstance(event, dict) or event.get("action") != "opened":
        return None
    repository = event.get("repository") or {}
    if repository.get("private") is not True or repository.get("full_name") != expected_repo:
        return None
    owner = ((repository.get("owner") or {}).get("login") or "")
    issue = event.get("issue") or {}
    if not isinstance(issue.get("number"), int) or issue["number"] < 1 or issue.get("pull_request"):
        return None
    if (issue.get("user") or {}).get("login", "").casefold() != owner.casefold():
        return None
    if not ISSUE_TITLE.fullmatch(issue.get("title") or ""):
        return None
    body = issue.get("body") or ""
    if not body.startswith(MARKER) or len(body) > 12000:
        return None
    try:
        request = json.loads(body[len(MARKER):])
    except (ValueError, TypeError):
        return None
    if not isinstance(request, dict):
        return None
    ident = request.get("request_id")
    question = request.get("question")
    project = request.get("project")
    if (not isinstance(ident, str) or not REQUEST_ID.fullmatch(ident)
            or not issue["title"].endswith(ident[:12])
            or not isinstance(project, str) or not PROJECT.fullmatch(project)
            or not isinstance(question, str) or not question.strip()
            or len(question) > 2500 or request.get("consent") is not True
            or request.get("result_required") != "AMIN_CHAT_REPLY_V1"):
        return None
    return request, issue["number"]


def safe_api(opener, repo: str, token: str, path: str, payload=None):
    """Only GitHub's verified fixed-host REST API. No redirects, no URL from Issue."""
    import urllib.request
    data = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    url = "https://api.github.com/repos/" + repo + path
    req = Request(url, method="POST" if data is not None else "GET", data=data,
                  headers={"Authorization": "Bearer " + token,
                           "Accept": "application/vnd.github+json",
                           "X-GitHub-Api-Version": "2022-11-28",
                           "Content-Type": "application/json",
                           "User-Agent": "amin-on-demand-reply/1.0"})
    with opener.open(req, timeout=20) as res:
        if res.status not in (200, 201):
            raise RuntimeError("Invalid GitHub response status")
        raw = res.read(256001)
        if len(raw) > 256000:
            raise RuntimeError("GitHub response too large")
        return json.loads(raw.decode("utf-8"))


def build_reply(question: str, project: str, source: Path) -> dict:
    """Use local knowledge only. Explicitly mark model and execution as absent."""
    from amin_support import SupportEngine
    import tempfile
    with tempfile.TemporaryDirectory(prefix="amin-on-demand-") as tempdir:
        base_config = source / "amin-ai-support" / "projects.json"
        config = json.loads(base_config.read_text(encoding="utf-8"))
        if project == "support":
            paths = ["amin-ai-support/README_FA.md",
                     "amin-ai-support/OWNER_REQUIREMENTS_FA.md",
                     "amin-ai-support/HANDOFF_PRIVATE_BRIDGE_FA.md",
                     "amin-ai-support/DIRECT_PRIVATE_GITHUB_CHAT_FA.md"]
            config["projects"].append({
                "id": "support", "name": "هوش امین",
                "source_prefixes": paths, "public_paths": paths
            })
        cfg = Path(tempdir) / "projects.json"
        cfg.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        engine = SupportEngine(cfg, Path(tempdir) / "kb.sqlite3")
        if project not in engine.projects:
            return {"answer": "شناسه نرم‌افزار در دانش تأییدشده ثبت نشده است. "
                              "برای بررسی باید مدیر آن نرم‌افزار را ثبت و منابعش را معرفی کند.",
                    "needs_human": True, "sources": []}
        engine.knowledge.ingest(engine.projects[project], source)
        response = engine.answer(project, question, external_consent=False)
        return {"answer": response["answer"], "needs_human": response["needs_human"],
                "sources": response["sources"]}


def process(event: dict, repo: str, token: str, source: Path, opener) -> dict:
    req = inspect_event(event, repo)
    if req is None:
        return {"processed": False, "reason": "untrusted_or_invalid"}
    request, issue = req
    info = safe_api(opener, repo, token, "")
    if info.get("private") is not True or info.get("full_name") != repo:
        return {"processed": False, "reason": "repo_not_private"}
    comments = safe_api(opener, repo, token, f"/issues/{issue}/comments?per_page=100")
    for comment in comments:
        body = comment.get("body") or ""
        if not body.startswith(REPLY):
            continue
        try:
            payload = json.loads(body[len(REPLY):])
        except (TypeError, ValueError):
            continue
        if payload.get("request_id") == request["request_id"]:
            return {"processed": False, "reason": "already_replied"}
    result = build_reply(request["question"], request["project"], source)
    answer = result["answer"]
    if len(answer) > 3600:
        answer = answer[:3570] + "..."
    note = ("\n\nاین پاسخ بر پایه مستندات موجود و بدون استفاده از مدل ChatGPT تولید شد؛ "
            "هیچ تغییر اجرایی روی دستگاه یا پروژه انجام نشد.")
    if result["needs_human"]:
        note += " مسئله هنوز نیازمند رسیدگی عامل هوشمند یا مسئول نرم‌افزار است."
    reply = {
        "request_id": request["request_id"],
        "status": "answered",
        "answer": answer + note,
        "needs_human": bool(result["needs_human"]),
        "source": "github_actions_document_retrieval",
        "chatgpt_invoked": False,
        "action_performed": False,
        "sources": result["sources"][:4]
    }
    safe_api(opener, repo, token, f"/issues/{issue}/comments",
             {"body": REPLY + json.dumps(reply, ensure_ascii=False, separators=(",", ":"))})
    return {"processed": True, "issue": issue, "needs_human": reply["needs_human"],
            "chatgpt_invoked": False}


def main():
    import urllib.request
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    source = Path(os.environ.get("AMIN_SOURCE", ".")).resolve()
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    # Keep OAuth token, question and response out of logs.
    out = process(event, repo, token, source, urllib.request.build_opener(
        urllib.request.HTTPHandler(), urllib.request.HTTPSHandler()))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
