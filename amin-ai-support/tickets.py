"""Project-isolated support tickets and administrator-reviewed solutions."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


class TicketStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS support_tickets(
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                resolution TEXT NOT NULL DEFAULT '',
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS tickets_project ON support_tickets(project_id, status)")

    def _connect(self):
        return sqlite3.connect(str(self.db_path), timeout=20)

    def submit(self, project_id: str, message: str, consent: bool) -> str:
        if consent is not True:
            raise ValueError("Explicit consent is required for ticket storage")
        if not isinstance(message, str) or not message.strip() or len(message) > 2500:
            raise ValueError("Ticket message must contain 1-2500 characters")
        ticket_id = uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO support_tickets(id,project_id,message,created_at) VALUES (?,?,?,?)",
                       (ticket_id, project_id, message.strip(),
                        datetime.now(timezone.utc).isoformat()))
        return ticket_id

    def pending(self, project_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,project_id,message,status,created_at FROM support_tickets "
                "WHERE project_id=? ORDER BY created_at DESC LIMIT 100", (project_id,)).fetchall()
        return [dict(zip(("id", "project", "message", "status", "created_at"), row))
                for row in rows]

    def approve(self, project_id: str, ticket_id: str, resolution: str) -> bool:
        if not isinstance(resolution, str) or not resolution.strip() or len(resolution) > 4000:
            raise ValueError("Resolution must contain 1-4000 characters")
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE support_tickets SET resolution=?, status='resolved', approved=1 "
                "WHERE id=? AND project_id=?",
                (resolution.strip(), ticket_id, project_id))
        return cursor.rowcount == 1

    def approved(self, project_id: str) -> list[tuple]:
        with self._connect() as db:
            return db.execute(
                "SELECT id,resolution FROM support_tickets WHERE project_id=? AND approved=1",
                (project_id,)).fetchall()
