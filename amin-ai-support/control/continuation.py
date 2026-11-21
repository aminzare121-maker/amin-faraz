#!/usr/bin/env python3
"""Amin continuation controller: deterministic, evidence-gated next-step suggestions.

Input: AMIN_REPORT_V1 + JSON in an OWNER-authored GitHub issue comment.
Output: AMIN_DIRECTIVE_V1 + JSON as a *suggestion* in the same issue.
This is not an LLM, ChatGPT hook, or autonomous executor.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent
POLICY = BASE / "policy.json"
REPORT_TAG = "AMIN_REPORT_V1"
DIRECTIVE_TAG = "AMIN_DIRECTIVE_V1"
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,79}$")


class ProtocolError(ValueError):
    pass


def policy_data():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def parse_report(body: str, policy: dict) -> dict:
    if not isinstance(body, str) or len(body) > 5000:
        raise ProtocolError("Invalid report length")
    if not body.startswith(REPORT_TAG + "\n"):
        raise ProtocolError("Not a continuation report")
    try:
        item = json.loads(body[len(REPORT_TAG) + 1:])
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ProtocolError("Invalid JSON report") from exc
    if not isinstance(item, dict):
        raise ProtocolError("Report must be a JSON object")
    for field in ("report_id", "project", "phase", "status", "summary"):
        if not isinstance(item.get(field), str):
            raise ProtocolError("Missing or invalid " + field)
    if not ID_PATTERN.fullmatch(item["report_id"]):
        raise ProtocolError("Unsafe report identifier")
    if item["project"] not in policy["allowed_projects"]:
        raise ProtocolError("Unknown project")
    if item["phase"] not in [x["id"] for x in policy["phases"]]:
        raise ProtocolError("Unknown phase")
    if item["status"] not in {"passed", "failed", "blocked", "in_progress"}:
        raise ProtocolError("Unknown status")
    if not 5 <= len(item["summary"].strip()) <= 1200:
        raise ProtocolError("Summary must contain 5-1200 characters")
    if "blocker" in item and not isinstance(item["blocker"], str):
        raise ProtocolError("Invalid blocker")
    if len(item.get("blocker", "")) > 300:
        raise ProtocolError("Blocker too long")
    sha = item.get("commit_sha")
    if sha is not None and (not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha)):
        raise ProtocolError("Invalid commit SHA")
    run = item.get("ci_run_id")
    if run is not None and (type(run) is not int or run <= 0):
        raise ProtocolError("Invalid CI run ID")
    return item


def verify_ci(report: dict, policy: dict, opener=None) -> bool:
    """Only verified success on same commit counts as CI evidence, not task completion."""
    sha, run_id = report.get("commit_sha"), report.get("ci_run_id")
    if not sha or not run_id:
        return False
    if opener is None:
        opener = urlopen
    repo = "aminzare121-maker/amin-faraz"
    token = os.environ.get("GH_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "amin-continuation-controller/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request("https://api.github.com/repos/" + repo +
                      "/actions/runs/" + str(run_id), headers=headers)
    try:
        with opener(request, timeout=12) as response:
            result = json.load(response)
    except (OSError, ValueError, KeyError):
        return False
    return (result.get("conclusion") == "success" and
            result.get("status") == "completed" and
            result.get("head_sha") == sha and
            result.get("repository", {}).get("full_name") == repo)


def decide(report: dict, policy: dict, ci_verified: bool = False) -> dict:
    phases = policy["phases"]
    ids = [x["id"] for x in phases]
    stage = ids.index(report["phase"])
    current = phases[stage]
    status = report["status"]
    guard = policy["projects"][report["project"]]["guard"]
    if status == "failed":
        action = ("آخرین شکست را از گزارش/لاگ واقعی پیدا کن، علت را جدا کن، "
                  "فقط همان نقص را در شاخه جداگانه اصلاح کن و دوباره آزمایش بگیر.")
        classification, next_phase = "repair", current["id"]
        rationale = "شکست آزمون، اجازه عبور به مرحله بعد نمی‌دهد."
    elif status == "blocked":
        action = ("مانع ثبت‌شده را با ابزارهای فعلی و بدون درخواست خرید بررسی کن؛ "
                  "اگر مانع دسترسی/مجوز واقعی باقی بود، دقیق ثبت کن و اقدام ساختگی انجام نده.")
        classification, next_phase = "blocked", current["id"]
        rationale = "پیشروی بدون رفع مانع واقعی قابل تأیید نیست."
    elif status == "in_progress":
        action = current["action"]
        classification, next_phase = "continue", current["id"]
        rationale = "مرحله هنوز کامل نشده و باید از همین نقطه ادامه یابد."
    elif not ci_verified:
        action = ("مدرک مستقل آزمون را برای همین commit ارائه و از GitHub Actions "
                  "تأیید کن؛ تا قبل از آن ادعای قبولی یا عبور از مرحله نکن.")
        classification, next_phase = "verify", current["id"]
        rationale = "ادعای قبولی بدون CI موفقِ منطبق با commit تأیید نمی‌شود."
    elif stage == len(ids) - 1:
        action = ("گزارش جمع‌بندی شواهد قبولی، آزمون واقعی کاربران، ریسک‌ها و مجوزها را آماده کن؛ "
                  "بدون تأیید مالک، نسخه عمومی منتشر نکن.")
        classification, next_phase = "owner_review", current["id"]
        rationale = "موفقیت CI استقرار یا قبولی محصول را اثبات نمی‌کند."
    else:
        next_phase = phases[stage + 1]["id"]
        action = phases[stage + 1]["action"]
        classification = "next_candidate"
        rationale = ("آزمون CI مرتبط با commit موفق بوده است؛ این فقط پیشنهاد "
                     "بررسی مرحله بعد است، نه تأیید نهایی کیفیت محصول.")
    return {
        "version": 1, "report_id": report["report_id"], "project": report["project"],
        "decision": classification, "current_phase": report["phase"],
        "next_phase": next_phase, "next_action_fa": action,
        "reason_fa": rationale, "project_guard_fa": guard,
        "ci_verified": bool(ci_verified), "automatically_executed": False,
        "approved_for_production": False,
        "note_fa": "این پاسخ از قواعد ثابت GitHub تولید شده و جایگزین قضاوت یا اجرای ChatGPT نیست."
    }


def from_event(event: dict, policy: dict):
    if event.get("action") != "created":
        raise ProtocolError("Unsupported event")
    if event.get("repository", {}).get("full_name") != "aminzare121-maker/amin-faraz":
        raise ProtocolError("Wrong repository")
    issue = event.get("issue", {})
    comment = event.get("comment", {})
    if (issue.get("number") != policy["controller_issue"] or
            issue.get("title") != policy["controller_title"] or "pull_request" in issue):
        raise ProtocolError("Wrong control issue")
    if (comment.get("user", {}).get("login") != policy["owner"] or
            comment.get("author_association") != "OWNER"):
        raise ProtocolError("Unauthorized sender")
    return parse_report(comment.get("body", ""), policy)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = policy_data()
    if args.event:
        report = from_event(json.loads(args.event.read_text(encoding="utf-8")), policy)
        verified = verify_ci(report, policy)
    elif args.report:
        report = parse_report(args.report.read_text(encoding="utf-8"), policy)
        verified = False  # Offline report cannot claim successful CI.
    else:
        parser.error("Provide --event or --report")
    output = decide(report, policy, verified)
    args.output.write_text(DIRECTIVE_TAG + "\n" +
                           json.dumps(output, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"directive={output['decision']};project={output['project']};"
          f"next_phase={output['next_phase']};ci_verified={verified}")


if __name__ == "__main__":
    main()
