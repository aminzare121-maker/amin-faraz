import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amin_support import (Knowledge, SupportEngine, classify_issue, diagnose_source,
                          load_projects, make_handler, normalize, permitted_path, scrub)


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "README.md").write_text(
            "راهنمای پروژه: خطای اتصال هنگام راه‌اندازی نسخه آزمایشی. "
            "برای اتصال MT5 باید اتصال شبکه را بررسی کرد.", encoding="utf-8")
        (self.source / "private.py").write_text(
            "INTERNAL_MECHANISM = 'NEVER_SHOW_CUSTOMER'\n", encoding="utf-8")
        (self.source / ".env").write_text(
            "api_key=topsecret", encoding="utf-8")
        self.config = self.root / "projects.json"
        self.config.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "پروژه الف", "source_prefixes": ["."],
             "public_paths": ["README.md"]},
            {"id": "beta", "name": "پروژه ب", "source_prefixes": ["."],
             "public_paths": []}
        ]}, ensure_ascii=False), encoding="utf-8")
        self.engine = SupportEngine(self.config, self.root / "test.sqlite3")

    def test_project_isolation_and_public_scope(self):
        r = self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        self.assertEqual(r["files"], 2)
        self.assertEqual(r["public_passages"], 1)
        alpha = self.engine.knowledge.search("alpha", "اتصال", "customer")
        beta = self.engine.knowledge.search("beta", "اتصال", "customer")
        self.assertTrue(alpha)
        self.assertEqual(beta, [])
        self.assertEqual(self.engine.knowledge.search(
            "alpha", "NEVER_SHOW_CUSTOMER", "customer"), [])
        dev = self.engine.knowledge.search(
            "alpha", "NEVER_SHOW_CUSTOMER", "developer")
        self.assertTrue(dev)
        self.assertTrue(all(x["visibility"] == "developer" for x in dev))
        self.assertNotIn("topsecret", json.dumps(dev))

    def test_unknown_question_requires_human(self):
        self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        r = self.engine.answer("alpha", "سؤالی کاملاً نامرتبط درباره ماهواره")
        self.assertTrue(r["needs_human"])
        self.assertEqual(r["sources"], [])
        self.assertFalse(r["model_used"])

    def test_answer_has_real_project_sources(self):
        self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        r = self.engine.answer("alpha", "خطای اتصال MT5")
        self.assertFalse(r["needs_human"])
        self.assertEqual(r["sources"][0]["path"], "README.md")
        self.assertIn("اتصال", r["answer"])

    def test_secret_scrub_and_safe_config(self):
        self.assertEqual(scrub("password: abc123\nhello"), "[REDACTED]\nhello")
        self.assertFalse(permitted_path("private.py", ["README.md"]))
        self.assertTrue(permitted_path("docs/help.md", ["docs"]))
        self.assertEqual(normalize("كی يک"), "کی یک")
        self.assertIn("سرویس", classify_issue("connection refused"))

    def test_readonly_diagnostic(self):
        (self.source / "broken.py").write_text("def nope(:\n", encoding="utf-8")
        report = diagnose_source(self.engine.projects["alpha"], self.source)
        self.assertEqual(report["python_files_checked"], 2)
        self.assertEqual(len(report["syntax_issues"]), 1)
        self.assertEqual(report["syntax_issues"][0]["file"], "broken.py")
        self.assertIn("no execution", report["scope"])

    def test_api_requires_key_and_no_public_developer_role(self):
        self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.engine, "only-test-key"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/health", timeout=2) as response:
            self.assertEqual(json.load(response)["status"], "running")
        with self.assertRaises(HTTPError) as err:
            urlopen(base + "/api/projects", timeout=2)
        self.assertEqual(err.exception.code, 401)
        payload = json.dumps({"project": "alpha", "message": "NEVER_SHOW_CUSTOMER",
                              "role": "developer"}).encode()
        request = Request(base + "/api/chat", data=payload, headers={
            "Authorization": "Bearer only-test-key",
            "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=2) as response:
            data = json.load(response)
        self.assertTrue(data["needs_human"])
        self.assertNotIn("NEVER_SHOW_CUSTOMER", data["answer"])
        self.assertEqual(data["role"], "customer")

    def test_reindex_removes_stale_passages(self):
        self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        (self.source / "README.md").unlink()
        self.engine.knowledge.ingest(self.engine.projects["alpha"], self.source)
        self.assertEqual(self.engine.knowledge.count("alpha", True), 0)

    def test_project_ids_validated(self):
        bad = self.root / "bad.json"
        bad.write_text('{"projects":[{"id":"../../bad"}]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_projects(bad)


if __name__ == "__main__":
    unittest.main()
