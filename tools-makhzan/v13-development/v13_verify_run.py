#!/usr/bin/env python3
"""V13 isolated end-to-end evidence verifier. Fails closed; never edits active queue."""
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
    return {
        "passed": gate["passed"] and files["passed"],
        "duration_seconds": gate["duration_seconds"],
        "errors": gate["errors"] + files["errors"],
        "status": "VERIFIED" if gate["passed"] and files["passed"] else "UNVERIFIED",
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
