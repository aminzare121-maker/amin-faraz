"""Owner zero-payment rule tested against attempted external requests.

No real paid services are contacted. Local provider mock proves local path is
retained. The workflow audit is a static runner-class safeguard, not a bill.
"""
import io
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from amin_support import model_completion
from audit_free_github import audit, scan_text
from model_probe import probe_model
from zero_payment_policy import permits_model_url, zero_payment_enabled


class LocalReply:
    def __enter__(self):
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "طبق سند [1] راهنمای محلی را بررسی کنید."}}]
        }, ensure_ascii=False).encode("utf-8"))
    def __exit__(self, *args):
        return False


class ZeroPaymentTests(unittest.TestCase):
    def setUp(self):
        self.project = {"id": "independent", "name": "نرم‌افزار دیگر"}
        self.evidence = [{"path": "guide.md", "section": 0, "excerpt": "راهنمای محلی"}]

    def test_on_by_default_and_external_provider_never_called_even_with_all_consents(self):
        env = {
            "AMIN_MODEL_BASE_URL": "https://potentially-paid.example.org/v1",
            "AMIN_MODEL_NAME": "remote",
            "AMIN_MODEL_REMOTE_CONSENT": "allow",
            "AMIN_MODEL_INTERNAL_CONSENT": "allow",
            "AMIN_MODEL_API_KEY": "anykey"
        }
        with patch.dict(os.environ, env, clear=True), patch("amin_support.urlopen") as transport:
            self.assertTrue(zero_payment_enabled())
            result = model_completion("پرسش", self.project, self.evidence, None,
                                      role="developer", external_consent=True)
            self.assertIsNone(result)
            transport.assert_not_called()
        with patch("model_probe.urlopen") as transport:
            probe = probe_model(env, opener=transport)
            self.assertEqual(probe["status"], "blocked_by_zero_payment_mode")
            transport.assert_not_called()

    def test_local_model_workflow_remains_usable_without_paid_api(self):
        env = {
            "AMIN_MODEL_BASE_URL": "http://127.0.0.1:11434/v1",
            "AMIN_MODEL_NAME": "ollama-local",
            "AMIN_ZERO_PAYMENT_MODE": "on"
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=LocalReply()) as transport:
            self.assertIn("[1]", model_completion(
                "پرسش راهنمای محلی", self.project, self.evidence, None))
            self.assertEqual(transport.call_count, 1)

    def test_explicit_opt_out_retains_preexisting_remote_consent_guards(self):
        env = {"AMIN_ZERO_PAYMENT_MODE": "off",
               "AMIN_MODEL_BASE_URL": "https://model.example.org/v1",
               "AMIN_MODEL_NAME": "remote",
               "AMIN_MODEL_REMOTE_CONSENT": "allow"}
        with patch.dict(os.environ, env, clear=True), \
             patch("amin_support.urlopen", return_value=LocalReply()) as transport:
            self.assertIsNone(model_completion(
                "پرسش", self.project, self.evidence, None, external_consent=False))
            transport.assert_not_called()
            self.assertIn("[1]", model_completion(
                "پرسش", self.project, self.evidence, None, external_consent=True))

    def test_policy_parses_explicit_values_but_does_not_assume_free_external_api(self):
        self.assertTrue(zero_payment_enabled({}))
        self.assertTrue(zero_payment_enabled({"AMIN_ZERO_PAYMENT_MODE": "on"}))
        self.assertFalse(zero_payment_enabled({"AMIN_ZERO_PAYMENT_MODE": "OFF"}))
        self.assertFalse(permits_model_url("https://example.org/v1", {}))
        self.assertTrue(permits_model_url("http://localhost:11434/v1", {}))
        self.assertTrue(permits_model_url("http://127.0.0.1:11434/v1", {}))


class GithubCostAuditTests(unittest.TestCase):
    def test_rejects_larger_and_dynamic_runners(self):
        self.assertTrue(scan_text("paid.yml", "jobs:\n  pay:\n    runs-on: ubuntu-latest-16-cores\n"))
        self.assertTrue(scan_text("paid.yml", "jobs:\n  pay:\n    runs-on: ubuntu-24.04-8core\n"))
        self.assertTrue(scan_text("paid.yml", "jobs:\n  pay:\n    runs-on: \${{ matrix.runner }}\n"))
        self.assertFalse(scan_text("free.yml", "jobs:\n  free:\n    runs-on: ubuntu-latest\n"))
        self.assertFalse(scan_text("owner.yml", "jobs:\n  local:\n    runs-on: [amin-win-native-58]\n"))

    def test_private_repo_fails_free_runner_assumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "test.yml").write_text(
                "jobs:\n  tests:\n    runs-on: ubuntu-24.04\n", encoding="utf-8")
            self.assertEqual(audit(root, visibility="public"), [])
            self.assertTrue(audit(root, visibility="private"))

    def test_actual_repo_runner_definitions_currently_allowed(self):
        repo = Path(__file__).resolve().parents[2]
        self.assertEqual(audit(repo, visibility="public"), [])

    def test_windows_launcher_explicitly_local_only_and_no_auto_install(self):
        path = (Path(__file__).resolve().parents[1] /
                "windows" / "Start-AminSupport-Free.ps1")
        script = path.read_text(encoding="utf-8")
        self.assertIn('$env:AMIN_ZERO_PAYMENT_MODE = "on"', script)
        self.assertIn('http://127.0.0.1:11434/v1', script)
        self.assertIn('--host 127.0.0.1', script)
        self.assertNotIn("Invoke-WebRequest", script)
        self.assertNotIn("winget install", script)


if __name__ == "__main__":
    unittest.main()
