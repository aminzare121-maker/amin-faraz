"""No network integration tests for immediate private GitHub issue actions."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from instant_issue_worker import inspect_event, process, MARKER


class FakeResponse:
    status = 200
    def __init__(self, obj):
        self.data = io.BytesIO(json.dumps(obj).encode("utf-8"))
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return self.data.read(size)


class FakeOpener:
    def __init__(self):
        self.calls = []
        self.comments = []
        self.private = True
    def open(self, request, timeout=20):
        self.calls.append((request.method, request.full_url, request.data))
        route = request.full_url.split("amin-mt5-review", 1)[-1]
        if route == "":
            return FakeResponse({"private": self.private,
                                 "full_name": "aminzare121-maker/amin-mt5-review"})
        if route == "/issues/7/comments?per_page=100":
            return FakeResponse(self.comments)
        if route == "/issues/7/comments" and request.data:
            self.comments.append({"body": json.loads(request.data)["body"],
                                  "user": {"login": "github-actions[bot]"}})
            answer = FakeResponse({"id": 29})
            answer.status = 201
            return answer
        raise AssertionError(f"Unexpected GitHub route {route}")


def event(question="چرا این برنامه پاسخ نمی‌دهد؟"):
    id = "abcdef1234567890abcdef1234567890"
    request = {
        "request_id": id, "project": "support", "device": "android",
        "question": question, "consent": True, "result_required": "AMIN_CHAT_REPLY_V1"
    }
    return {
        "action": "opened",
        "repository": {
            "private": True,
            "full_name": "aminzare121-maker/amin-mt5-review",
            "owner": {"login": "aminzare121-maker"}
        },
        "issue": {
            "number": 7,
            "title": "[Amin private support] " + id[:12],
            "user": {"login": "aminzare121-maker"},
            "body": MARKER + json.dumps(request, ensure_ascii=False)
        }
    }


class PrivateOnDemandTests(unittest.TestCase):
    REPO = "aminzare121-maker/amin-mt5-review"

    def test_valid_private_request(self):
        result = inspect_event(event(), self.REPO)
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 7)

    def test_unsafe_events_are_not_accepted(self):
        data = event()
        for target, value in [
            (("repository", "private"), False),
            (("repository", "full_name"), "other/repo"),
            (("issue", "user"), {"login": "stranger"}),
            (("issue", "title"), "Other task"),
            (("issue", "body"), "AMIN_CHAT_BRIDGE_V1\nnot json"),
        ]:
            changed = json.loads(json.dumps(data))
            changed[target[0]][target[1]] = value
            self.assertIsNone(inspect_event(changed, self.REPO), target)
        changed = event()
        changed["issue"]["body"] = changed["issue"]["body"].replace('"consent": true', '"consent": false')
        self.assertIsNone(inspect_event(changed, self.REPO))

    def test_events_publish_documented_reply_once(self):
        opener = FakeOpener()
        with patch("instant_issue_worker.build_reply", return_value={
            "answer": "مستندات مربوط به خطا بررسی شد.",
            "needs_human": False, "sources": []}):
            one = process(event(), self.REPO, "fake-token", Path("."), opener)
            self.assertTrue(one["processed"])
            self.assertFalse(one["chatgpt_invoked"])
            two = process(event(), self.REPO, "fake-token", Path("."), opener)
            self.assertEqual(two["reason"], "already_replied")
        payload = json.loads(opener.comments[0]["body"].split("\n", 1)[1])
        self.assertFalse(payload["action_performed"])
        self.assertFalse(payload["chatgpt_invoked"])
        self.assertIn("بدون استفاده از مدل ChatGPT", payload["answer"])
        self.assertEqual(len(opener.comments), 1)

    def test_public_repo_no_reply_even_if_event_spoofed(self):
        opener = FakeOpener()
        opener.private = False
        result = process(event(), self.REPO, "fake-token", Path("."), opener)
        self.assertFalse(result["processed"])
        self.assertFalse(opener.comments)


if __name__ == "__main__":
    unittest.main()
