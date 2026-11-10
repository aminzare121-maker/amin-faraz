"""Fail-closed audit of a real V13 per-video cycle receipt.

This module does not run ASR/OCR or claim that a film was processed.
It checks timestamps and explicit evidence flags emitted by the real pipeline.
"""
from datetime import datetime, timezone
import json
import sys

STAGES = ("received", "speech_complete", "visual_complete",
          "semantic_review_complete", "archived", "receipt_written",
          "next_handoff_complete")
REQUIRED_EVIDENCE = ("speech_source_verified", "visual_source_verified",
                     "teacher_semantics_verified", "archive_verified",
                     "next_handoff_verified")

def audit(receipt):
    if not isinstance(receipt, dict):
        return {"passed": False, "errors": ["receipt must be an object"]}
    errors = []
    if not isinstance(receipt.get("video_id"), str) or not receipt["video_id"].strip():
        errors.append("missing video_id")
    timestamps = []
    for stage in STAGES:
        value = receipt.get("timestamps", {}).get(stage) if isinstance(receipt.get("timestamps"), dict) else None
        try:
            if not isinstance(value, str):
                raise ValueError("timestamp missing")
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None or dt.utcoffset() is None:
                raise ValueError("timezone required")
            timestamps.append(dt.astimezone(timezone.utc))
        except (ValueError, TypeError, OverflowError):
            errors.append("invalid or missing timestamp: " + stage)
    if len(timestamps) == len(STAGES):
        if any(b < a for a, b in zip(timestamps, timestamps[1:])):
            errors.append("out-of-order stages")
        elapsed = (timestamps[-1] - timestamps[0]).total_seconds()
        if not (0 <= elapsed < 180):
            errors.append("end-to-end duration must be strictly under 180 seconds")
    else:
        elapsed = None
    evidence = receipt.get("evidence")
    for key in REQUIRED_EVIDENCE:
        if not isinstance(evidence, dict) or evidence.get(key) is not True:
            errors.append("unverified evidence: " + key)
    return {"passed": not errors, "duration_seconds": elapsed, "errors": errors}

def main():
    if len(sys.argv) != 2:
        print("usage: python artin_real_cycle_receipt_gate.py receipt.json", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            receipt = json.load(f)
    except (OSError, ValueError) as exc:
        print(json.dumps({"passed": False, "errors": [str(exc)]}))
        return 1
    result = audit(receipt)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
