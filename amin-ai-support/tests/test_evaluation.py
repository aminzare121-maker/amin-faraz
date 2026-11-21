import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from amin_support import model_completion, _identifier_focus
from evaluation import evaluate


class EvaluationTests(unittest.TestCase):
    def test_synthetic_project_separation(self):
        result = evaluate()
        self.assertGreaterEqual(result["total"], 10)
        self.assertEqual(result["failed"], 0, result)
        self.assertFalse(result["supports_real_customer_acceptance"])
        self.assertEqual(result["fixture_type"], "synthetic")


class FakeModel(BaseHTTPRequestHandler):
    reply = "طبق مستند پروژه [1] ابتدا اتصال را بررسی کنید."
    last_request = None

    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        size = int(self.headers.get("Content-Length", "0"))
        FakeModel.last_request = json.loads(self.rfile.read(size))
        encoded = json.dumps({"choices": [{"message": {"content": self.reply}}]},
                             ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class ModelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.env = patch.dict(os.environ, {
            "AMIN_MODEL_BASE_URL": f"http://127.0.0.1:{self.server.server_port}/v1",
            "AMIN_MODEL_NAME": "synthetic-stub-model",
            "AMIN_MODEL_API_KEY": ""
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sources = [{"path": "docs/guide.md", "section": 0,
                         "excerpt": "اتصال MT5 باید بررسی شود."}]

    def call(self, text):
        FakeModel.reply = text
        return model_completion("اتصال MT5", {"name": "فراز"}, self.sources, None)

    def test_accept_only_existing_source_citations(self):
        self.assertEqual(self.call("طبق مستند [1] وضعیت اتصال را بررسی کنید."),
                         "طبق مستند [1] وضعیت اتصال را بررسی کنید.")
        self.assertEqual(FakeModel.last_request["model"], "synthetic-stub-model")
        self.assertGreaterEqual(FakeModel.last_request["max_tokens"], 32)
        self.assertIn("docs/guide.md", FakeModel.last_request["messages"][1]["content"])

    def test_reject_uncited_or_nonexistent_sources(self):
        self.assertIsNone(self.call("اتصال درست شد."))
        self.assertIsNone(self.call("طبق سند [4] این مشکل حل شده."))
        self.assertIsNone(self.call("طبق سند [1] و [4] اتصال برقرار است."))

    def test_reject_metadata_only_source_header(self):
        # Found by live Qwen model pilot; citations alone cannot count as support.
        self.assertIsNone(self.call("[1] docs/guide.md section 0"))
        self.assertIsNone(self.call("docs/guide.md section 0 [1]"))
        self.assertIsNone(self.call("[1]"))
        self.assertIsNotNone(self.call("طبق راهنمای [1] ابتدا سرویس اتصال را بررسی کنید."))

    def test_identifier_question_uses_matching_source_row_and_rejects_wrong_version(self):
        evidence = [{
            "path": "INDEX_FA.md",
            "section": 0,
            "excerpt": (
                "| کد | نام ابزار | وضعیت |\n"
                "| --- | --- | --- |\n"
                "| VIDEO-001 | پردازشگر مستقل فیلم و کلاس | ابزار اصلی |\n"
                "| VIDEO-001-V13 | ارتقای آزمایشی پردازشگر فیلم | غیرعملیاتی |"
            )
        }]
        question = "شناسه ثبت‌شده پردازشگر فیلم و کلاس در مخزن ابزارها چیست؟"
        focus = _identifier_focus(question, evidence)
        self.assertIsNotNone(focus)
        self.assertEqual(focus[1], "VIDEO-001")
        self.assertIn("پردازشگر مستقل فیلم و کلاس", focus[0])
        FakeModel.reply = "شناسه ابزار VIDEO-001-V13 است. [1]"
        self.assertIsNone(model_completion(question, {"name": "آرتین"}, evidence, None))
        self.assertIn("بخش دقیقاً مرتبط", FakeModel.last_request["messages"][1]["content"])
        FakeModel.reply = "طبق سند [1] شناسه ابزار اصلی VIDEO-001 است."
        self.assertEqual(
            model_completion(question, {"name": "آرتین"}, evidence, None),
            FakeModel.reply)
        self.assertIsNone(_identifier_focus("اتصال MT5", evidence))

    def test_identifier_source_without_clear_matching_row_is_not_forced(self):
        sources = [{"path": "docs/help.md", "section": 0,
                    "excerpt": "| APP-100 | سرویس شبکه | فعال |"}]
        self.assertIsNone(_identifier_focus("شناسه پردازشگر فیلم و کلاس چیست؟", sources))

    def test_reject_claims_of_actions_not_performed(self):
        self.assertIsNone(self.call("من نصب کردم. طبق سند [1]"))
        self.assertIsNone(self.call("من معامله کردم. طبق سند [1]"))

    def test_test_server_does_not_claim_real_model(self):
        self.assertEqual(FakeModel.last_request.get("model"), "synthetic-stub-model")


if __name__ == "__main__":
    unittest.main()
