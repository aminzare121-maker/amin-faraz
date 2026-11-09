#!/usr/bin/env python3
"""Isolated V13 end-to-end verifier. Never writes production queue or asserts real-run success from flags."""
import hashlib
import zipfile
import argparse
import importlib.util
import json
import sys
from pathlib import Path

def load(name):
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def verify_run(record, root):
    gate = load("v13_acceptance_gate").check(record)
    files = load("verify_artifacts").verify(record, root)
    errors = gate["errors"] + files["errors"]
    # A receipt must bind the SAME source, archive and queue handoff. A matching
    # receipt-file digest alone cannot establish that it describes this film.
    if files["passed"]:
        receipt = (Path(root) / record["receipt_path"]).resolve()
        try:
            doc = json.loads(receipt.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("receipt must be an object")
            for field in ("queue_id", "source_sha256", "archive_sha256", "semantic_review_sha256", "next_queue_id"):
                if doc.get(field) != record.get(field):
                    errors.append("receipt binding mismatch: " + field)
            if doc.get("semantic_review_passed") is not True:
                errors.append("receipt lacks verified semantic review")
            if doc.get("next_handoff_verified") is not True:
                errors.append("receipt lacks verified next handoff")
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append("receipt cannot be parsed: " + type(exc).__name__)
    try:
        root = Path(root).resolve()
        readback = (root / record["behrooz_readback_path"]).resolve()
        if not readback.is_relative_to(root) or not readback.is_file():
            raise ValueError("missing readback bytes")
        if not record.get("behrooz_library_file_id") or int(record["behrooz_version"]) < 1:
            raise ValueError("missing saved version")
        with zipfile.ZipFile(readback) as master:
            # ZIP allows duplicate filenames and read(name) silently selects one.
            names = master.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate ZIP members in Behrooz readback")
            if "BEHROOZ_INDEX.json" not in names:
                raise ValueError("missing Behrooz index")
            entries = json.loads(master.read("BEHROOZ_INDEX.json"))["videos"]
            matches = [v for v in entries if v.get("queue_id") == record["queue_id"]]
            if len(matches) != 1:
                raise ValueError("film identity absent or ambiguous")
            entry = matches[0]
            if not isinstance(entry.get("archive"), str) or entry["archive"] not in names:
                raise ValueError("indexed film archive missing")
            if not isinstance(entry.get("video"), int) or not 1 <= entry["video"] <= 999:
                raise ValueError("invalid indexed video number")
            review_member = f"DERIVED_NOT_RAW/VIDEO_{entry['video']:02d}/REVIEW_FA.md"
            if review_member not in names:
                raise ValueError("indexed film review missing")
            archive_digest = hashlib.sha256(master.read(entry["archive"])).hexdigest()
            if archive_digest != record["archive_sha256"] or archive_digest != entry["sha256"]:
                raise ValueError("wrong film archive in Behrooz")
            review = master.read(review_member)
            if hashlib.sha256(review).hexdigest() != record["semantic_review_sha256"]:
                raise ValueError("wrong review in Behrooz")
    except (KeyError, ValueError, OSError, TypeError, zipfile.BadZipFile) as exc:
        errors.append("Behrooz readback verification failed: " + str(exc))
    passed = not errors
    return {
        "passed": passed,
        "duration_seconds": gate["duration_seconds"],
        "errors": errors,
        "status": "VERIFIED" if passed else "UNVERIFIED",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify_run(json.loads(args.record.read_text(encoding="utf-8")), args.root)
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if args.report:
        args.report.write_text(serialized + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    sys.exit(main())
