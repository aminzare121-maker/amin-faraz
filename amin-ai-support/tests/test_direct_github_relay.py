"""Proof-level tests for public repo refusal, private request, and owner-only answer."""
import io
import json
import unittest
from urllib.request import Request

from direct_github_relay import GitHubPrivateBridge


class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.buffer = io.BytesIO(json.dumps(payload).encode("utf8"))
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, n=-1):
        return self.buffer.read(n)


class FakeOpener:
    def __init__(self, private=True):
        self.private = private
        self.calls = []
        self.issues = {}
        self.comments = {}
    def open(self, req: Request, timeout=20):
        self.calls.append((req.method, req.full_url, req.data))
        url = req.full_url
        if url.endswith("/repos/owner/repo"):
            return FakeResponse({"private": self.private, "full_name": "owner/repo",
                                 "has_issues": True, "owner": {"login": "owner"}})
        if url.endswith("/issues") and req.method == "POST":
            payload = json.loads(req.data.decode("utf8"))
            self.issues[12] = payload
            return FakeResponse({"number": 12})
        if url.endswith("/issues/12"):
            return FakeResponse(self.issues[12])
        if url.endswith("/issues/12/comments?per_page=100"):
            return FakeResponse(self.comments.get(12, []))
        if url.endswith("/issues?state=all&per_page=100"):
            return FakeResponse([{"body": i["body"], "number": n, "created_at": "2026-11-22"}
                                 for n,i in self.issues.items()])
        raise AssertionError("Unexpected " + url)


class PrivateRelayTests(unittest.TestCase):
    TOKEN = "github_pat_" + "x" * 50
    def test_public_repo_never_receives_question(self):
        opener = FakeOpener(private=False)
        bridge = GitHubPrivateBridge("owner/repo", self.TOKEN, opener=opener)
        with self.assertRaisesRegex(RuntimeError, "PUBLIC"):
            bridge.submit("support", "SECRET PRIVATE QUESTION")
        self.assertEqual(len(opener.calls), 1)
        self.assertIsNone(opener.calls[0][2])

    def test_private_issue_answer_from_verified_owner(self):
        opener = FakeOpener()
        bridge = GitHubPrivateBridge("owner/repo", self.TOKEN, opener=opener)
        request = bridge.submit("support", "سؤال اختصاصی آزمایشی")
        self.assertEqual(request["issue_number"], 12)
        self.assertFalse(request["chatgpt_invoked"])
        self.assertIn("سؤال اختصاصی", opener.issues[12]["body"])
        self.assertEqual(bridge.status(12, request["request_id"])["status"], "pending")
        text = "AMIN_CHAT_REPLY_V1\n" + json.dumps({
            "request_id": request["request_id"], "status": "answered",
            "answer": "پاسخ بررسی‌شده"})
        opener.comments[12] = [
            {"user": {"login": "somebody"}, "body": text},
            {"user": {"login": "owner"}, "body": text}]
        self.assertEqual(bridge.status(12, request["request_id"])["answer"], "پاسخ بررسی‌شده")
        self.assertEqual(len(bridge.list_requests()), 1)
        self.assertEqual(bridge.list_requests()[0]["request_id"], request["request_id"])

    def test_cross_issue_id_and_fake_reply_blocked(self):
        opener = FakeOpener()
        bridge = GitHubPrivateBridge("owner/repo", self.TOKEN, opener=opener)
        request = bridge.submit("support", "request")
        with self.assertRaisesRegex(RuntimeError, "mismatch"):
            bridge.status(12, "a" * 32)
        opener.comments[12] = [{"user": {"login": "attacker"},
                                "body": "AMIN_CHAT_REPLY_V1\n" + json.dumps({
                                    "request_id": request["request_id"], "status": "answered",
                                    "answer": "false"})}]
        self.assertEqual(bridge.status(12, request["request_id"])["status"], "pending")

    def test_invalid_token_or_repo(self):
        for repo in ("owner/public/path", "https://github.com/owner/repo", "../bad"):
            with self.assertRaises(ValueError): GitHubPrivateBridge(repo, self.TOKEN)
        with self.assertRaises(ValueError): GitHubPrivateBridge("owner/repo", "ghp_short")


if __name__ == "__main__":
    unittest.main()
