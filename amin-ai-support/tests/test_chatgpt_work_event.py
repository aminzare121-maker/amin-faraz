"""No-network checks: PR event for ChatGPT Work without invoking Codex/API."""
from __future__ import annotations

import base64
import json
import unittest

from chatgpt_work_event import prepare_work_event


class MockPrivateBridge:
    def __init__(self, private=True, owner="owner", consent=True, test_only=False):
        self.private = private
        self.owner = owner
        self.consent = consent
        self.test_only = test_only
        self.rid = "a" * 32
        self.calls = []
        self.question = "SECRET_PRIVATE_USER_QUESTION_NEVER_COMMIT"
        self.branch_created = False

    def require_private(self):
        if not self.private:
            raise RuntimeError("PUBLIC repository refused")
        return {"private": True, "owner": {"login": "owner"},
                "full_name": "owner/repo", "default_branch": "main"}

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if (method, path) == ("GET", "/issues/12"):
            return {"user": {"login": self.owner},
                    "body": "AMIN_CHAT_BRIDGE_V1\n" + json.dumps({
                        "request_id": self.rid, "project": "support",
                        "question": self.question,
                        "consent": self.consent, "test_only": self.test_only,
                    })}
        if (method, path) == ("GET", "/git/ref/heads/main"):
            return {"object": {"sha": "b" * 40}}
        if (method, path) == ("POST", "/git/refs"):
            self.branch_created = True
            return {"ref": payload["ref"]}
        if method == "PUT" and path.endswith(".json"):
            return {"content": {"path": path}}
        if (method, path) == ("POST", "/pulls"):
            return {"number": 22}
        raise AssertionError("Unexpected GitHub endpoint: " + method + " " + path)


class ChatGPTWorkPRBridgeTests(unittest.TestCase):
    def test_private_pr_event_contains_no_question_and_no_model_claim(self):
        bridge = MockPrivateBridge()
        result = prepare_work_event(bridge, 12, bridge.rid)
        self.assertTrue(result["private_pr_event_created"])
        self.assertFalse(result["chatgpt_invoked"])
        self.assertFalse(result["chatgpt_task_configured"])
        self.assertFalse(result["execution_authorized"])
        calls = [item for item in bridge.calls if item[0] in {"PUT", "POST"}]
        payloads = [json.dumps(item[2]) for item in calls]
        self.assertNotIn(bridge.question, " ".join(payloads))
        saved = next(x[2] for x in calls if x[0] == "PUT")
        raw = json.loads(base64.b64decode(saved["content"]).decode("utf8"))
        self.assertEqual(raw["request_id"], bridge.rid)
        self.assertEqual(raw["issue_number"], 12)
        self.assertFalse(raw["execution_authorized"])
        pr = next(x[2] for x in calls if x[1] == "/pulls")
        self.assertTrue(pr["title"].startswith("[Amin ChatGPT Work] "))
        self.assertEqual(pr["head"], "amin-chatgpt-work/" + bridge.rid)
        self.assertEqual(pr["base"], "main")
        self.assertNotIn(bridge.question, pr["body"])

    def test_public_issue_mismatch_or_no_consent_cannot_emit_pr(self):
        for params in ({"private": False}, {"owner": "someone_else"},
                       {"consent": False}, {"test_only": True}):
            bridge = MockPrivateBridge(**params)
            with self.subTest(params=params), self.assertRaises(RuntimeError):
                prepare_work_event(bridge, 12, bridge.rid)
            self.assertFalse(bridge.branch_created)

    def test_invalid_request_never_calls_remote(self):
        bridge = MockPrivateBridge()
        for issue, rid in ((0, bridge.rid), (12, "short"), (12, "f"*32)):
            with self.subTest(issue=issue, rid=rid), self.assertRaises((ValueError, RuntimeError)):
                prepare_work_event(bridge, issue, rid)
        self.assertFalse(bridge.branch_created)


if __name__ == "__main__":
    unittest.main()
