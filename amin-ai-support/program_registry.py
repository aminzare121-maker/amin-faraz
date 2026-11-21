"""Universal software onboarding and controlled, isolated improvement memory.

All writes are trusted local administrator operations. A director_id stored here
is a label, NOT authentication. Do not expose registration/review over the
shared-key public HTTP API. No model finetuning or unsupervised self-modification.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

APP_ID = re.compile(r"^[a-z][a-z0-9_-]{1,50}$")
DIRECTOR_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{2,79}$")
ALLOWED_STYLE = {
    "language": {"fa", "en", "bilingual"},
    "tone": {"direct", "formal", "friendly"},
    "detail": {"short", "balanced", "thorough"},
    "expertise": {"beginner", "intermediate", "expert", "adaptive"},
}
DEFAULT_STYLE = {
    "language": "fa",
    "tone": "direct",
    "detail": "balanced",
    "expertise": "adaptive",
}
STYLE_HINTS = {
    "language": {"fa": "به فارسی پاسخ بده.", "en": "Answer in English.",
                 "bilingual": "به فارسی پاسخ بده و اصطلاحات تخصصی مهم را انگلیسی هم ذکر کن."},
    "tone": {"direct": "صریح و نتیجه‌محور باش.", "formal": "لحن رسمی و حرفه‌ای داشته باش.",
             "friendly": "با لحن دوستانه و محترمانه بنویس."},
    "detail": {"short": "مختصر پاسخ بده.", "balanced": "توضیح به اندازه نیاز بده.",
               "thorough": "در حد شواهد، توضیح مرحله‌به‌مرحله و کامل بده."},
    "expertise": {"beginner": "اصطلاحات تخصصی را برای مبتدی توضیح بده.",
                  "intermediate": "سطح توضیح را متوسط نگه دار.",
                  "expert": "واژگان فنی دقیق برای متخصص به‌کار ببر.",
                  "adaptive": "سطح توضیح را با سؤال و تجربه مخاطب تطبیق بده."},
}


def checked_style(style: dict) -> dict:
    if not isinstance(style, dict) or set(style) != set(ALLOWED_STYLE):
        raise ValueError("Style requires exactly: language, tone, detail, expertise")
    if any(style[key] not in values for key, values in ALLOWED_STYLE.items()):
        raise ValueError("Unsupported style option")
    return dict(style)


def style_instructions(style: dict) -> str:
    style = checked_style(style)
    # A fixed vocabulary prevents arbitrary stored text becoming system instructions.
    return " ".join(STYLE_HINTS[key][style[key]] for key in ALLOWED_STYLE)


def _reasonable_text(value: str, minimum: int, maximum: int, label: str) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{label} length must be {minimum}-{maximum}")
    if "\x00" in value:
        raise ValueError("Invalid input")
    return value.strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProgramStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS onboarded_programs(
                program_id TEXT PRIMARY KEY,
                program_name TEXT NOT NULL,
                director_id TEXT NOT NULL,
                director_label TEXT NOT NULL,
                style_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS learning_feedback(
                feedback_id TEXT PRIMARY KEY,
                program_id TEXT NOT NULL,
                private_observation TEXT NOT NULL,
                consent INTEGER NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                reviewed_problem TEXT NOT NULL DEFAULT '',
                reviewed_solution TEXT NOT NULL DEFAULT '',
                visibility TEXT NOT NULL DEFAULT 'developer',
                created_at TEXT NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(program_id) REFERENCES onboarded_programs(program_id)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS learning_scope ON learning_feedback(program_id, state, visibility)")
            db.execute("""CREATE TABLE IF NOT EXISTS program_style_events(
                event_id TEXT PRIMARY KEY, program_id TEXT NOT NULL,
                previous_json TEXT NOT NULL, new_json TEXT NOT NULL,
                changed_at TEXT NOT NULL
            )""")

    def connect(self):
        return sqlite3.connect(str(self.db_path), timeout=20)

    def programs(self) -> dict[str, dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT program_id,program_name,director_id,director_label,style_json "
                "FROM onboarded_programs ORDER BY program_id").fetchall()
        # An onboarding record does not grant access to any repository or private docs.
        return {
            ident: {"id": ident, "name": name, "director_id": director,
                    "director_label": label, "style": json.loads(style),
                    "source_prefixes": [], "public_paths": [], "registered": True}
            for ident, name, director, label, style in rows
        }

    def register(self, program_id: str, name: str, director_id: str,
                 director_label: str, style: dict | None = None) -> dict:
        if not isinstance(program_id, str) or not APP_ID.fullmatch(program_id):
            raise ValueError("Unsafe application id")
        if not isinstance(director_id, str) or not DIRECTOR_ID.fullmatch(director_id):
            raise ValueError("Unsafe director id")
        name = _reasonable_text(name, 3, 120, "Program name")
        director_label = _reasonable_text(director_label, 2, 100, "Director label")
        style = checked_style(style if style is not None else DEFAULT_STYLE)
        with self.connect() as db:
            db.execute(
                "INSERT INTO onboarded_programs VALUES (?,?,?,?,?,?)",
                (program_id, name, director_id, director_label,
                 json.dumps(style, ensure_ascii=False), _utc_now()))
        return self.programs()[program_id]

    def update_style(self, program_id: str, director_id: str, style: dict) -> dict:
        style = checked_style(style)
        with self.connect() as db:
            row = db.execute("SELECT director_id,style_json FROM onboarded_programs "
                             "WHERE program_id=?", (program_id,)).fetchone()
            if row is None or row[0] != director_id:
                raise ValueError("Program/director mismatch; trusted administrator required")
            current = json.loads(row[1])
            if current != style:
                new_json = json.dumps(style, ensure_ascii=False)
                db.execute("UPDATE onboarded_programs SET style_json=? WHERE program_id=?",
                           (new_json, program_id))
                db.execute("INSERT INTO program_style_events VALUES (?,?,?,?,?)",
                           (uuid4().hex, program_id, row[1], new_json, _utc_now()))
        return self.programs()[program_id]["style"]

    def propose(self, program_id: str, observation: str, consent: bool, scrub) -> str:
        if consent is not True:
            raise ValueError("Consent required for storing feedback")
        if program_id not in self.programs():
            raise ValueError("Unknown onboarded program")
        observation = _reasonable_text(observation, 5, 2000, "Observation")
        feedback_id = uuid4().hex
        with self.connect() as db:
            db.execute(
                "INSERT INTO learning_feedback(feedback_id,program_id,private_observation,consent,created_at) "
                "VALUES (?,?,?,?,?)",
                (feedback_id, program_id, scrub(observation), 1, _utc_now()))
        return feedback_id

    def pending(self, program_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT feedback_id,private_observation,created_at FROM learning_feedback "
                "WHERE program_id=? AND state='pending' ORDER BY created_at DESC LIMIT 100",
                (program_id,)).fetchall()
        return [{"id": fid, "observation": note, "created_at": at}
                for fid, note, at in rows]

    def approve(self, program_id: str, director_id: str, feedback_id: str,
                public_problem: str, solution: str, visibility: str, scrub) -> bool:
        if visibility not in {"public", "developer"}:
            raise ValueError("Unknown visibility")
        public_problem = _reasonable_text(public_problem, 5, 500, "Reviewed problem")
        solution = _reasonable_text(solution, 5, 2400, "Reviewed solution")
        if not isinstance(feedback_id, str) or not re.fullmatch(r"[a-f0-9]{32}", feedback_id):
            raise ValueError("Invalid feedback id")
        # Reject redacted secrets: they are not suitable as public knowledge.
        if scrub(public_problem) != public_problem or scrub(solution) != solution:
            raise ValueError("Reviewed knowledge contains a recognized secret")
        with self.connect() as db:
            row = db.execute(
                "SELECT director_id FROM onboarded_programs WHERE program_id=?",
                (program_id,)).fetchone()
            if row is None or row[0] != director_id:
                raise ValueError("Program/director mismatch")
            cursor = db.execute(
                "UPDATE learning_feedback SET state='approved', reviewed_problem=?, "
                "reviewed_solution=?, visibility=?, reviewed_at=? "
                "WHERE feedback_id=? AND program_id=? AND state='pending'",
                (public_problem, solution, visibility, _utc_now(),
                 feedback_id, program_id))
        return cursor.rowcount == 1

    def reviewed(self, program_id: str, role: str = "customer") -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT feedback_id,reviewed_problem,reviewed_solution,visibility "
                "FROM learning_feedback WHERE program_id=? AND state='approved'"
                + (" AND visibility='public'" if role != "developer" else "")
                + " ORDER BY reviewed_at DESC LIMIT 100", (program_id,)).fetchall()
        return [{"id": fid, "problem": problem, "solution": solution,
                 "visibility": visibility} for fid, problem, solution, visibility in rows]

    def stats(self, program_id: str) -> dict:
        with self.connect() as db:
            rows = db.execute(
                "SELECT state, COUNT(*) FROM learning_feedback WHERE program_id=? "
                "GROUP BY state", (program_id,)).fetchall()
        states = dict(rows)
        return {"program_id": program_id, "pending": states.get("pending", 0),
                "approved": states.get("approved", 0),
                "not_a_training_metric": True}
