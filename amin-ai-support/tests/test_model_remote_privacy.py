"""Privacy gate: explicit request-level consent in addition to operator-level consent.

Fixtures are mocks: success demonstrates non-disclosure gate logic, not a real
remote provider's data protection, production identity, or user consent logs.
"""
import io
import json
import os
from pathlib import Path
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
        self.project = {"id": "sample", "name": "نرم‌افزار مستقل"}
        self.public = [{"path": "README.md", "section": 0,
                        "excerpt": "نسخه نرم‌افزار را بررسی کنید."}]
        self.internal = [{"path": "internal.md", "section": 0,
                          "excerpt": "Developer-only project information"}]
        self.external_env = {
            "AMIN_MODEL_BASE_URL": "https://model.example.net/v1",
            "AMIN_MODEL_NAME": "a-model", "AMIN_MODEL_API_KEY": ""
        }

    def call(self, evidence=None, role="customer", external_consent=False):
        return model_completion("هنگام اجرا مشکل دارم", self.project,
                                evidence if evidence is not None else self.public,
                                None, role=role, external_consent=external_consent)

    def test_no_external_transport_by_default(self):
        with patch.dict(os.environ, self.external_env, clear=True), \
             patch("amin_support.urlopen") as opener:
            self.assertIsNone(self.call())
            self.assertIsNone(self.call(self.internal, role="developer"))
            opener.assert_not_called()

    def test_operator_permission_alone_never_replaces_per_request_consent(self):
        env = dict(self.external_env, AMIN_MODEL_REMOTE_CONSENT="allow")
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen") as opener:
            self.assertIsNone(self.call())
            self.assertIsNone(self.call(self.internal, role="developer"))
            opener.assert_not_called()

    def test_per_request_consent_alone_never_replaces_operator_permission(self):
        with patch.dict(os.environ, self.external_env, clear=True), \
             patch("amin_support.urlopen") as opener:
            self.assertIsNone(self.call(external_consent=True))
            opener.assert_not_called()

    def test_both_permissions_send_only_selected_question_and_public_evidence(self):
        env = dict(self.external_env, AMIN_MODEL_REMOTE_CONSENT="allow")
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as opener:
            reply = self.call(external_consent=True)
            self.assertIn("[1]", reply)
            self.assertEqual(opener.call_count, 1)
            request = opener.call_args.args[0]
            payload = json.loads(request.data)
            self.assertIn("README.md", payload["messages"][1]["content"])
            self.assertNotIn("internal.md", payload["messages"][1]["content"])

    def test_internal_developer_evidence_requires_third_permission(self):
        env = dict(self.external_env, AMIN_MODEL_REMOTE_CONSENT="allow")
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen") as opener:
            self.assertIsNone(self.call(self.internal, role="developer",
                                        external_consent=True))
            opener.assert_not_called()
        env["AMIN_MODEL_INTERNAL_CONSENT"] = "allow"
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as opener:
            self.assertIn("[1]", self.call(self.internal, role="developer",
                                           external_consent=True))
            self.assertEqual(opener.call_count, 1)

    def test_malformed_or_non_tls_remote_urls_cannot_send(self):
        bad_values = (
            "https://user:pass@model.example.net/v1",
            "https://model.example.net/v1?access=abc",
            "http://model.example.net/v1",
            "https://model.example.net/v1/chat/completions",
            "https://model.example.net/v1#hidden",
        )
        for bad in bad_values:
            env = dict(self.external_env, AMIN_MODEL_BASE_URL=bad,
                       AMIN_MODEL_REMOTE_CONSENT="allow")
            with self.subTest(url=bad), patch.dict(os.environ, env, clear=True), \
                 patch("amin_support.urlopen") as opener, \
                 self.assertRaises(ValueError):
                self.call(external_consent=True)
                opener.assert_not_called()

    def test_local_loopback_works_without_remote_permission(self):
        env = {"AMIN_MODEL_BASE_URL": "http://127.0.0.1:11434/v1",
               "AMIN_MODEL_NAME": "local-model"}
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=FakeReply()) as opener:
            self.assertIn("[1]", self.call(self.internal, role="developer"))
            self.assertEqual(opener.call_count, 1)

    def test_web_ui_has_separate_opt_in_from_ticket_storage(self):
        html = (Path(__file__).resolve().parents[1] / "web/index.html").read_text("utf-8")
        self.assertIn('id="remoteConsent"', html)
        self.assertIn('id="consent"', html)
        self.assertIn('external_model_consent:$("remoteConsent").checked === true', html)
        self.assertNotIn('type="checkbox" checked', html)


if __name__ == "__main__":
    unittest.main()
