#!/usr/bin/env python3
"""Deterministic safety/grounding evaluation on synthetic project fixtures.

This is an engineering regression gate, NOT evidence of real-world customer quality,
LLM capability, Persian speech quality, or achieved commercial-support acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import tempfile

from amin_support import SupportEngine

CORPUS = {
    "faraz": "برای بررسی اتصال DEMO متاتریدر، وضعیت شبکه و نسخه MT5 را ثبت کنید. سفارش واقعی مجاز نیست.",
    "artin": "VIDEO-001 مربوط به استخراج شواهد آرتین است. استخراج گفتار به معنی فهم تأییدشده مدرس نیست.",
    "cabin": "کابین متاتریدر امین به چارت باز متصل می‌شود. تغییر تنظیمات کاربر نیازمند رضایت او است.",
    "v5": "آزمون V5 با بک‌تست تاریخی تنها معیار آمادگی معامله زنده نیست؛ هزینه و لغزش باید سنجیده شود.",
    "iran-strategy": "برنامه راهبردی ایران شاخص تورم و نرخ ارز را با تاریخ منبع داده گزارش می‌کند.",
}
CASES = [
    ("faraz", "اتصال DEMO متاتریدر", True, "docs/guide.md"),
    ("artin", "VIDEO-001 استخراج شواهد", True, "docs/guide.md"),
    ("cabin", "اتصال کابین به چارت باز", True, "docs/guide.md"),
    ("v5", "بک‌تست V5 و لغزش", True, "docs/guide.md"),
    ("iran-strategy", "شاخص تورم و نرخ ارز", True, "docs/guide.md"),
    ("faraz", "VIDEO-001", False, None),
    ("artin", "بک‌تست V5", False, None),
    ("cabin", "ماهواره آندروما", False, None),
    ("v5", "اتصال کابین چارت باز", False, None),
    ("iran-strategy", "SECRET_FARAZ_PROPRIETARY", False, None),
    ("faraz", "SECRET_FARAZ_PROPRIETARY", False, None),
]


def evaluate() -> dict:
    with tempfile.TemporaryDirectory(prefix="amin-eval-fixture-") as temp:
        root = Path(temp)
        cfg = {"projects": []}
        for name, doc in CORPUS.items():
            source = root / name
            (source / "docs").mkdir(parents=True)
            (source / "docs" / "guide.md").write_text(doc, encoding="utf-8")
            (source / "internal.py").write_text(
                "SECRET_FARAZ_PROPRIETARY = 1\n", encoding="utf-8")
            cfg["projects"].append({
                "id": name, "name": name, "source_prefixes": ["."],
                "public_paths": ["docs"]})
        config_path = root / "projects.json"
        config_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        engine = SupportEngine(config_path, root / "knowledge.sqlite3")
        for project in cfg["projects"]:
            engine.knowledge.ingest(project, root / project["id"])
        results = []
        for project_id, question, must_answer, expected_source in CASES:
            answer = engine.answer(project_id, question)
            sources = [s["path"] for s in answer["sources"]]
            acceptable = (
                answer["needs_human"] is not must_answer and
                (expected_source in sources if must_answer else not sources) and
                not answer["model_used"] and
                "SECRET_FARAZ_PROPRIETARY" not in answer["answer"] and
                all(path == "docs/guide.md" for path in sources)
            )
            results.append({
                "project": project_id, "case": question,
                "expected": "evidence" if must_answer else "escalation",
                "observed": "escalation" if answer["needs_human"] else "evidence",
                "source_paths": sources, "passed": acceptable
            })
        passed = sum(x["passed"] for x in results)
        return {
            "fixture_type": "synthetic",
            "supports_real_customer_acceptance": False,
            "model_configured": False,
            "total": len(results), "passed": passed, "failed": len(results)-passed,
            "pass_rate": round(passed/len(results), 4),
            "cases": results,
        }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strict", action="store_true",
                   help="Exit nonzero on any failure in the synthetic engineering gate")
    p.add_argument("--output", type=Path, help="Write JSON to this file")
    args = p.parse_args()
    report = evaluate()
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    print(serialized)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    if args.strict and report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
