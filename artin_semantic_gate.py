"""Fail-closed semantic acceptance gate for the 25 Artin sessions.

This does NOT infer teacher intent. It checks independently reviewed evidence
and example comparisons before a rule may be marked verified.
Input: JSON object {"sessions": [{"session": 1..25, "rules": [...]}, ...]}.
Each rule requires raw evidence references and a human-reviewed comparison.
"""
import json
import math
import re
import sys

REQUIRED = {"entry", "exit", "exception", "decision_order"}
# Bound untrusted evidence size before the quadratic speech/image join.
MAX_ANCHORS_PER_RULE = 2000


def audit(document):
    if not isinstance(document, dict):
        raise ValueError("evidence document must be an object")
    sessions = document.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("sessions must be an array")
    by_number = {}
    errors = []
    for row in sessions:
        if not isinstance(row, dict) or type(row.get("session")) is not int:
            errors.append("invalid session record")
            continue
        number = row["session"]
        if not 1 <= number <= 25 or number in by_number:
            errors.append(f"session {number}: duplicate or out of range")
            continue
        by_number[number] = row
    result = []
    for number in range(1, 26):
        row = by_number.get(number)
        if row is None:
            result.append({"session": number, "status": "MISSING", "verified_rules": 0})
            continue
        rules = row.get("rules", [])
        if not isinstance(rules, list):
            errors.append(f"session {number}: rules must be an array")
            rules = []
        verified = 0
        verified_kinds = set()
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"session {number} rule {idx}: malformed")
                continue
            evidence = rule.get("evidence")
            compare = rule.get("independent_comparison")
            # Verifier must identify actual teacher example, expected and observed
            # decision, speech+image timed anchors, and independent reviewer.
            # A pair of unrelated timestamps or placeholder hashes is not
            # evidence of a synchronized speech/image observation.
            def valid_anchor(x):
                return (
                    isinstance(x, dict)
                    and isinstance(x.get("source_sha256"), str)
                    and re.fullmatch(r"[0-9a-fA-F]{64}", x["source_sha256"]) is not None
                    and type(x.get("start")) in (int, float)
                    and type(x.get("end")) in (int, float)
                    and math.isfinite(x["start"])
                    and math.isfinite(x["end"])
                    and 0 <= x["start"] <= x["end"]
                    and x.get("modality") in ("speech", "image")
                )

            refs_ok = False
            if (isinstance(evidence, list) and 0 < len(evidence) <= MAX_ANCHORS_PER_RULE
                    and all(valid_anchor(x) for x in evidence)):
                # Match anchors on the same source video, with overlapping
                # intervals. Zero-duration anchors are allowed if coincident.
                # Group by video and sweep intervals sorted by start time.
                # Avoid the quadratic cross-product for long lessons.
                by_source = {}
                for anchor in evidence:
                    source = anchor["source_sha256"].lower()
                    pair = by_source.setdefault(source, {"speech": [], "image": []})
                    pair[anchor["modality"]].append((anchor["start"], anchor["end"]))
                for pair in by_source.values():
                    speech = sorted(pair["speech"])
                    images = sorted(pair["image"])
                    i = j = 0
                    while i < len(speech) and j < len(images):
                        a, b = speech[i], images[j]
                        if max(a[0], b[0]) <= min(a[1], b[1]):
                            refs_ok = True
                            break
                        if a[1] < b[1]:
                            i += 1
                        else:
                            j += 1
                    if refs_ok:
                        break
            compare_ok = (
                isinstance(compare, dict)
                and isinstance(compare.get("teacher_example_id"), str)
                and bool(compare["teacher_example_id"].strip())
                and isinstance(compare.get("reviewer"), str)
                and bool(compare["reviewer"].strip())
                and compare.get("expected_decision") in ("ENTER", "EXIT", "HOLD", "NO_TRADE")
                and compare.get("observed_decision") == compare.get("expected_decision")
                and compare.get("independent") is True
                and compare.get("review_result") == "PASS"
            )
            if (rule.get("kind") in REQUIRED and
                    rule.get("cross_session_checked") is True and
                    rule.get("ambiguity_resolved") is True and
                    refs_ok and compare_ok):
                verified += 1
                verified_kinds.add(rule["kind"])
            elif rule.get("status") == "VERIFIED":
                errors.append(f"session {number} rule {idx}: unsupported VERIFIED claim")
        result.append({
            "session": number,
            "status": "REVIEWED" if REQUIRED.issubset(verified_kinds) and verified == len(rules) else "UNVERIFIED",
            "missing_rule_kinds": sorted(REQUIRED - verified_kinds),
            "verified_rules": verified,
            "total_rules": len(rules)
        })
    return {"complete": len(by_number) == 25 and all(
        x["status"] == "REVIEWED" for x in result
    ) and not errors, "sessions": result, "errors": errors}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python artin_semantic_gate.py evidence.json")
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    outcome = audit(data)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    sys.exit(0 if outcome["complete"] else 1)
