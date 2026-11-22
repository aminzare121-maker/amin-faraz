"""Private, project-scoped mobile/desktop handoff queue.

Only a reference marker (never user text or an answer) may be published to a
VERIFIED PRIVATE GitHub repository. Public repositories are rejected.
There is no automatic ChatGPT session/API invocation.
A trusted human/agent must read private requests from the owner-hosted engine
and submit a reviewed answer through the local CLI.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

REQUEST_ID = re.compile(r"^[a-f0-9]{32}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HandoffStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS support_handoffs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                requester_key_id TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'answered')),
                answer TEXT NOT NULL DEFAULT '',
                github_issue INTEGER,
                github_state TEXT NOT NULL DEFAULT 'not_configured',
                created_at TEXT NOT NULL,
                answered_at TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS handoffs_project_status "
                       "ON support_handoffs(project_id,status,created_at)")

    def connect(self):
        return sqlite3.connect(str(self.path), timeout=20)

    def submit(self, project: str, requester_key_id: str, question: str, consent: bool) -> str:
        if consent is not True:
            raise ValueError("Explicit handoff consent is required")
        if not isinstance(question, str) or not question.strip() or len(question) > 2500:
            raise ValueError("Handoff question must be 1-2500 characters")
        if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,60}", project):
            raise ValueError("Invalid project")
        if not isinstance(requester_key_id, str) or not re.fullmatch(r"[a-f0-9]{16}|local", requester_key_id):
            raise ValueError("Invalid requester scope")
        ident = uuid4().hex
        with self.connect() as db:
            db.execute(
                "INSERT INTO support_handoffs"
                "(id,project_id,requester_key_id,question,status,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (ident, project, requester_key_id, question.strip(), "pending", now()))
        return ident

    def status(self, project: str, ident: str, requester_key_id: str) -> dict | None:
        if not isinstance(ident, str) or not REQUEST_ID.fullmatch(ident):
            return None
        with self.connect() as db:
            row = db.execute(
                "SELECT status,answer,github_state,github_issue,created_at,answered_at"
                " FROM support_handoffs WHERE id=? AND project_id=? AND requester_key_id=?",
                (ident, project, requester_key_id)).fetchone()
        if row is None:
            return None
        return {"id": ident, "project": project, "status": row[0], "answer": row[1],
                "github_state": row[2], "github_issue": row[3],
                "created_at": row[4], "answered_at": row[5]}

    def pending(self, project: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,project_id,question,github_state,created_at"
                " FROM support_handoffs WHERE project_id=? AND status='pending'"
                " ORDER BY created_at ASC LIMIT 100", (project,)).fetchall()
        return [dict(zip(("id", "project", "question", "github_state", "created_at"), row))
                for row in rows]

    def answer(self, project: str, ident: str, approved_answer: str) -> bool:
        if not isinstance(ident, str) or not REQUEST_ID.fullmatch(ident):
            raise ValueError("Invalid handoff id")
        if not isinstance(approved_answer, str) or not approved_answer.strip() or len(approved_answer) > 4000:
            raise ValueError("Answer must be 1-4000 characters")
        with self.connect() as db:
            changed = db.execute(
                "UPDATE support_handoffs SET status='answered',answer=?,answered_at=?"
                " WHERE project_id=? AND id=? AND status='pending'",
                (approved_answer.strip(), now(), project, ident))
        return changed.rowcount == 1

    def record_issue(self, ident: str, issue_number: int | None, state: str) -> None:
        if state not in {"not_configured", "published", "failed"}:
            raise ValueError("Invalid issue state")
        with self.connect() as db:
            db.execute("UPDATE support_handoffs SET github_issue=?,github_state=? WHERE id=?",
                       (issue_number, state, ident))


def publish_private_marker(store: HandoffStore, request_id: str) -> str:
    """Best-effort GitHub issue. NEVER exports private request body or response.

    Server-only environment variables; no credential in Android or web client.
    If GitHub is unavailable, the request stays safely queued in local SQLite.
    """
    token = os.environ.get("AMIN_HANDOFF_GITHUB_TOKEN", "").strip()
    repo = os.environ.get("AMIN_HANDOFF_GITHUB_REPO", "").strip()
    if not token or not REPOSITORY.fullmatch(repo):
        return "not_configured"
    # Verify the target repository really is PRIVATE before any write.
    # Source code can stay public while each user's transport remains private.
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "User-Agent": "amin-support-handoff/0.2"}
    try:
        check = Request("https://api.github.com/repos/" + repo, headers=headers)
        with urlopen(check, timeout=8) as response:
            repository = json.load(response)
        if repository.get("private") is not True:
            store.record_issue(request_id, None, "failed")
            return "failed"
    except (OSError, ValueError, HTTPError, URLError):
        store.record_issue(request_id, None, "failed")
        return "failed"
    payload = json.dumps({
        "title": "[Amin handoff] " + request_id[:12],
        "body": "AMIN_HANDOFF_MARKER_V1\\n"
                + json.dumps({"request_id": request_id, "private_text_uploaded": False,
                              "state": "pending_owner_review"}, separators=(",", ":")),
    }).encode("utf-8")
    request = Request("https://api.github.com/repos/" + repo + "/issues",
                      data=payload,
                      headers={**headers, "Content-Type": "application/json"},
                      method="POST")
    try:
        with urlopen(request, timeout=8) as response:
            result = json.load(response)
        number = result.get("number")
        if not isinstance(number, int) or number < 1:
            raise ValueError("No GitHub issue number")
        store.record_issue(request_id, number, "published")
        return "published"
    except (OSError, ValueError, HTTPError, URLError):
        store.record_issue(request_id, None, "failed")
        return "failed"
