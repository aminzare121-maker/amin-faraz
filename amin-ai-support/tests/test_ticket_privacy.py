"""Regression for support-ticket privacy and reviewer-approved search metadata.

The real customer message is not public. This suite verifies that only a
reviewer-authored, generic issue summary can become a search hint.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from amin_support import SupportEngine
from tickets import TicketStore


class ReviewedResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        config = self.root / "projects.json"
        config.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "الف", "public_paths": [], "source_prefixes": []},
            {"id": "beta", "name": "ب", "public_paths": [], "source_prefixes": []}
        ]}, ensure_ascii=False), encoding="utf-8")
        self.engine = SupportEngine(config, self.root / "kb.sqlite3")

    def test_original_customer_message_is_not_in_public_answers(self):
        secret = "رازخصوصی۹۸۷۶۵"
        ticket = self.engine.tickets.submit(
            "alpha", f"اطلاعات شخصی {secret}؛ مشکل من هنگام اجرا رخ داد", True)
        self.engine.tickets.approve(
            "alpha", ticket,
            "پس از بستن برنامه، نسخه نرم‌افزار را کنترل و آن را دوباره اجرا کنید.",
            "صفحه سفید هنگام باز کردن برنامه")
        answer = self.engine.answer("alpha", "صفحه سفید موقع باز کردن برنامه")
        self.assertTrue(answer["sources"])
        self.assertIn("approved_resolutions/", answer["sources"][0]["path"])
        self.assertIn("نسخه نرم‌افزار", answer["answer"])
        self.assertNotIn(secret, answer["answer"])
        self.assertNotIn(secret, json.dumps(answer, ensure_ascii=False))
        self.assertFalse(self.engine.knowledge.search("alpha", secret))
        self.assertFalse(self.engine.knowledge.search("beta", "صفحه سفید"))

    def test_unapproved_ticket_does_not_become_searchable(self):
        self.engine.tickets.submit("alpha", "ورود کاربر با مشکل تکراری روبه‌رو است", True)
        self.assertFalse(self.engine.knowledge.search("alpha", "ورود کاربر مشکل"))

    def test_old_databases_migrate_without_losing_existing_tickets(self):
        old = self.root / "old.sqlite3"
        with sqlite3.connect(old) as db:
            db.execute("""CREATE TABLE support_tickets(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
                resolution TEXT NOT NULL DEFAULT '',
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL)""")
            db.execute("""INSERT INTO support_tickets
                       VALUES ('old1','alpha','original private text','resolved',
                               'مستند تأییدشده قدیمی',1,'2026-01-01')""")
        store = TicketStore(old)
        self.assertEqual(store.approved("alpha"),
                         [("old1", "", "مستند تأییدشده قدیمی")])
        self.assertTrue(store.approve("alpha", "old1", "نسخه اصلاح شده",
                                      "اشکال خروج از نرم‌افزار"))
        self.assertEqual(store.approved("alpha"),
                         [("old1", "اشکال خروج از نرم‌افزار", "نسخه اصلاح شده")])
        self.assertEqual(len(TicketStore(old).pending("alpha")), 1)

    def test_problem_summary_is_optional_and_length_bounded(self):
        ticket = self.engine.tickets.submit("alpha", "مشکل بی‌نام", True)
        self.assertTrue(self.engine.tickets.approve(
            "alpha", ticket, "راهکار تأییدشده نسخه برنامه"))
        self.assertTrue(self.engine.knowledge.search("alpha", "راهکار تأییدشده"))
        with self.assertRaises(ValueError):
            self.engine.tickets.approve("alpha", ticket, "راهکار", "x" * 501)

    def test_private_ticket_never_used_as_model_evidence(self):
        ticket = self.engine.tickets.submit(
            "alpha", "PRIVATE-USER-KEY-1234 and phone details", True)
        self.engine.tickets.approve(
            "alpha", ticket, "برای رفع مشکل تنظیمات صدای برنامه را بازبینی کنید",
            "قطع شدن صدای برنامه")
        hits = self.engine.knowledge.search("alpha", "قطع شدن صدای برنامه")
        self.assertTrue(hits)
        self.assertNotIn("PRIVATE-USER-KEY-1234", json.dumps(hits))


if __name__ == "__main__":
    unittest.main()
