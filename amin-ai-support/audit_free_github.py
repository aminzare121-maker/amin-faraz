#!/usr/bin/env python3
"""Static cost-safety audit of GitHub Actions runner classes.

Standard GitHub-hosted runners are free for PUBLIC repositories. This is not
a billing-settings audit. Custom runner labels need separate owner verification.
"""
from __future__ import annotations
import os
from pathlib import Path
import re
import sys

STANDARD = re.compile(
    r"^(?:ubuntu-(?:latest|2[0246]\.04)|"
    r"windows-(?:latest|20(?:19|22|25))|"
    r"macos-(?:latest|1[345]))$", re.IGNORECASE)
KNOWN_CUSTOM = {"amin-win-native-58"}
LINE = re.compile(r"^\s*runs-on:\s*(.*?)\s*(?:#.*)?$")


def scan_text(name: str, content: str) -> list[str]:
    errors = []
    count = 0
    for number, line in enumerate(content.splitlines(), 1):
        match = LINE.match(line)
        if not match:
            continue
        count += 1
        raw = match.group(1).strip().strip('"').strip("'")
        if raw.startswith("[") and raw.endswith("]"):
            items = [x.strip().strip('"').strip("'") for x in raw[1:-1].split(",")]
            if len(items) == 1 and items[0] in KNOWN_CUSTOM:
                continue
            if "self-hosted" in items:
                continue
            errors.append(f"{name}:{number}: unknown multi-runner definition {raw}")
        elif not STANDARD.fullmatch(raw) and raw not in KNOWN_CUSTOM:
            errors.append(f"{name}:{number}: unsupported or potentially paid runner {raw}")
    if not count:
        errors.append(f"{name}: no auditable runs-on declaration")
    return errors


def audit(root: Path, visibility: str | None = None) -> list[str]:
    errors = []
    if visibility and visibility != "public":
        errors.append("Repository not public: standard runner use may be billed")
    workflows = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((root / ".github" / "workflows").glob("*.yaml"))
    if not workflows:
        return ["No GitHub workflows found"]
    for workflow in workflows:
        errors.extend(scan_text(workflow.name, workflow.read_text(encoding="utf-8")))
    return errors


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    issues = audit(root, visibility=os.environ.get("GITHUB_REPOSITORY_VISIBILITY"))
    if issues:
        print("\n".join("COST POLICY FAILED: " + issue for issue in issues))
        sys.exit(1)
    print("Runner policy passed. Actual GitHub billing settings were not inspected.")
