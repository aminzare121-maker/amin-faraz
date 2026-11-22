"""Test local-process model resource protection with deterministic clocks."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from amin_support import SupportEngine, make_handler
from request_limits import SlidingLimits


class FakeClock:
    def __init__(self):
        self.now = 100
    def __call__(self):
        return self.now


class RateLimitTests(unittest.TestCase):
    def test_per_program_key_and_action_budgets_reset(self):
        clock = FakeClock()
        limits = SlidingLimits(clock)
        for _ in range(3):
            self.assertTrue(limits.allow("alpha-token", "chat", 3, window_s=60))
        self.assertFalse(limits.allow("alpha-token", "chat", 3, window_s=60))
        self.assertTrue(limits.allow("beta-token", "chat", 3, window_s=60))
        self.assertTrue(limits.allow("alpha-token", "ticket", 2, window_s=60))
        clock.now += 61
        self.assertTrue(limits.allow("alpha-token", "chat", 3, window_s=60))

    def test_invalid_scopes_are_rejected(self):
        limit = SlidingLimits()
        for token, route, cap in (("", "chat", 1), ("a", "admin", 1),
                                   ("a", "chat", 0)):
            with self.assertRaises(ValueError):
                limit.allow(token, route, cap)

    def test_actual_http_returns_429_and_other_program_still_works(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cfg = root / "config.json"
            cfg.write_text(json.dumps({"projects": [
                {"id": "alpha", "name": "A", "source_prefixes": [],
                 "public_paths": []},
                {"id": "beta", "name": "B", "source_prefixes": [],
                 "public_paths": []}
            ]}), encoding="utf-8")
            engine = SupportEngine(cfg, root / "db.sqlite3")
            a = engine.access.issue("alpha")["token"]
            b = engine.access.issue("beta")["token"]
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0), make_handler(engine, "", scoped_only=True))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            url = f"http://127.0.0.1:{server.server_port}/api/chat"
            def call(key, project):
                req = Request(url, data=json.dumps({
                    "project": project, "message": "سؤال نمونه عمومی"
                }).encode("utf-8"), headers={
                    "Authorization": "Bearer " + key, "Content-Type": "application/json"
                }, method="POST")
                try:
                    with urlopen(req, timeout=3) as resp:
                        return resp.status
                except HTTPError as exc:
                    return exc.code
            for _ in range(30):
                self.assertEqual(call(a, "alpha"), 200)
            self.assertEqual(call(a, "alpha"), 429)
            self.assertEqual(call(b, "beta"), 200)


if __name__ == "__main__":
    unittest.main()
