"""External model privacy: no question/source may leave the machine by default."""
import io
import json
import os
import unittest
from unittest.mock import patch

from amin_support import model_completion


class FakeReply:
    def __enter__(self):
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "طبق سند [1] نسخه نرم‌افزار را بررسی کنید."}}]
        }, ensure_ascii=False).encode("utf-8"))

    def __exit__(self, *args):
        return False


class RemoteModelPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.project = {"id": "faraz", "name": "فراز"}
        self.public = [{"path": "README.md", "section": 0,
                        "excerpt": "نسخه نرم‌افزار را بررسی کنید."}]
        self.internal = [{"path": "internal.md", "section": 0,
                          "excerpt": "Developer-only project information"}]
        self.external_env = {
            "AMIN_MODEL_BASE_URL": "https://model.example.net/v1",
            "AMIN_MODEL_NAME": "a-model", "AMIN_MODEL_API_KEY": ""
        }

    def call(self, evidence=None, role="customer"):
        return model_completion("هنگام اجرا مشکل دارم", self.project,
                                evidence or self.public, None, role=role)

    def test_default_denies_remote_without_even_opening_connection(self):
        with patch.dict(os.environ, self.external_env, clear=True), \
             patch("amin_support.urlopen") as open_mock:
            self.assertIsNone(self.call())
            self.assertIsNone(self.call(self.internal, role="developer"))
            open_mock.assert_not_called()

    def test_operator_consent_for_public_remote_model_is_explicit(self):
        env = dict(self.external_env, AMIN_MODEL_REMOTE_CONSENT="allow")
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as open_mock:
            reply = self.call()
            self.assertIn("[1]", reply)
            self.assertEqual(open_mock.call_count, 1)
            request = open_mock.call_args.args[0]
            body = json.loads(request.data)
            self.assertIn("README.md", body["messages"][1]["content"])

    def test_developer_evidence_needs_separate_explicit_consent(self):
        env = dict(self.external_env, AMIN_MODEL_REMOTE_CONSENT="allow")
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen") as open_mock:
            self.assertIsNone(self.call(self.internal, role="developer"))
            open_mock.assert_not_called()
        env["AMIN_MODEL_INTERNAL_CONSENT"] = "allow"
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as open_mock:
            self.assertIn("[1]", self.call(self.internal, role="developer"))
            self.assertEqual(open_mock.call_count, 1)

    def test_malformed_remote_url_must_fail_before_any_request(self):
        for bad in ("https://user:pass@model.example.net/v1",
                    "https://model.example.net/v1?token=abc",
                    "http://model.example.net/v1",
                    "https://model.example.net/v1/chat/completions"):
            env = dict(self.external_env, AMIN_MODEL_BASE_URL=bad,
                       AMIN_MODEL_REMOTE_CONSENT="allow")
            with self.subTest(base=bad), patch.dict(os.environ, env, clear=True), \
                 patch("amin_support.urlopen") as open_mock, \
                 self.assertRaises(ValueError):
                self.call()
                open_mock.assert_not_called()

    def test_local_loopback_continues_to_work_without_remote_consent(self):
        env = {"AMIN_MODEL_BASE_URL": "http://127.0.0.1:11434/v1",
               "AMIN_MODEL_NAME": "local-model"}
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as open_mock:
            self.assertIn("[1]", self.call(self.internal, role="developer"))
            self.assertEqual(open_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
