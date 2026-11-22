import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from model_probe import probe_model, validate_base_url


class ModelProbeTests(unittest.TestCase):
    def test_not_configured_is_not_a_pass(self):
        result = probe_model({})
        self.assertFalse(result["configured"])
        self.assertEqual(result["status"], "not_configured")
        self.assertFalse(result["responded"])

    def test_rejects_insecure_or_malformed_api_urls(self):
        for url in ("http://example.org/v1", "ftp://example.org/v1",
                    "https://user:pass@example.org/v1",
                    "https://example.org/v1?key=secret",
                    "https://example.org/v1#model",
                    "http://10.0.0.1:1234/v1",
                    "https://example.org/v1/chat/completions"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_base_url(url)

    def test_no_secret_revealed_and_loopback_http_request_works(self):
        class Handler(BaseHTTPRequestHandler):
            payload = None
            auth = None

            def log_message(self, format, *args):
                pass

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                Handler.payload = json.loads(self.rfile.read(length))
                Handler.auth = self.headers.get("Authorization")
                response = json.dumps({
                    "choices": [{"message": {"content": "پاسخ فارسی آزمایشی"}}]
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = {"AMIN_MODEL_BASE_URL": f"http://127.0.0.1:{server.server_port}/v1",
               "AMIN_MODEL_NAME": "test-placeholder",
               "AMIN_MODEL_API_KEY": "do-not-print-this-key"}
        result = probe_model(env)
        self.assertEqual(result["status"], "response_smoke_passed")
        self.assertTrue(result["responded"])
        self.assertTrue(result["persian_output"])
        self.assertNotIn("do-not-print-this-key", json.dumps(result))
        self.assertEqual(Handler.auth, "Bearer do-not-print-this-key")
        self.assertEqual(Handler.payload["model"], "test-placeholder")
        self.assertEqual(Handler.payload["messages"][1]["content"][:14],
                         "این یک آزمایش ")
        self.assertNotIn("private source", json.dumps(Handler.payload))

    def test_english_only_reply_does_not_pass_persian(self):
        class FakeResponse:
            def __enter__(self):
                import io
                return io.BytesIO(b'{"choices":[{"message":{"content":"Hello"}}]}')
            def __exit__(self, *args):
                return False
        result = probe_model({"AMIN_MODEL_BASE_URL": "https://example.org/v1",
                              "AMIN_MODEL_NAME": "placeholder",
                              "AMIN_ZERO_PAYMENT_MODE": "off"},
                             opener=lambda req, timeout: FakeResponse())
        self.assertEqual(result["status"], "non_persian_response")
        self.assertFalse(result["persian_output"])

    def test_unavailable_service_is_not_a_pass(self):
        from urllib.error import URLError
        def fail(*args, **kwargs):
            raise URLError("Test-only simulated outage; not a real network result")
        result = probe_model({"AMIN_MODEL_BASE_URL": "http://127.0.0.1:1/v1",
                              "AMIN_MODEL_NAME": "placeholder"}, opener=fail)
        self.assertEqual(result["status"], "connection_or_response_error")
        self.assertFalse(result["responded"])

    def test_http_auth_failure_reports_only_status(self):
        from urllib.error import HTTPError
        def fail(request, timeout):
            raise HTTPError(request.full_url, 401, "hidden upstream detail", {}, None)
        result = probe_model({"AMIN_MODEL_BASE_URL": "https://example.org/v1",
                              "AMIN_MODEL_NAME": "placeholder",
                              "AMIN_MODEL_API_KEY": "never-expose-me",
                              "AMIN_ZERO_PAYMENT_MODE": "off"}, opener=fail)
        self.assertEqual(result["http_status"], 401)
        self.assertNotIn("never-expose-me", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
