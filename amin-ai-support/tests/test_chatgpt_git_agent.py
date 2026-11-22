"""End-to-end OFFLINE tests: real GitHub tool state changes through fake adapter.

These tests certify tool orchestration and isolation, NOT live ChatGPT login
or actual GitHub writes. Production route does not expose mock transport.
"""
from __future__ import annotations

import base64
import json
import unittest

from chatgpt_git_agent import run_agent, sse_completed_response
from chatgpt_plan_direct import PlanConnectionUnavailable
from github_agent_tools import (
    AgentToolError, ScopedGitHubAgent, checked_path, tool_namespace
)

SHA0 = "a"*40
SHA1 = "b"*40
SHA2 = "c"*40


class FakeGitHub:
    def __init__(self, name="myowner/privateapp", private=True):
        self.name, self.private = name, private
        self.calls = []
        self.branch = False
        self.pr = None
        self.file = {"content": "old\n", "sha": SHA0}
        self.otherfiles = {}
        self.status = "completed"
        self.conclusion = "success"

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path == "":
            return {"full_name": self.name, "private": self.private,
                    "default_branch": "main"}
        if method == "GET" and path == "/git/ref/heads/main":
            return {"object": {"sha": SHA0}}
        if method == "POST" and path == "/git/refs":
            assert payload["sha"] == SHA0
            self.branch = True
            return {"ref": payload["ref"]}
        if method == "GET" and path.startswith("/git/ref/heads/amin-ai-plan/"):
            return {"object": {"sha": SHA2}}
        if method == "GET" and path.startswith("/contents/README.md?ref="):
            return {"type": "file", "encoding": "base64", "sha": self.file["sha"],
                    "content": base64.b64encode(self.file["content"].encode()).decode()}
        if method == "GET" and path.startswith("/contents/new.py?ref="):
            if "new.py" not in self.otherfiles:
                raise RuntimeError("GitHub access failed (HTTP 404)")
            item = self.otherfiles["new.py"]
            return {"type": "file", "encoding": "base64", "sha": item["sha"],
                    "content": base64.b64encode(item["content"].encode()).decode()}
        if method == "PUT" and path == "/contents/README.md":
            assert payload["branch"].startswith("amin-ai-plan/")
            assert payload["sha"] == self.file["sha"]
            self.file = {"content": base64.b64decode(payload["content"]).decode(),
                         "sha": SHA1}
            return {"commit": {"sha": SHA2}, "content": {"sha": SHA1}}
        if method == "PUT" and path == "/contents/new.py":
            assert payload["branch"].startswith("amin-ai-plan/")
            assert "sha" not in payload
            self.otherfiles["new.py"] = {
                "content": base64.b64decode(payload["content"]).decode(), "sha": SHA1}
            return {"commit": {"sha": SHA2}, "content": {"sha": SHA1}}
        if method == "POST" and path == "/pulls":
            assert payload["draft"] is True
            assert payload["base"] == "main"
            assert payload["head"].startswith("amin-ai-plan/")
            self.pr = payload
            return {"number": 44, "html_url": "https://github.com/myowner/privateapp/pull/44"}
        if method == "GET" and path.startswith("/actions/runs?head_sha="):
            return {"workflow_runs": [
                {"id": 123, "name": "CI", "status": self.status,
                 "conclusion": self.conclusion}]}
        if method == "GET" and path.startswith("/contents?ref="):
            return [{"path": "README.md", "type": "file", "size": 4},
                    {"path": ".env", "type": "file", "size": 20}]
        raise AssertionError(f"Unexpected GitHub request {method} {path}")


class FakeResponses:
    def __init__(self):
        self.round = 0
        self.checked = False

    def __call__(self, payload, bearer):
        assert bearer == "OFFLINE_TEST_ONLY"
        assert payload["store"] is False and payload["stream"] is True
        assert payload.get("previous_response_id") is None
        assert payload["tools"][0]["type"] == "namespace"
        assert payload["tools"][0]["name"] == "github"
        self.round += 1
        def call(cid, name, args):
            return {"type": "function_call", "call_id": cid,
                    "name": name, "arguments": json.dumps(args)}
        if self.round == 1:
            assert payload["input"][0]["role"] == "user"
            output = [call("call_read", "github.read_file", {"path": "README.md"})]
        elif self.round == 2:
            assert any(x.get("type") == "function_call_output" for x in payload["input"])
            read_result = next(x for x in payload["input"]
                               if x.get("call_id") == "call_read" and
                               x.get("type") == "function_call_output")
            result = json.loads(read_result["output"])
            assert result["ok"] and result["result"]["content"] == "old\n"
            output = [call("call_branch", "github.create_branch", {})]
        elif self.round == 3:
            output = [call("call_edit", "github.write_file",
                           {"path": "README.md", "content": "new\n",
                            "expected_sha": SHA0, "message": "Update intro"})]
        elif self.round == 4:
            output = [call("call_pr", "github.create_pull_request",
                           {"title": "Improve README", "body": "One file updated. Not deployed."})]
        elif self.round == 5:
            output = [call("call_ci", "github.check_ci", {})]
        elif self.round == 6:
            output = [{"type": "message", "role": "assistant",
                       "content": [{"type": "output_text",
                                    "text": "فایل تغییر کرد و PR پیش‌نویس ایجاد شد؛ نصب انجام نشده."}]}]
        else:
            raise AssertionError("Agent exceeded expected rounds")
        return {"status": "completed", "output": output}


class GitHubAgentTests(unittest.TestCase):
    def bridge(self, rid="1"*32, allow_write=True, repo=None, allow_public=False):
        fake = repo or FakeGitHub()
        agent = ScopedGitHubAgent(fake.name, "not-a-real-token", rid,
                                  allow_write=allow_write,
                                  allow_public=allow_public, bridge=fake)
        return agent, fake

    def test_actual_tool_transitions_and_draft_pr_not_merge(self):
        fake = FakeGitHub()
        result = run_agent(
            "Improve README", fake.name, "not-a-token", "1"*32,
            allow_write=True, transport=FakeResponses(), bridge=fake)
        self.assertEqual(fake.file["content"], "new\n")
        self.assertTrue(fake.branch)
        self.assertIsNotNone(fake.pr)
        self.assertEqual(result["pr_number"], 44)
        self.assertEqual(result["status"], "draft_pr_created")
        self.assertEqual(result["changed_files"], ["README.md"])
        self.assertFalse(result["tests_passed"])
        self.assertFalse(result["model_used"])
        self.assertTrue(result["simulation"])
        self.assertFalse(result["action_performed"])
        self.assertFalse(result["deployed"])
        self.assertFalse(result["merged"])
        self.assertFalse(result["installed"])
        self.assertEqual(result["rounds"], 6)
        self.assertFalse(any(p == "/merges" or m == "DELETE" for m, p, _ in fake.calls))

    def test_read_only_agent_cannot_write_or_create_branch(self):
        agent, fake = self.bridge(allow_write=False)
        allowed = tool_namespace(False)[0]["tools"]
        self.assertNotIn("write_file", {x["name"] for x in allowed})
        self.assertEqual(agent.execute("github.read_file", {"path": "README.md"})["sha"], SHA0)
        for action, args in (("github.write_file",
                              {"path":"README.md", "content":"bad",
                               "expected_sha":SHA0, "message":"Overwrite"}),
                             ("github.create_branch", {})):
            with self.assertRaises(AgentToolError):
                agent.execute(action, args)
        self.assertFalse(fake.branch)

    def test_stale_file_sha_is_rejected(self):
        agent, fake = self.bridge()
        with self.assertRaisesRegex(AgentToolError, "Stale SHA"):
            agent.write_file("README.md", "hi", SHA1, "Change")
        self.assertEqual(fake.file["content"], "old\n")
        self.assertIsNone(fake.pr)

    def test_rejects_secrets_workflows_and_traversal(self):
        for path in (".env", ".env.local", "../secrets.txt", "/etc/passwd",
                     ".github/workflows/test.yml", ".github/actions/step",
                     "config/private_key.pem", "stuff//script.py", ".ssh/config",
                     "folder/../secret.txt"):
            with self.subTest(path=path), self.assertRaises(AgentToolError):
                checked_path(path)
        agent, fake = self.bridge()
        with self.assertRaises(AgentToolError):
            agent.execute("github.read_file", {"path": ".env"})
        self.assertFalse(fake.branch)

    def test_one_branch_per_job_and_no_cross_repo_call(self):
        agent1, fake1 = self.bridge("1"*32)
        agent2, fake2 = self.bridge("2"*32)
        self.assertNotEqual(agent1.branch, agent2.branch)
        agent1.create_branch()
        agent2.create_branch()
        self.assertNotEqual(fake1.calls[-1][2]["ref"], fake2.calls[-1][2]["ref"])
        with self.assertRaisesRegex(AgentToolError, "does not match"):
            ScopedGitHubAgent("otheruser/another", "fake", "3"*32,
                              bridge=FakeGitHub())

    def test_public_repo_requires_explicit_permission(self):
        fake = FakeGitHub(private=False)
        with self.assertRaisesRegex(AgentToolError, "Public"):
            self.bridge(repo=fake)
        agent, _ = self.bridge(repo=fake, allow_public=True)
        self.assertFalse(agent.private)

    def test_existing_file_requires_sha_new_file_requires_empty_sha(self):
        agent, fake = self.bridge()
        with self.assertRaisesRegex(AgentToolError, "Stale SHA"):
            agent.write_file("README.md", "overwrite", "", "oops")
        out = agent.write_file("new.py", "x = 1\n", "", "Add module")
        self.assertTrue(out["source_changed"])
        self.assertIn("new.py", fake.otherfiles)
        with self.assertRaisesRegex(AgentToolError, "Stale SHA"):
            agent.write_file("new.py", "x = 2\n", "", "Change module")

    def test_model_stream_must_complete_before_tools_are_executed(self):
        incomplete = [
            'data: '+json.dumps({"type": "response.output_item.done",
                  "item": {"type": "function_call", "name": "github.write_file",
                           "call_id":"c", "arguments":"{}"}})+'\n\n'
        ]
        with self.assertRaisesRegex(PlanConnectionUnavailable, "without response.completed"):
            sse_completed_response(incomplete)
        completed = [
            'data: '+json.dumps({"type": "response.completed",
                "response": {"status": "completed", "output": []}})+'\n\n'
        ]
        self.assertEqual(sse_completed_response(completed)["output"], [])

    def test_subscription_failure_after_partial_stream_denies_tools(self):
        chunks = [
            'data: '+json.dumps({"type": "response.output_item.done",
               "item": {"type": "function_call", "name": "github.write_file"}})+'\n\n',
            'data: '+json.dumps({"type":"response.failed",
                "response":{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}})+'\n\n'
        ]
        with self.assertRaisesRegex(PlanConnectionUnavailable, "subscription_sharing_usage_limit_exceeded"):
            sse_completed_response(chunks)


if __name__ == "__main__":
    unittest.main()
