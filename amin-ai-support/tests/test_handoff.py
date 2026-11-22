"""Private device handoff: real HTTP integration, requester isolation, consent,
private-only GitHub routing and reviewed answers. No external network.
"""
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amin_support import SupportEngine, main, make_handler
from handoff import publish_private_marker


class FakeResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")
    def __enter__(self):
        return io.BytesIO(self.data)
    def __exit__(self, *args):
        return False


class HandoffApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.config = root / "projects.json"
        self.db = root / "support.sqlite3"
        self.config.write_text(json.dumps({"projects": [
            {"id": "alpha", "name": "Alpha", "source_prefixes": [], "public_paths": []},
            {"id": "beta", "name": "Beta", "source_prefixes": [], "public_paths": []}
        ]}), encoding="utf-8")
        self.engine = SupportEngine(self.config, self.db)
        self.alpha_1 = self.engine.access.issue("alpha", allow_ticket=True)
        self.alpha_2 = self.engine.access.issue("alpha", allow_ticket=True)
        self.alpha_denied = self.engine.access.issue("alpha", allow_ticket=False)
        self.beta = self.engine.access.issue("beta", allow_ticket=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     make_handler(self.engine, "", scoped_only=True))
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}"

    def call(self, path, token, body=None):
        req = Request(
            self.url + path,
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"},
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method="POST" if body is not None else "GET")
        with urlopen(req, timeout=3) as response:
            return response.status, json.load(response)

    def error(self, path, token, body=None):
        with self.assertRaises(HTTPError) as exc:
            self.call(path, token, body)
        return exc.exception.code

    def test_submit_and_answer_return_to_same_token_only(self):
        private_message = "راز محرمانه مشتری: ۹۹۸۸۷۷"
        payload = {"project": "alpha", "message": private_message, "consent": True}
        with patch.dict(os.environ, {"AMIN_HANDOFF_GITHUB_TOKEN": "",
                                     "AMIN_HANDOFF_GITHUB_REPO": ""}):
            status, item = self.call("/api/handoff", self.alpha_1["token"], payload)
        self.assertEqual(status, 201)
        self.assertEqual(item["status"], "pending")
        self.assertFalse(item["chatgpt_invoked"])
        self.assertFalse(item["public_text_uploaded"])
        self.assertEqual(item["github_state"], "not_configured")
        reqid = item["id"]
        path = "/api/handoff?id=" + reqid
        self.assertEqual(self.error(path, self.alpha_2["token"]), 404)
        self.assertEqual(self.error(path, self.beta["token"]), 404)
        self.assertEqual(self.error("/api/handoff?id=" + "f"*32, self.alpha_1["token"]), 404)
        self.assertEqual(self.call(path, self.alpha_1["token"])[1]["status"], "pending")
        self.assertTrue(self.engine.handoffs.answer("alpha", reqid, "پاسخ تأییدشده برای امین"))
        self.assertFalse(self.engine.handoffs.answer("alpha", reqid, "تکراری"))
        resolved = self.call(path, self.alpha_1["token"])[1]
        self.assertEqual(resolved["answer"], "پاسخ تأییدشده برای امین")
        self.assertEqual(resolved["status"], "answered")
        self.assertNotIn(private_message, json.dumps(item, ensure_ascii=False))
        self.assertNotIn(private_message, self.engine.answer("alpha", "راز محرمانه")["answer"])

    def test_cross_project_and_consent_and_permission(self):
        data = {"project": "alpha", "message": "درخواست", "consent": True}
        self.assertEqual(self.error("/api/handoff", self.beta["token"], data), 403)
        self.assertEqual(self.error("/api/handoff", self.alpha_denied["token"], data), 403)
        self.assertEqual(self.error("/api/handoff", self.alpha_1["token"], {**data, "consent": False}), 400)
        self.assertEqual(self.error("/api/handoff", self.alpha_1["token"], {**data, "message": ""}), 400)

    def test_unknown_token_cannot_submit_or_poll(self):
        self.assertEqual(self.error("/api/handoff", "invalid",
                                    {"project": "alpha", "message": "x", "consent": True}), 401)
        self.assertEqual(self.error("/api/handoff?id="+"0"*32, "invalid"), 401)

    def test_github_requires_private_repo_and_never_posts_to_public(self):
        ident = self.engine.handoffs.submit("alpha", self.alpha_1["token_id"], "private data", True)
        calls = []
        def pretend(req, timeout=8):
            calls.append((req.full_url, req.data))
            if req.full_url.endswith("/issues"):
                raise AssertionError("must never publish to PUBLIC repository")
            return FakeResponse({"private": False})
        with patch.dict(os.environ, {"AMIN_HANDOFF_GITHUB_TOKEN": "test-scope",
                                     "AMIN_HANDOFF_GITHUB_REPO": "owner/public"}):
            with patch("handoff.urlopen", side_effect=pretend):
                result = publish_private_marker(self.engine.handoffs, ident)
        self.assertEqual(result, "failed")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0][1])

    def test_private_repo_gets_only_marker_not_user_text(self):
        secret = "DO-NOT-UPLOAD-USER-CHAT-007"
        ident = self.engine.handoffs.submit("alpha", self.alpha_1["token_id"], secret, True)
        calls = []
        def pretend(req, timeout=8):
            calls.append((req.full_url, req.data))
            return FakeResponse({"private": True} if req.data is None else {"number": 321})
        with patch.dict(os.environ, {"AMIN_HANDOFF_GITHUB_TOKEN": "test-scope",
                                     "AMIN_HANDOFF_GITHUB_REPO": "owner/private"}):
            with patch("handoff.urlopen", side_effect=pretend):
                result = publish_private_marker(self.engine.handoffs, ident)
        self.assertEqual(result, "published")
        self.assertEqual(len(calls), 2)
        self.assertNotIn(secret, calls[1][1].decode("utf-8"))
        self.assertNotIn("alpha", calls[1][1].decode("utf-8"))

    def test_cli_reviewed_answer_is_retrieved_over_api(self):
        ident = self.engine.handoffs.submit("beta", self.beta["token_id"], "Help beta", True)
        output = io.StringIO()
        with redirect_stdout(output):
            main(["--config", str(self.config), "--db", str(self.db),
                  "handoff-answer", "--project", "beta", "--id", ident,
                  "--answer", "بررسی شد؛ رفع خطا"])
        self.assertTrue(json.loads(output.getvalue())["answered"])
        self.assertEqual(self.call("/api/handoff?id=" + ident, self.beta["token"])[1]["answer"],
                         "بررسی شد؛ رفع خطا")


if __name__ == "__main__":
    unittest.main()
