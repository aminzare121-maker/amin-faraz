import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from continuation import (REPORT_TAG, ProtocolError,
                          decide, from_event, parse_report, policy_data, verify_ci)


class FakeResponse:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return io.BytesIO(json.dumps(self.data).encode())
    def __exit__(self, *args):
        return False


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy_data()
        self.report = {
            "report_id": "support-cycle-0001",
            "project": "support", "phase": "knowledge",
            "status": "in_progress", "summary": "در حال جمع‌آوری سوابق GitHub"
        }

    def body(self, report=None):
        return REPORT_TAG + "\n" + json.dumps(report or self.report, ensure_ascii=False)

    def event(self, body=None):
        return {
            "action": "created",
            "repository": {"full_name": "aminzare121-maker/amin-faraz"},
            "issue": {"number": 68,
                      "title": "AMIN-CONTINUATION-CONTROL — فرمان‌دهی پروژه‌ها"},
            "comment": {"user": {"login": "aminzare121-maker"},
                        "author_association": "OWNER",
                        "body": body or self.body()},
        }

    def test_all_project_profiles(self):
        self.assertEqual(len(self.policy["allowed_projects"]), 6)
        for project in self.policy["allowed_projects"]:
            report = dict(self.report, project=project)
            self.assertEqual(parse_report(self.body(report), self.policy)["project"], project)

    def test_valid_event_continues_same_phase(self):
        report = from_event(self.event(), self.policy)
        directive = decide(report, self.policy)
        self.assertEqual(directive["decision"], "continue")
        self.assertEqual(directive["next_phase"], "knowledge")
        self.assertFalse(directive["automatically_executed"])

    def test_failed_never_advances(self):
        report = dict(self.report, status="failed")
        directive = decide(report, self.policy, ci_verified=True)
        self.assertEqual(directive["decision"], "repair")
        self.assertEqual(directive["next_phase"], "knowledge")

    def test_blocked_never_advances(self):
        report = dict(self.report, status="blocked", blocker="GitHub rate limit")
        directive = decide(report, self.policy, ci_verified=True)
        self.assertEqual(directive["decision"], "blocked")
        self.assertFalse(directive["approved_for_production"])

    def test_pass_without_matching_ci_never_advances(self):
        report = dict(self.report, status="passed")
        directive = decide(report, self.policy, ci_verified=False)
        self.assertEqual(directive["decision"], "verify")
        self.assertEqual(directive["next_phase"], "knowledge")

    def test_pass_with_verified_ci_gives_candidate_next_phase(self):
        report = dict(self.report, status="passed")
        directive = decide(report, self.policy, ci_verified=True)
        self.assertEqual(directive["decision"], "next_candidate")
        self.assertEqual(directive["next_phase"], "intelligence")
        self.assertFalse(directive["approved_for_production"])

    def test_deployment_still_requires_owner_review(self):
        report = dict(self.report, phase="deployment", status="passed")
        directive = decide(report, self.policy, ci_verified=True)
        self.assertEqual(directive["decision"], "owner_review")

    def test_control_issue_and_owner_restrictions(self):
        event = self.event()
        event["comment"]["user"]["login"] = "untrusted-user"
        with self.assertRaises(ProtocolError):
            from_event(event, self.policy)
        event = self.event()
        event["comment"]["author_association"] = "CONTRIBUTOR"
        with self.assertRaises(ProtocolError):
            from_event(event, self.policy)
        event = self.event()
        event["issue"]["number"] = 99
        with self.assertRaises(ProtocolError):
            from_event(event, self.policy)
        event = self.event()
        event["issue"]["pull_request"] = {}
        with self.assertRaises(ProtocolError):
            from_event(event, self.policy)

    def test_invalid_protocol_rejected(self):
        for body in ['AMIN_DIRECTIVE_V1\n{}', 'AMIN_REPORT_V1\nnot-json',
                     'AMIN_REPORT_V1\n[]', self.body(dict(self.report, project="../evil")),
                     self.body(dict(self.report, status="magic")),
                     self.body(dict(self.report, phase="unknown")),
                     self.body(dict(self.report, report_id="x"))]:
            with self.assertRaises(ProtocolError, msg=body[:40]):
                parse_report(body, self.policy)

    def test_verified_run_checks_same_sha_and_repo(self):
        sha = "a" * 40
        report = dict(self.report, commit_sha=sha, ci_run_id=123)
        good = {
            "status": "completed", "conclusion": "success", "head_sha": sha,
            "repository": {"full_name": "aminzare121-maker/amin-faraz"}}
        self.assertTrue(verify_ci(report, self.policy, opener=lambda req, timeout: FakeResponse(good)))
        for patchval in [
            {"head_sha": "b" * 40},
            {"conclusion": "failure"},
            {"repository": {"full_name": "another/repo"}},
            {"status": "in_progress"}
        ]:
            bad = dict(good, **patchval)
            self.assertFalse(verify_ci(report, self.policy, opener=lambda req, timeout: FakeResponse(bad)))

    def test_no_ci_run_means_no_ci_verification(self):
        self.assertFalse(verify_ci(self.report, self.policy))

    def test_default_policy_has_distinct_project_guards(self):
        self.assertNotEqual(self.policy["projects"]["artin"]["guard"],
                            self.policy["projects"]["faraz"]["guard"])


if __name__ == "__main__":
    unittest.main()
