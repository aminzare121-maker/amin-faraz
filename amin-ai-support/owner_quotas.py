"""Owner-managed monthly free allowances + purchased top-up credits.

This is NOT a payment gateway. Payment confirmation happens outside the service.
Only a trusted local administrator may set allowances or add credits after
independently verifying a payment. The public API has no grant endpoint.

Existing keys remain unmetered until their owner explicitly enables a quota;
the existing per-minute abuse limits remain in effect for all scoped keys.
Top-up balances survive monthly rollovers. Monthly free use resets in UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path

TOKEN_ID = re.compile(r"^[a-f0-9]{16}$")
RECEIPT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,95}$")
MAX_GRANT = 1_000_000


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _valid_count(value, name: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_GRANT:
        raise ValueError(f"Invalid {name} count")
    return value


class OwnerQuotas:
    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS support_owner_quotas(
                token_id TEXT PRIMARY KEY,
                month TEXT NOT NULL,
                free_chat INTEGER NOT NULL,
                free_ticket INTEGER NOT NULL,
                used_chat INTEGER NOT NULL DEFAULT 0,
                used_ticket INTEGER NOT NULL DEFAULT 0,
                paid_chat INTEGER NOT NULL DEFAULT 0,
                paid_ticket INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS support_owner_grants(
                receipt_ref TEXT PRIMARY KEY,
                token_id TEXT NOT NULL,
                chat_units INTEGER NOT NULL,
                ticket_units INTEGER NOT NULL,
                verified_by TEXT NOT NULL,
                granted_at TEXT NOT NULL
            )""")

    def connect(self):
        return sqlite3.connect(str(self.path), timeout=20)

    @staticmethod
    def _check_id(token_id: str):
        if not isinstance(token_id, str) or not TOKEN_ID.fullmatch(token_id):
            raise ValueError("Invalid token id")

    def _check_existing_active_token(self, db, token_id: str):
        row = db.execute(
            "SELECT 1 FROM support_scoped_tokens "
            "WHERE token_id=? AND revoked_at=''", (token_id,)).fetchone()
        if row is None:
            raise ValueError("Token does not exist or is revoked")

    @staticmethod
    def _reset_month(db, token_id: str):
        db.execute(
            "UPDATE support_owner_quotas SET month=?, used_chat=0, used_ticket=0 "
            "WHERE token_id=? AND month<>?", (_month(), token_id, _month()))

    def configure(self, token_id: str, free_chat: int, free_ticket: int) -> dict:
        """Trusted local administrator only; no public endpoint."""
        self._check_id(token_id)
        _valid_count(free_chat, "free chat")
        _valid_count(free_ticket, "free ticket")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_existing_active_token(db, token_id)
            self._reset_month(db, token_id)
            db.execute(
                "INSERT INTO support_owner_quotas(token_id, month, free_chat, free_ticket) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(token_id) DO UPDATE SET "
                "free_chat=excluded.free_chat, free_ticket=excluded.free_ticket",
                (token_id, _month(), free_chat, free_ticket))
        return self.status(token_id)

    def grant(self, token_id: str, receipt_ref: str, chat_units: int, ticket_units: int,
              verified_by: str) -> dict:
        """Credit ONLY after trusted administrator checks payment independently.

        A receipt is unique globally, preventing accidental double-crediting.
        This function does not and cannot verify a bank transaction.
        """
        self._check_id(token_id)
        _valid_count(chat_units, "chat grant")
        _valid_count(ticket_units, "ticket grant")
        if chat_units + ticket_units < 1:
            raise ValueError("Empty grant")
        if not isinstance(receipt_ref, str) or not RECEIPT.fullmatch(receipt_ref):
            raise ValueError("Invalid receipt reference")
        if not isinstance(verified_by, str) or not 3 <= len(verified_by.strip()) <= 90:
            raise ValueError("A trusted operator identifier is required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_existing_active_token(db, token_id)
            self._reset_month(db, token_id)
            if not db.execute(
                "SELECT 1 FROM support_owner_quotas WHERE token_id=?", (token_id,)
            ).fetchone():
                raise ValueError("Owner must configure free quota before top-up")
            if db.execute(
                "SELECT 1 FROM support_owner_grants WHERE receipt_ref=?",
                (receipt_ref,)).fetchone():
                raise ValueError("Receipt reference already used; no second credit")
            db.execute(
                "INSERT INTO support_owner_grants VALUES (?,?,?,?,?,?)",
                (receipt_ref, token_id, chat_units, ticket_units,
                 verified_by.strip(), datetime.now(timezone.utc).isoformat()))
            db.execute(
                "UPDATE support_owner_quotas "
                "SET paid_chat=paid_chat+?, paid_ticket=paid_ticket+? "
                "WHERE token_id=?", (chat_units, ticket_units, token_id))
        return self.status(token_id)

    def reserve(self, token_id: str, action: str) -> str:
        """Atomically consume one free or pre-credited paid request.

        Returns: 'unmetered', 'free', 'paid' or 'exhausted'.
        All paid credits are valid until consumed; they never auto-charge.
        """
        self._check_id(token_id)
        if action not in {"chat", "ticket"}:
            raise ValueError("Unknown quota action")
        free_col, used_col, paid_col = (
            ("free_chat", "used_chat", "paid_chat") if action == "chat"
            else ("free_ticket", "used_ticket", "paid_ticket"))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._reset_month(db, token_id)
            row = db.execute(
                f"SELECT {free_col}, {used_col}, {paid_col} "
                "FROM support_owner_quotas WHERE token_id=?",
                (token_id,)).fetchone()
            if row is None:
                return "unmetered"
            free, used, paid = row
            if used < free:
                db.execute(
                    f"UPDATE support_owner_quotas SET {used_col}={used_col}+1 "
                    "WHERE token_id=?", (token_id,))
                return "free"
            if paid:
                db.execute(
                    f"UPDATE support_owner_quotas SET {paid_col}={paid_col}-1 "
                    "WHERE token_id=?", (token_id,))
                return "paid"
            return "exhausted"

    def refund(self, token_id: str, action: str, debit: str):
        """Undo an accepted quota unit on an unexpected failure.

        The caller must invoke this exactly once, and only for a reservation
        it owns. This is not a public refund or payment reversal endpoint.
        """
        if debit not in {"free", "paid"}:
            return
        self._check_id(token_id)
        if action not in {"chat", "ticket"}:
            raise ValueError("Unknown quota action")
        used_col, paid_col = (("used_chat", "paid_chat") if action == "chat"
                              else ("used_ticket", "paid_ticket"))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._reset_month(db, token_id)
            if debit == "free":
                db.execute(
                    f"UPDATE support_owner_quotas SET {used_col}={used_col}-1 "
                    f"WHERE token_id=? AND {used_col}>0", (token_id,))
            else:
                db.execute(
                    f"UPDATE support_owner_quotas SET {paid_col}={paid_col}+1 "
                    "WHERE token_id=?", (token_id,))

    def status(self, token_id: str) -> dict:
        self._check_id(token_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._reset_month(db, token_id)
            row = db.execute(
                "SELECT month,free_chat,free_ticket,used_chat,used_ticket,"
                "paid_chat,paid_ticket FROM support_owner_quotas WHERE token_id=?",
                (token_id,)).fetchone()
        if row is None:
            return {"token_id": token_id, "metered": False}
        month, free_chat, free_ticket, used_chat, used_ticket, paid_chat, paid_ticket = row
        return {"token_id": token_id, "metered": True, "month_utc": month,
                "free_chat_remaining": max(0, free_chat-used_chat),
                "free_ticket_remaining": max(0, free_ticket-used_ticket),
                "paid_chat_remaining": paid_chat, "paid_ticket_remaining": paid_ticket,
                "owner_collects_payment": True, "payment_gateway_connected": False}
