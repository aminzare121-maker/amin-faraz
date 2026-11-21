import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from continuation import ProtocolError, policy_data
from javab import (TASK_TAG, REPORT_TAG, parse_report, directive_for, parse_task)


class JavabTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy_data()

    def event(self, number=101, project="faraz", status="in_progress",
              state="open", owner="aminzare121-maker", goal_met=False):
        task = {
            "task_id": number,
            "project": project,
            "goal": f"توسعه واقعی و آزمایش مستقل برنامه شماره {number} تا نتیجه مشخص",
            "success_criteria": "آزمون واقعی تکرارپذیر، گزارش شواهد و تأیید مالک"
        }
        report = {
            "report_id": f"task-{number}-20261122-01",
            "task_id": number, "project": project, "phase": "diagnostics",
            "status": status, "summary": "بررسی کد و آزمایش مرحله فعلی",
            "goal_met": goal_met
        }
        event = {
            "action": "created",
            "repository": {"full_name": "aminzare121-maker/amin-faraz"},
            "issue": {
                "number": number,
                "title": f"برنامه جواب | وظیفه مستقل {number}",
                "state": state,
                "user": {"login": owner},
                "body": TASK_TAG + "\n" + json.dumps(task, ensure_ascii=False)
            },
            "comment": {
                "user": {"login": "aminzare121-maker"},
                "author_association": "OWNER",
                "body": REPORT_TAG + "\n" + json.dumps(report, ensure_ascii=False)
            }
        }
        return event

    def test_independent_tasks_get_independent_directives(self):
        task1, report1 = parse_report(self.event(101, "faraz", "failed"), self.policy)
        task2, report2 = parse_report(self.event(102, "artin", "in_progress"), self.policy)
        a = directive_for(task1, report1, self.policy, False)
        b = directive_for(task2, report2, self.policy, False)
        self.assertEqual(a["task_id"], 101)
        self.assertEqual(b["task_id"], 102)
        self.assertEqual(a["decision"], "repair")
        self.assertEqual(b["decision"], "continue")
        self.assertNotEqual(a["project_guard_fa"], b["project_guard_fa"])
        self.assertNotEqual(a["goal_fa"], b["goal_fa"])

    def test_stop_by_closing_issue_prevents_new_directives(self):
        with self.assertRaises(ProtocolError):
            parse_report(self.event(state="closed"), self.policy)

    def test_report_cannot_cross_task_issue(self):
        event = self.event(number=101)
        body = json.loads(event["comment"]["body"].split("\n", 1)[1])
        body["task_id"] = 102
        event["comment"]["body"] = REPORT_TAG + "\n" + json.dumps(body)
        with self.assertRaises(ProtocolError):
            parse_report(event, self.policy)

    def test_report_cannot_cross_projects(self):
        event = self.event(number=101, project="faraz")
        body = json.loads(event["comment"]["body"].split("\n", 1)[1])
        body["project"] = "artin"
        event["comment"]["body"] = REPORT_TAG + "\n" + json.dumps(body)
        with self.assertRaises(ProtocolError):
            parse_report(event, self.policy)

    def test_owner_only_issues_and_reports(self):
        with self.assertRaises(ProtocolError):
            parse_report(self.event(owner="external-user"), self.policy)
        event = self.event()
        event["comment"]["user"]["login"] = "external-user"
        with self.assertRaises(ProtocolError):
            parse_report(event, self.policy)

    def test_issue_must_have_goal_acceptance_and_matching_id(self):
        event = self.event()
        issue = event["issue"]
        for key, bad in [("goal", "x"), ("success_criteria", ""),
                         ("task_id", 666), ("project", "unregistered")]:
            original = json.loads(issue["body"].split("\n", 1)[1])
            original[key] = bad
            issue["body"] = TASK_TAG + "\n" + json.dumps(original)
            with self.assertRaises(ProtocolError, msg=key):
                parse_task(issue, self.policy)
            issue["body"] = TASK_TAG + "\n" + json.dumps(
                json.loads(self.event()["issue"]["body"].split("\n", 1)[1]))

    def test_completed_claim_is_not_automatic_stop(self):
        task, report = parse_report(self.event(goal_met=True, status="passed"), self.policy)
        answer = directive_for(task, report, self.policy, ci_verified=True)
        self.assertEqual(answer["decision"], "owner_acceptance_review")
        self.assertFalse(answer["accepted_as_complete"])
        self.assertFalse(answer["suggested_auto_stop"])
        self.assertFalse(answer["approved_for_production"])

    def test_goal_claim_without_ci_is_not_done(self):
        task, report = parse_report(self.event(goal_met=True, status="passed"), self.policy)
        answer = directive_for(task, report, self.policy, ci_verified=False)
        self.assertEqual(answer["decision"], "verify_goal_claim")
        self.assertFalse(answer["accepted_as_complete"])

    def test_invalid_report_and_wrong_prefix_rejected(self):
        event = self.event()
        event["issue"]["title"] = "Unrelated project"
        with self.assertRaises(ProtocolError):
            parse_report(event, self.policy)
        event = self.event()
        event["comment"]["body"] = "JAVAB_DIRECTIVE_V1\n{}"
        with self.assertRaises(ProtocolError):
            parse_report(event, self.policy)

    def test_report_failure_does_not_skip_phase(self):
        task, report = parse_report(self.event(status="failed"), self.policy)
        reply = directive_for(task, report, self.policy, ci_verified=True)
        self.assertEqual(reply["next_phase"], "diagnostics")


if __name__ == "__main__":
    unittest.main()
