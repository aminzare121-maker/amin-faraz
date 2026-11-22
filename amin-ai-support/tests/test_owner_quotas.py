"""Real local HTTP and SQLite tests for owner-controlled top-ups.

This is NOT a test payment transaction; only owner-verified offline crediting.
No network payment provider is connected and no price is configured.
"""
import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amin_support import SupportEngine, make_handler


class OwnerQuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cfg = self.root / "projects.json"
        cfg.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "A", "public_paths": [], "source_prefixes": []},
            {"id": "beta", "name": "B", "public_paths": [], "source_prefixes": []},
        ]}), encoding="utf-8")
        self.db = self.root / "store.sqlite3"
        self.engine = SupportEngine(cfg, self.db)
        self.alpha = self.engine.access.issue("alpha", allow_ticket=True)
        self.beta = self.engine.access.issue("beta", allow_ticket=True)
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.engine, "", scoped_only=True))
        t = threading.Thread(target=self.server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def post(self, token: dict, action: str, body: dict | None = None):
        if body is None:
            body = {"project": token["project_id"], "message": "پرسش عمومی"}
            if action == "ticket":
                body["consent"] = True
        req = Request(
            self.base + "/api/" + action,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + token["token"],
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urlopen(req, timeout=4) as response:
                return response.status, json.load(response)
        except HTTPError as failure:
            return failure.code, json.load(failure)

    def test_preserves_existing_clients_until_owner_configures_quota(self):
        self.assertFalse(self.engine.quotas.status(self.alpha["token_id"])["metered"])
        self.assertEqual(self.post(self.alpha, "chat")[0], 200)

    def test_when_free_quota_finishes_only_owner_can_grant_prepaid_units(self):
        token_id = self.alpha["token_id"]
        configured = self.engine.quotas.configure(token_id, free_chat=2, free_ticket=1)
        self.assertTrue(configured["metered"])
        self.assertEqual(configured["free_chat_remaining"], 2)
        self.assertEqual(self.post(self.alpha, "chat")[0], 200)
        self.assertEqual(self.post(self.alpha, "chat")[0], 200)
        status, body = self.post(self.alpha, "chat")
        self.assertEqual(status, 402)
        self.assertFalse(body["payment_gateway_connected"])
        self.assertEqual(self.engine.quotas.status(token_id)["free_chat_remaining"], 0)
        status, body = self.post(self.beta, "chat")
        self.assertEqual(status, 200)
        granted = self.engine.quotas.grant(
            token_id, "operator-confirmed-20261122-001",
            chat_units=3, ticket_units=0, verified_by="owner-admin")
        self.assertEqual(granted["paid_chat_remaining"], 3)
        for _ in range(3):
            self.assertEqual(self.post(self.alpha, "chat")[0], 200)
        self.assertEqual(self.post(self.alpha, "chat")[0], 402)
        self.assertEqual(self.engine.quotas.status(token_id)["paid_chat_remaining"], 0)

    def test_payment_receipt_is_idempotent_and_never_publicly_accepted(self):
        token_id = self.alpha["token_id"]
        self.engine.quotas.configure(token_id, 0, 0)
        self.engine.quotas.grant(
            token_id, "operator-confirmed-receipt-002", 1, 1, "owner-admin")
        with self.assertRaises(ValueError):
            self.engine.quotas.grant(
                token_id, "operator-confirmed-receipt-002", 1000, 0, "owner-admin")
        self.assertEqual(self.engine.quotas.status(token_id)["paid_chat_remaining"], 1)
        self.assertEqual(self.post(self.alpha, "grant-credits", {
            "project": "alpha", "chat_units": 1000000, "payment": "paid"})[0], 404)
        self.assertEqual(self.post(self.alpha, "chat")[0], 200)
        self.assertEqual(self.post(self.alpha, "chat")[0], 402)
        self.assertEqual(self.post(self.alpha, "ticket", {
            "project": "alpha", "message": "مشکل ثبت تیکت",
            "consent": True})[0], 201)
        self.assertEqual(self.post(self.alpha, "ticket", {
            "project": "alpha", "message": "دومین تیکت",
            "consent": True})[0], 402)

    def test_no_credit_for_bad_request_and_invalid_payment_inputs(self):
        tid = self.alpha["token_id"]
        self.engine.quotas.configure(tid, 1, 0)
        self.assertEqual(self.post(self.alpha, "chat", {
            "project": "alpha", "message": ""})[0], 400)
        self.assertEqual(self.engine.quotas.status(tid)["free_chat_remaining"], 1)
        self.assertEqual(self.post(self.alpha, "ticket", {
            "project": "alpha", "message": "مشکل", "consent": False})[0], 400)
        self.assertEqual(self.engine.quotas.status(tid)["free_ticket_remaining"], 0)
        with self.assertRaises(ValueError):
            self.engine.quotas.grant(tid, "fake", 4, 0, "owner")
        with self.assertRaises(ValueError):
            self.engine.quotas.grant(tid, "payment-reference-okay", -1, 0, "owner")
        with self.assertRaises(ValueError):
            self.engine.quotas.grant(tid, "payment-reference-okay", 3, 0, "")
        self.assertEqual(self.engine.quotas.status(tid)["paid_chat_remaining"], 0)

    def test_prepaid_balance_survives_monthly_free_reset(self):
        tid = self.alpha["token_id"]
        self.engine.quotas.configure(tid, 1, 0)
        self.engine.quotas.grant(tid, "operator-confirmed-receipt-003", 2, 0, "owner")
        self.assertEqual(self.post(self.alpha, "chat")[0], 200)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE support_owner_quotas SET month='2000-01' WHERE token_id=?",
                       (tid,))
        state = self.engine.quotas.status(tid)
        self.assertEqual(state["free_chat_remaining"], 1)
        self.assertEqual(state["paid_chat_remaining"], 2)

    def test_cannot_grant_credit_to_revoked_or_nonexistent_key(self):
        self.engine.quotas.configure(self.alpha["token_id"], 1, 1)
        self.assertTrue(self.engine.access.revoke(self.alpha["token_id"]))
        with self.assertRaises(ValueError):
            self.engine.quotas.grant(
                self.alpha["token_id"], "operator-confirmed-receipt-004",
                2, 0, "owner-admin")
        self.assertEqual(self.post(self.alpha, "chat")[0], 401)
        with self.assertRaises(ValueError):
            self.engine.quotas.configure("1234567890abcdef", 4, 0)

    def test_insufficient_quota_has_no_automatic_payment_attempt(self):
        self.engine.quotas.configure(self.alpha["token_id"], 0, 0)
        result = self.post(self.alpha, "chat")
        self.assertEqual(result[0], 402)
        self.assertNotIn("price", json.dumps(result))
        self.assertFalse(result[1]["payment_gateway_connected"])


if __name__ == "__main__":
    unittest.main()
