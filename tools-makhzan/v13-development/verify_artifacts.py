#!/usr/bin/env python3
"""Verify actual V13 artifact bytes, not merely claimed SHA strings."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ARTIFACT_KEYS = ("source", "speech_evidence", "visual_evidence", "semantic_review", "archive", "receipt")

def verify(record, root):
    errors = []
    for name in ARTIFACT_KEYS:
        relative = record.get(name + "_path")
        expected = record.get(name + "_sha256")
        if not isinstance(relative, str) or not relative:
            errors.append("missing file path: " + name)
            continue
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            errors.append("missing or unsafe file: " + name)
            continue
        h = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != expected:
            errors.append("byte digest mismatch: " + name)
    return {"passed": not errors, "errors": errors}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.record.read_text(encoding="utf-8")), args.root)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
