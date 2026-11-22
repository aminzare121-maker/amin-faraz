"""Restricted customer API credentials per software program.

Only trusted local CLI may issue/revoke credentials. Secrets are generated with
the OS CSPRNG and never stored in plaintext. A program-scoped bearer key
authenticates a *program*, not a human user or its director. Production user
identity, audit of individual staff, rate limiting and TLS termination remain
separate acceptance requirements.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


TOKEN_ID = re.compile(r"^[a-f0-9]{16}$")
PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,60}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScopedAccess:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS support_scoped_tokens(
                token_id TEXT PRIMARY KEY,
                digest TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                allow_ticket INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS tokens_project ON support_scoped_tokens(project_id, revoked_at)")

    def connect(self):
        return sqlite3.connect(str(self.path), timeout=20)

    def issue(self, project_id: str, allow_ticket: bool = False) -> dict:
        if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
            raise ValueError("Unsafe project id")
        if type(allow_ticket) is not bool:
            raise ValueError("allow_ticket must be boolean")
        # 32 bytes of entropy; a plain SHA-256 digest is sufficient for a
        # high-entropy bearer value, unlike for user-chosen passwords.
        secret = "amin_" + secrets.token_urlsafe(32)
        token_id = secrets.token_hex(8)
        digest = hashlib.sha256(secret.encode("ascii")).hexdigest()
        with self.connect() as db:
            db.execute(
                "INSERT INTO support_scoped_tokens VALUES (?,?,?,?,?,?)",
                (token_id, digest, project_id, int(allow_ticket), _now(), ""))
        # Caller must show this secret once. No API endpoint can create it.
        return {"token": secret, "token_id": token_id, "project_id": project_id,
                "allow_ticket": allow_ticket, "warning": "Copy once: token is not stored in plaintext"}

    def verify(self, token: str) -> dict | None:
        if not isinstance(token, str) or len(token) > 180 or not token.startswith("amin_"):
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT token_id,project_id,allow_ticket FROM support_scoped_tokens "
                "WHERE digest=? AND revoked_at=''", (digest,)).fetchone()
        if not row:
            return None
        return {"token_id": row[0], "project_id": row[1],
                "allow_ticket": bool(row[2]), "kind": "scoped"}

    def revoke(self, token_id: str) -> bool:
        if not isinstance(token_id, str) or not TOKEN_ID.fullmatch(token_id):
            raise ValueError("Invalid token id")
        with self.connect() as db:
            cur = db.execute(
                "UPDATE support_scoped_tokens SET revoked_at=? "
                "WHERE token_id=? AND revoked_at=''", (_now(), token_id))
        return cur.rowcount == 1

    def list(self, project_id: str | None = None) -> list[dict]:
        if project_id is not None and (not isinstance(project_id, str)
                                       or not PROJECT_ID.fullmatch(project_id)):
            raise ValueError("Invalid project id")
        with self.connect() as db:
            rows = db.execute(
                "SELECT token_id,project_id,allow_ticket,created_at,revoked_at "
                "FROM support_scoped_tokens"
                + (" WHERE project_id=?" if project_id else "")
                + " ORDER BY created_at, token_id",
                (project_id,) if project_id else (),
            ).fetchall()
        return [{"token_id": tid, "project_id": pid, "allow_ticket": bool(t),
                 "created_at": created, "revoked": bool(revoked)}
                for tid, pid, t, created, revoked in rows]

    def active_count(self) -> int:
        with self.connect() as db:
            return db.execute(
                "SELECT COUNT(*) FROM support_scoped_tokens WHERE revoked_at=''").fetchone()[0]
