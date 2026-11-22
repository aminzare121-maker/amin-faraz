"""Offline tests for official plan-sharing; never perform real OAuth/inference in CI."""
import io
import json
import unittest
from unittest.mock import patch

from chatgpt_plan_direct import (
    authorization_url, pkce_values, parse_sse_events, _make_profile,
    PlanConnectionUnavailable, REQUIRED_SCOPE, SCOPES,
)


class OfficialSIWCTests(unittest.TestCase):
    def test_pkce_and_dynamic_client_registration(self):
        v, c = pkce_values()
        self.assertGreaterEqual(len(v), 43)
        self.assertTrue(c)
        url = authorization_url("http://127.0.0.1:1455/auth/callback",
                                "state", "nonce", c,
                                "urn:uuid:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee")
        self.assertIn("client_id=dynamic_agent_client", url)
        self.assertIn("chatgpt.tokens.use.direct", url)
        self.assertIn("resource=https%3A%2F%2Fapi.openai.com%2Fv1", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("agent_name_hint=Amin+AI+Support", url)
        self.assertNotIn("api_key", url)
        self.assertNotIn("Codex", url)

    def test_reject_non_loopback_redirect(self):
        for uri in ("https://evil.example/auth/callback",
                    "http://localhost:1234/auth/callback",
                    "http://127.0.0.1:1234/callback"):
            with self.assertRaises(ValueError):
                authorization_url(uri, "state", "nonce", "challenge", "urn:uuid:x")

    def test_plan_scope_required_no_paid_fallback(self):
        data = {"access_token": "a"*30, "refresh_token": "r"*30,
                "token_type": "Bearer", "expires_in": 3600,
                "scope": "openid profile email offline_access"}
        with self.assertRaisesRegex(PlanConnectionUnavailable, "not approved"):
            _make_profile(data, "oaiapp_"+("x"*20),
                          "urn:uuid:local", {"sub": "user"})
        data["scope"] = SCOPES
        result = _make_profile(data, "oaiapp_"+("x"*20),
                               "urn:uuid:local", {"sub": "user"})
        self.assertIn(REQUIRED_SCOPE, result["scopes"])
        self.assertGreater(result["expires_at"], 0)

    def test_successful_stream_requires_completed_event(self):
        payload = [
            'event: response.output_text.delta\n',
            'data: '+json.dumps({"type":"response.output_text.delta","delta":"سلام "})+'\n',
            '\n',
            'data: '+json.dumps({"type":"response.output_text.delta","delta":"امین"})+'\n',
            'data: '+json.dumps({"type":"response.completed"})+'\n',
        ]
        self.assertEqual(parse_sse_events(payload), "سلام امین")

    def test_interrupted_stream_never_claims_success(self):
        chunks = ['data: '+json.dumps({"type":"response.output_text.delta","delta":"half"})+'\n']
        with self.assertRaisesRegex(PlanConnectionUnavailable, "incomplete"):
            parse_sse_events(chunks)

    def test_subscription_error_during_stream_denies_success(self):
        chunks = [
            'data: '+json.dumps({"type":"response.output_text.delta","delta":"partial"})+'\n',
            'data: '+json.dumps({"type":"response.failed",
                "response":{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}})+'\n'
        ]
        with self.assertRaisesRegex(PlanConnectionUnavailable, "subscription_sharing_usage_limit_exceeded"):
            parse_sse_events(chunks)

    def test_account_switch_denied(self):
        data = {"access_token": "a"*30, "refresh_token": "r"*30,
                "token_type": "Bearer", "scope": SCOPES}
        prev = {"client_id": "oaiapp_"+("x"*20), "subject": "original"}
        with self.assertRaisesRegex(PlanConnectionUnavailable, "identity changed"):
            _make_profile(data, prev["client_id"],
                          "urn:uuid:one", {"sub": "other"}, prev)


if __name__ == "__main__":
    unittest.main()
