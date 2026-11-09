"""Fail-closed semantic acceptance gate for the 25 Artin sessions.

This does NOT infer teacher intent. It checks independently reviewed evidence
and example comparisons before a rule may be marked verified.
Input: JSON object {"sessions": [{"session": 1..25, "rules": [...]}, ...]}.
Each rule requires raw evidence references and a human-reviewed comparison.
"""
import json
import sys

REQUIRED = {"entry", "exit", "exception", "decision_order"}


def audit(document):
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
        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                errors.append(f"session {number} rule {idx}: malformed")
                continue
            evidence = rule.get("evidence")
            compare = rule.get("independent_comparison")
            # Verifier must identify actual teacher example, expected and observed
            # decision, speech+image timed anchors, and independent reviewer.
            refs_ok = (
                isinstance(evidence, list) and bool(evidence)
                and all(isinstance(x, dict)
                        and x.get("source_sha256")
                        and isinstance(x.get("start"), (int, float))
                        and isinstance(x.get("end"), (int, float))
                        and 0 <= x["start"] <= x["end"]
                        and x.get("modality") in ("speech", "image")
                        for x in evidence)
                and {"speech", "image"}.issubset(
                    {x["modality"] for x in evidence}
                )
            )
            compare_ok = (
                isinstance(compare, dict)
                and compare.get("teacher_example_id")
                and compare.get("reviewer")
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
            elif rule.get("status") == "VERIFIED":
                errors.append(f"session {number} rule {idx}: unsupported VERIFIED claim")
        result.append({
            "session": number,
            "status": "REVIEWED" if verified and verified == len(rules) else "UNVERIFIED",
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
