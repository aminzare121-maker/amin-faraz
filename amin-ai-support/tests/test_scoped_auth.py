"""HTTP integration tests for revocable, project-scoped customer credentials.

These exercise the real local HTTP handler, not only mocked authorization.
They do not prove internet-facing TLS, user identity or production deployment.
"""
import io
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amin_support import SupportEngine, main, make_handler


class ProjectScopedHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "projects.json"
        self.db = self.root / "support.sqlite3"
        self.config.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "Software Alpha", "source_prefixes": ["docs"],
             "public_paths": ["docs/alpha.md"]},
            {"id": "beta", "name": "Software Beta", "source_prefixes": ["docs"],
             "public_paths": ["docs/beta.md"]},
        ]}), encoding="utf-8")
        self.engine = SupportEngine(self.config, self.db)
        root = self.root / "checkout"
        docs = root / "docs"
        docs.mkdir(parents=True)
        (docs / "alpha.md").write_text("راهنمای خاص نرم افزار آلفا: کلید صفحه فروش.", encoding="utf-8")
        (docs / "beta.md").write_text("راهنمای خاص نرم افزار بتا: گزارش انبار.", encoding="utf-8")
        self.engine.knowledge.ingest(self.engine.projects["alpha"], root)
        self.engine.knowledge.ingest(self.engine.projects["beta"], root)

    def serve(self, scoped_only=True, api_key="old-global-secret"):
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.engine, api_key,
                                          scoped_only=scoped_only))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def request(self, base, path, token=None, body=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(base + path,
                          data=json.dumps(body).encode("utf-8") if body is not None else None,
                          headers=headers,
                          method="POST" if body is not None else "GET")
        with urlopen(request, timeout=3) as response:
            return response.status, json.load(response)

    def error_code(self, base, path, token=None, body=None):
        with self.assertRaises(HTTPError) as error:
            self.request(base, path, token, body)
        return error.exception.code

    def test_public_requires_scoped_token_not_global_or_anonymous(self):
        tok = self.engine.access.issue("alpha")
        base = self.serve(scoped_only=True)
        self.assertEqual(self.error_code(base, "/api/projects"), 401)
        self.assertEqual(self.error_code(base, "/api/projects", "old-global-secret"), 401)
        self.assertEqual(self.error_code(base, "/api/projects", "wrong-key"), 401)
        status, body = self.request(base, "/api/projects", tok["token"])
        self.assertEqual(status, 200)
        self.assertEqual([x["id"] for x in body["projects"]], ["alpha"])
        self.assertNotIn("Software Beta", json.dumps(body))

    def test_cannot_cross_read_project_or_submit_tickets_as_other_app(self):
        alpha = self.engine.access.issue("alpha", allow_ticket=False)
        beta = self.engine.access.issue("beta", allow_ticket=True)
        base = self.serve()
        question = {"project": "alpha", "message": "راهنمای خاص نرم افزار آلفا"}
        s, r = self.request(base, "/api/chat", alpha["token"], question)
        self.assertEqual(s, 200)
        self.assertEqual(r["project"], "alpha")
        self.assertIn("فروش", r["answer"])
        self.assertEqual(self.error_code(
            base, "/api/chat", alpha["token"], {"project": "beta", "message": "گزارش انبار"}), 403)
        self.assertEqual(self.error_code(
            base, "/api/ticket", alpha["token"],
            {"project": "alpha", "message": "مشکل جدید", "consent": True}), 403)
        self.assertEqual(self.error_code(
            base, "/api/ticket", beta["token"],
            {"project": "alpha", "message": "مشکل جدید", "consent": True}), 403)
        status, result = self.request(base, "/api/ticket", beta["token"],
                                      {"project": "beta", "message": "مشکل در گزارش انبار", "consent": True})
        self.assertEqual(status, 201)
        self.assertEqual(result["project"], "beta")
        self.assertEqual(self.error_code(
            base, "/api/chat", alpha["token"],
            {"project": "../../beta", "message": "گزارش انبار"}), 403)

    def test_revocation_is_immediate_and_secrets_never_in_list(self):
        alpha = self.engine.access.issue("alpha", allow_ticket=True)
        base = self.serve()
        self.assertEqual(self.request(base, "/api/projects", alpha["token"])[0], 200)
        records = self.engine.access.list("alpha")
        self.assertEqual(len(records), 1)
        self.assertNotIn(alpha["token"], json.dumps(records))
        with sqlite3.connect(self.db) as db:
            self.assertNotIn(alpha["token"], str(db.execute(
                "SELECT * FROM support_scoped_tokens").fetchall()))
        self.assertTrue(self.engine.access.revoke(alpha["token_id"]))
        self.assertFalse(self.engine.access.revoke(alpha["token_id"]))
        self.assertEqual(self.error_code(base, "/api/projects", alpha["token"]), 401)
        self.assertEqual(self.engine.access.active_count(), 0)

    def test_local_legacy_is_explicit_compatibility_only(self):
        base = self.serve(scoped_only=False)
        _, r = self.request(base, "/api/projects", "old-global-secret")
        self.assertEqual({x["id"] for x in r["projects"]}, {"alpha", "beta"})
        self.assertEqual(self.error_code(base, "/api/projects", "not-the-legacy-secret"), 401)

    def test_nonlocal_serve_refuses_without_active_scoped_keys(self):
        output = io.StringIO()
        with redirect_stdout(output):
            with self.assertRaises(SystemExit) as err:
                main(["--config", str(self.config), "--db", str(self.db),
                      "serve", "--host", "0.0.0.0", "--port", "0"])
        self.assertNotEqual(err.exception.code, 0)

    def test_token_issue_is_only_local_trusted_cli_not_public_api(self):
        base = self.serve(scoped_only=True)
        alpha = self.engine.access.issue("alpha")
        self.assertEqual(self.error_code(
            base, "/api/issue-access", alpha["token"],
            {"project": "alpha"}), 404)
        with self.assertRaises(ValueError):
            self.engine.access.issue("../alpha")
        issued = io.StringIO()
        with redirect_stdout(issued):
            main(["--config", str(self.config), "--db", str(self.db),
                  "issue-access", "--project", "beta", "--allow-ticket"])
        token = json.loads(issued.getvalue())
        self.assertTrue(token["token"].startswith("amin_"))
        self.assertTrue(token["allow_ticket"])
        self.assertEqual(self.engine.access.verify(token["token"])["project_id"], "beta")


if __name__ == "__main__":
    unittest.main()
