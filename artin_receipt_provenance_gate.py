"""Independent file-backed evidence check for Artin V13 receipts.

Receipt booleans are self-reported. This gate verifies that declared artifact
bytes exist and match SHA-256 before a receipt may be called file-backed.
It does NOT verify teacher meaning or source authenticity.
"""
import hashlib
import json
import os
import stat
from pathlib import Path

REQUIRED = ("source_video", "speech", "visual", "semantic_review", "archive", "handoff")
MAX_BYTES = 1024 * 1024 * 1024

def fstat_artifact(file):
    return os.fstat(file.fileno())

def audit_artifacts(receipt, root):
    errors = []
    root = Path(root).resolve()
    artifacts = receipt.get("artifacts") if isinstance(receipt, dict) else None
    if not isinstance(artifacts, dict):
        return {"passed": False, "errors": ["missing artifacts map"]}
    seen_paths = set()
    seen_inodes = set()
    for kind in REQUIRED:
        item = artifacts.get(kind)
        if not isinstance(item, dict):
            errors.append("missing artifact: " + kind)
            continue
        name, expected = item.get("path"), item.get("sha256")
        if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
            errors.append("invalid artifact path: " + kind)
            continue
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            errors.append("invalid SHA-256: " + kind)
            continue
        # Open the artifact once and verify/hash the SAME file descriptor.
        # A path may be replaced between stat() and open(); fstat() on the
        # opened descriptor prevents accepting an unchecked replacement.
        try:
            path = (root / name).resolve(strict=True)
            if not path.is_relative_to(root):
                errors.append("missing or unsafe file: " + kind)
                continue
            with path.open("rb") as f:
                metadata = fstat_artifact(f)
                if not stat.S_ISREG(metadata.st_mode):
                    errors.append("missing or unsafe file: " + kind)
                    continue
                if path in seen_paths:
                    errors.append("duplicate artifact file: " + kind)
                    continue
                identity = (metadata.st_dev, metadata.st_ino)
                if identity in seen_inodes:
                    errors.append("duplicate artifact inode: " + kind)
                    continue
                seen_paths.add(path)
                seen_inodes.add(identity)
                if metadata.st_size > MAX_BYTES:
                    errors.append("artifact exceeds size limit: " + kind)
                    continue
                digest = hashlib.sha256()
                total = 0
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    total += len(block)
                    if total > MAX_BYTES:
                        errors.append("artifact exceeds size limit: " + kind)
                        break
                    digest.update(block)
                else:
                    if digest.hexdigest() != expected:
                        errors.append("digest mismatch: " + kind)
        except (OSError, RuntimeError):
            errors.append("missing or unreadable file: " + kind)
    return {"passed": not errors, "errors": errors}

def audit_file_backed_cycle(receipt, root):
    from artin_real_cycle_receipt_gate import audit
    timing = audit(receipt)
    files = audit_artifacts(receipt, root)
    return {"passed": timing["passed"] and files["passed"],
            "duration_seconds": timing.get("duration_seconds"),
            "errors": timing["errors"] + files["errors"]}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    try:
        with open(args.receipt, encoding="utf-8") as f:
            receipt = json.load(f)
        result = audit_file_backed_cycle(receipt, args.root)
    except (OSError, ValueError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
