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
# Bound untrusted evidence size before validation and interval indexing.
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
                    and int(x["source_sha256"], 16) != 0  # Reject all-zero placeholder hashes
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
                # Require overlap within the same source. Prefix maxima preserve\n                # long enclosing intervals; zero-duration anchors can coincide.
                by_source = {}
                for anchor in evidence:
                    source = anchor["source_sha256"].lower()
                    pair = by_source.setdefault(source, {"speech": [], "image": []})
                    pair[anchor["modality"]].append((anchor["start"], anchor["end"]))
                # Prefix maximum end handles nested intervals correctly.
                # For each speech interval, binary-search the last image
                # starting no later than speech.end. An overlap exists iff
                # the maximum image end in that prefix >= speech.start.
                from bisect import bisect_right
                for pair in by_source.values():
                    images = sorted(pair["image"], key=lambda interval: (interval[0], interval[1]))
                    starts = [interval[0] for interval in images]
                    max_ends = []
                    running_max = float("-inf")
                    for _, image_end in images:
                        running_max = max(running_max, image_end)
                        max_ends.append(running_max)
                    for speech_start, speech_end in pair["speech"]:
                        k = bisect_right(starts, speech_end) - 1
                        if k >= 0 and max_ends[k] >= speech_start:
                            refs_ok = True
                            break
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
            # Untrusted JSON may supply a list/dict as kind; never hash it.
            kind = rule.get("kind")
            kind_ok = isinstance(kind, str) and kind in REQUIRED
            if (kind_ok and
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
