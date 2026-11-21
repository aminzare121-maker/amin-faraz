#!/usr/bin/env python3
"""برنامه جواب: per-task, issue-scoped, rule-based next-step coordinator.

GitHub is the durable mailbox. It does NOT execute ChatGPT, replace the model,
or guarantee uninterrupted work. Each task has a separate owner-created issue.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from continuation import decide, policy_data, verify_ci, ProtocolError

TASK_TAG = "JAVAB_TASK_V1"
REPORT_TAG = "JAVAB_REPORT_V1"
DIRECTIVE_TAG = "JAVAB_DIRECTIVE_V1"
TITLE_PREFIX = "برنامه جواب | "
OWNER = "aminzare121-maker"
REPO = "aminzare121-maker/amin-faraz"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,79}$")
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")
STATUSES = {"in_progress", "failed", "blocked", "passed"}


def tagged_json(raw: str, tag: str, limit: int) -> dict:
    if not isinstance(raw, str) or len(raw) > limit or not raw.startswith(tag + "\n"):
        raise ProtocolError("Unexpected message format")
    try:
        data = json.loads(raw[len(tag) + 1:])
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProtocolError("Invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProtocolError("Expected JSON object")
    return data


def parse_task(issue: dict, policy: dict) -> dict:
    if not isinstance(issue, dict) or not isinstance(issue.get("number"), int):
        raise ProtocolError("Issue number missing")
    if (not isinstance(issue.get("title"), str) or
            not issue["title"].startswith(TITLE_PREFIX) or
            not 1 <= len(issue["title"][len(TITLE_PREFIX):].strip()) <= 100):
        raise ProtocolError("This issue is not an independently named Javab task")
    if issue.get("user", {}).get("login") != OWNER:
        raise ProtocolError("Task must be created by owner")
    if issue.get("state") != "open" or "pull_request" in issue:
        raise ProtocolError("Task has been stopped or is not an issue")
    task = tagged_json(issue.get("body"), TASK_TAG, 6000)
    if task.get("project") not in policy["allowed_projects"]:
        raise ProtocolError("Unrecognized project")
    if (not isinstance(task.get("goal"), str) or
            not 10 <= len(task["goal"].strip()) <= 1500):
        raise ProtocolError("Goal is missing or too long")
    criteria = task.get("success_criteria")
    if (not isinstance(criteria, str) or
            not 8 <= len(criteria.strip()) <= 1500):
        raise ProtocolError("Independent acceptance criteria are required")
    if task.get("task_id") != issue["number"]:
        raise ProtocolError("Task id must equal its own issue number")
    return task


def parse_report(event: dict, policy: dict) -> tuple[dict, dict]:
    if (event.get("action") != "created" or
            event.get("repository", {}).get("full_name") != REPO):
        raise ProtocolError("Not an eligible GitHub event")
    comment = event.get("comment", {})
    if (comment.get("user", {}).get("login") != OWNER or
            comment.get("author_association") != "OWNER"):
        raise ProtocolError("Report author is not repository owner")
    issue = event.get("issue")
    task = parse_task(issue, policy)
    report = tagged_json(comment.get("body"), REPORT_TAG, 5000)
    if report.get("task_id") != issue["number"] or report.get("project") != task["project"]:
        raise ProtocolError("Report cannot cross task or project boundaries")
    if not isinstance(report.get("report_id"), str) or not ID_PATTERN.fullmatch(report["report_id"]):
        raise ProtocolError("Invalid report id")
    if report.get("status") not in STATUSES:
        raise ProtocolError("Invalid status")
    phase = report.get("phase")
    if phase not in [entry["id"] for entry in policy["phases"]]:
        raise ProtocolError("Invalid phase")
    if not isinstance(report.get("summary"), str) or not 5 <= len(report["summary"].strip()) <= 1200:
        raise ProtocolError("Invalid summary")
    if "blocker" in report and (not isinstance(report["blocker"], str) or
                                 len(report["blocker"]) > 300):
        raise ProtocolError("Invalid blocker")
    sha = report.get("commit_sha")
    if sha is not None and (not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha)):
        raise ProtocolError("Invalid commit SHA")
    run_id = report.get("ci_run_id")
    if run_id is not None and (type(run_id) is not int or run_id <= 0):
        raise ProtocolError("Invalid CI run ID")
    if "goal_met" in report and type(report["goal_met"]) is not bool:
        raise ProtocolError("Invalid goal_met flag")
    if "acceptance_evidence" in report and (not isinstance(report["acceptance_evidence"], str)
                                            or len(report["acceptance_evidence"]) > 900):
        raise ProtocolError("Invalid acceptance evidence")
    return task, report


def directive_for(task: dict, report: dict, policy: dict, ci_verified: bool) -> dict:
    result = decide(report, policy, ci_verified)
    result["protocol"] = "JAVAB_V1"
    result["task_id"] = task["task_id"]
    result["goal_fa"] = task["goal"]
    result["acceptance_criteria_fa"] = task["success_criteria"]
    result["task_state"] = "active"
    result["suggested_auto_stop"] = False
    result["accepted_as_complete"] = False
    if report.get("goal_met") is True:
        # A reported goal is a claim, not independent acceptance.
        result["decision"] = "owner_acceptance_review" if ci_verified else "verify_goal_claim"
        result["next_phase"] = report["phase"]
        result["next_action_fa"] = (
            "شواهد نتیجه مطلوب را با معیارهای پذیرش اصلی تطبیق بده؛ برای پایان کار "
            "به تأیید صریح مالک و توقف تسک نیاز است."
            if ci_verified else
            "ادعای تحقق هدف هنوز با آزمون CI منطبق با همین commit تأیید نشده؛ "
            "شواهد واقعی را بررسی کن و پیش از اعلام پایان، آزمون معتبر ثبت کن."
        )
    # Prevent a generic phase transition from claiming the user's unique goal is complete.
    result["note_fa"] = (
        "دستور خودکار فقط یک پیشنهاد قاعده‌محور است. ChatGPT باید در نوبت دارای دسترسی "
        "آن را بخواند و اجرا کند؛ اجرای مداوم، موازی بی‌صف و قبولی نهایی تضمین نمی‌شود."
    )
    result["automatically_executed"] = False
    result["approved_for_production"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description="Javab independent task reply")
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = policy_data()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    task, report = parse_report(event, policy)
    ci_verified = verify_ci(report, policy)
    directive = directive_for(task, report, policy, ci_verified)
    args.output.write_text(DIRECTIVE_TAG + "\n" +
                           json.dumps(directive, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print("issue={};project={};decision={};ci_verified={}".format(
        task["task_id"], task["project"], directive["decision"], ci_verified))


if __name__ == "__main__":
    main()
