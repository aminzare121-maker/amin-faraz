#!/usr/bin/env python3
"""Strict V13 acceptance gate. Never infer success from an extraction receipt alone."""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = ("source_started_at", "download_verified_at", "speech_complete_at",
            "visual_complete_at", "semantic_review_complete_at", "archive_committed_at",
            "receipt_committed_at", "next_handoff_committed_at", "behrooz_readback_verified_at")
EVIDENCE = ("source_sha256", "speech_evidence_sha256", "visual_evidence_sha256",
            "semantic_review_sha256", "archive_sha256", "receipt_sha256",
            "next_queue_id")

def check(record):
    errors = []
    times = {}
    for key in REQUIRED:
        value = record.get(key)
        if not value:
            errors.append("missing "+key)
            continue
        try:
            times[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if times[key].tzinfo is None:
                raise ValueError("timezone required")
        except (ValueError, TypeError, AttributeError):
            errors.append("invalid UTC timestamp "+key)
    for key in EVIDENCE:
        if not record.get(key):
            errors.append("missing evidence "+key)
    # A populated field is not proof: require actual SHA-256 digests, not placeholders.
    for key in EVIDENCE:
        if key.endswith("_sha256"):
            value = record.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                errors.append("invalid SHA-256 evidence "+key)
    # A single reused digest cannot represent distinct source, ASR, OCR, review, archive and receipt artifacts.\n    digests = [record.get(k) for k in EVIDENCE if k.endswith("_sha256")]\n    valid_digests = [v for v in digests if isinstance(v, str) and len(v) == 64]\n    if len(valid_digests) != len(set(valid_digests)):\n        errors.append("duplicate SHA-256 across distinct evidence artifacts")\n    if record.get("evidence_mode") != "real-production":
        errors.append("not real production evidence")
    if record.get("semantic_review_passed") is not True:
        errors.append("semantic review not verified")
    if record.get("next_handoff_verified") is not True:
        errors.append("next-film handoff not verified")
    if record.get("source_integrity_verified") is not True:
        errors.append("source integrity not verified")
    if len(times) == len(REQUIRED):
        order = [times[k] for k in REQUIRED]
        if order != sorted(order):
            errors.append("timestamps out of order, including Behrooz readback")
        duration = (times["behrooz_readback_verified_at"] - times["source_started_at"]).total_seconds()
        if duration >= 180 or duration < 0:
            errors.append(f"end-to-end duration {duration:.3f}s must be nonnegative and below 180s")
    else:
        duration = None
    return {"passed": not errors, "duration_seconds": duration, "errors": errors}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("evidence", type=Path)
    a = p.parse_args()
    result = check(json.loads(a.evidence.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
