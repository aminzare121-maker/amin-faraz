#!/usr/bin/env python3
"""Measure a *live model* against selected facts in actual GitHub project documents.

No invented customer success: this is a small developer-only pilot, NOT evidence of
release readiness. The reference texts are checked out from the actual repository.
They are passed only to a disposable local model; never printed to CI logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from time import monotonic

from amin_support import SupportEngine
from model_probe import validate_base_url

# A reviewer must re-check the reference docs if their quoted anchors change.
BENCHMARK = (
    {
        "id": "faraz_no_live_trade", "project": "faraz",
        "question": "طبق سند فراز، آیا انجام معامله واقعی مجاز است؟",
        "source": "FARAZ_STATUS_AND_HANDOFF_FA.md",
        "doc_anchor": "هیچ معامله واقعی",
        "answer_regex": r"(?:مجاز\s+نیست|ممنوع|اجازه\s+ندارد|خیر|نباید)",
    },
    {
        "id": "faraz_15_minute_data", "project": "faraz",
        "question": "در هدف پروژه فراز داده تاریخی XAUUSD با کندل چند دقیقه‌ای خواسته شده است؟",
        "source": "FARAZ_STATUS_AND_HANDOFF_FA.md",
        "doc_anchor": "۱۵ دقیقه‌ای",
        "answer_regex": r"(?:۱۵|15)\s*(?:دقیقه|دقیقه‌ای|minute|m)",
    },
    {
        "id": "artin_video_engine", "project": "artin",
        "question": "شناسه ثبت‌شده پردازشگر فیلم و کلاس در مخزن ابزارها چیست؟",
        "source": "INDEX_FA.md",
        "doc_anchor": "VIDEO-001",
        "answer_regex": r"VIDEO-001(?!-V13)",
    },
    {
        "id": "artin_v13_not_operational", "project": "artin",
        "question": "آیا ابزار آزمایشی VIDEO-001-V13 عملیاتی و ادغام‌شده است؟",
        "source": "INDEX_FA.md",
        "doc_anchor": "عملیاتی و ادغام‌نشده",
        "answer_regex": r"(?:عملیاتی\s+(?:و\s+)?(?:نیست|نشده)|ادغام[\s‌-]*نشده|تأیید[\s‌-]*نشده|تایید[\s‌-]*نشده|خیر|هنوز\s+.*نیست)",
    },
    {
        "id": "no_cross_project_dukas", "project": "artin",
        "question": "Dukascopy",
        "expected": "escalation",
    },
)


def score_case(case: dict, answer: dict) -> dict:
    sources = answer.get("sources", [])
    if case.get("expected") == "escalation":
        passed = (bool(answer.get("needs_human")) and not answer.get("model_used")
                  and not sources)
        return {
            "case_id": case["id"], "project": case["project"], "type": "escalation",
            "passed": bool(passed), "model_used": bool(answer.get("model_used")),
            "needs_human": bool(answer.get("needs_human")),
            "source_paths": [x["path"] for x in sources],
        }
    fact_found = bool(re.search(case["answer_regex"], answer.get("answer", ""),
                                flags=re.IGNORECASE))
    correct_source = any(s["path"] == case["source"] for s in sources)
    accepted = bool(answer.get("model_used"))
    passed = fact_found and correct_source and accepted and not answer.get("needs_human")
    return {
        "case_id": case["id"], "project": case["project"], "type": "documented_fact",
        "passed": bool(passed), "model_used": accepted, "fact_pattern_matched": fact_found,
        "correct_source_retrieved": correct_source,
        "needs_human": bool(answer.get("needs_human")),
        "source_paths": [x["path"] for x in sources],
    }


def evaluate(faraz_file: Path, artin_file: Path) -> dict:
    files = {"faraz": faraz_file, "artin": artin_file}
    for project, path in files.items():
        if not path.is_file() or path.stat().st_size < 100 or path.stat().st_size > 150_000:
            raise ValueError("Missing or oversized versioned reference file for " + project)
    docs = {p: f.read_text(encoding="utf-8") for p, f in files.items()}
    for case in BENCHMARK:
        anchor = case.get("doc_anchor")
        if anchor and anchor not in docs[case["project"]]:
            raise ValueError("Benchmark requires reference review: " + case["id"])
    model = os.environ.get("AMIN_MODEL_NAME", "")
    endpoint = os.environ.get("AMIN_MODEL_BASE_URL", "")
    if not model or not endpoint:
        raise ValueError("Live model endpoint has not been configured")
    validate_base_url(endpoint)

    with tempfile.TemporaryDirectory(prefix="amin-actual-doc-benchmark-") as tmp:
        root = Path(tmp)
        settings = {"projects": []}
        for project, file in files.items():
            source = root / project
            source.mkdir()
            # Keep the canonical repository path regardless of the temporary
            # download filename chosen by the CI runner.
            canonical_name = ("FARAZ_STATUS_AND_HANDOFF_FA.md"
                              if project == "faraz" else "INDEX_FA.md")
            (source / canonical_name).write_text(docs[project], encoding="utf-8")
            settings["projects"].append({
                "id": project, "name": project,
                "source_prefixes": [canonical_name], "public_paths": [],
            })
        cfg = root / "projects.json"
        cfg.write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
        engine = SupportEngine(cfg, root / "kb.sqlite3")
        ingestion = {p["id"]: engine.knowledge.ingest(p, root / p["id"])
                     for p in settings["projects"]}
        cases = []
        for case in BENCHMARK:
            started = monotonic()
            # Only trusted-local developer mode can use the engineering docs.
            result = engine.answer(case["project"], case["question"], role="developer")
            scored = score_case(case, result)
            scored["latency_seconds"] = round(monotonic() - started, 2)
            cases.append(scored)

    passed = sum(case["passed"] for case in cases)
    total = len(cases)
    rate = passed / total if total else 0.0
    return {
        "dataset": "real_git_document_excerpt_pilot",
        "provenance": {
            p: {"doc": str(files[p]), "sha256": hashlib.sha256(
                files[p].read_bytes()).hexdigest(), "indexed_passages": ingestion[p]["passages"]}
            for p in files
        },
        "model_name": model, "model_called": True,
        "source_policy": "developer_only_local_model",
        "not_customer_acceptance": True,
        "not_production_ready": True,
        "min_target_pass_rate": 0.85,
        "measured_pass_rate": round(rate, 4),
        "target_met_on_pilot": bool(rate >= 0.85),
        "cases_passed": passed, "cases_total": total,
        "case_details": cases,
        "caveat": ("A five-case pilot on real developer docs is not a representative "
                   "sample of live customer support; actual deployment needs independent review.")
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--faraz-doc", type=Path, required=True)
    parser.add_argument("--artin-doc", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="Exit nonzero unless at least 85 percent of pilot cases pass")
    args = parser.parse_args(argv)
    result = evaluate(args.faraz_doc, args.artin_doc)
    message = json.dumps(result, ensure_ascii=False, indent=2)
    print(message, flush=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(message + "\n", encoding="utf-8")
    if args.strict and not result["target_met_on_pilot"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
