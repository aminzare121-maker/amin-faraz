"""Structural (not semantic) verification of Artin cross-modal evidence."""
import json
import re
import sys

SHA = re.compile(r"^[a-f0-9]{64}$")
KINDS = {"entry", "exit", "exception", "decision_order"}
DECISIONS = {"ENTER", "EXIT", "HOLD", "NO_TRADE"}
SCENARIO_KINDS = {"hypothetical_market_state", "observed_market_state"}


def scenario_ok(rule):
    """A teacher's hypothetical market state is valid instructional evidence.

    Classifying a scenario is distinct from proving it occurred historically.
    This is a structural check; it does NOT certify the teacher's meaning.
    """
    scenario = rule.get("teaching_scenario")
    if scenario is None:
        return True, None  # Backwards-compatible: unclassified, not historically proven.
    if not isinstance(scenario, dict) or scenario.get("kind") not in SCENARIO_KINDS:
        return False, "invalid_teaching_scenario"
    if not good_text(scenario.get("market_state")):
        return False, "missing_scenario_market_state"
    if scenario["kind"] == "hypothetical_market_state":
        if scenario.get("claims_observed_trade") is True:
            return False, "hypothetical_falsely_claims_observed_trade"
        # Example/assumption/conditional speech is not grounds for rejection.
        return True, None
    if (scenario.get("source_observation_verified") is not True
            or not good_text(scenario.get("observation_evidence_id"))):
        return False, "unverified_historical_observation"
    return True, None


def good_text(v):
    return isinstance(v, str) and bool(v.strip())


def valid_anchor(a, session, sources):
    if not isinstance(a, dict):
        return False
    s, e, sha = a.get("start"), a.get("end"), a.get("source_sha256")
    return (a.get("modality") in {"speech", "image"}
            and good_text(a.get("evidence_id"))
            and isinstance(sha, str) and SHA.fullmatch(sha) is not None
            and isinstance(sources, dict) and sources.get(str(session)) == sha
            and type(s) in (int, float) and type(e) in (int, float)
            and 0 <= s <= e < 1e9)


def rule_ok(rule, number, sources):
    if not isinstance(rule, dict) or rule.get("kind") not in KINDS:
        return False, "invalid_rule"
    if rule.get("cross_session_checked") is not True or rule.get("ambiguity_resolved") is not True:
        return False, "review_incomplete"
    evidence = rule.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return False, "missing_av_evidence"
    if not all(valid_anchor(a, number, sources) for a in evidence):
        return False, "invalid_or_unmatched_source_anchor"
    speech = [a for a in evidence if a["modality"] == "speech"]
    images = [a for a in evidence if a["modality"] == "image"]
    if not speech or not images:
        return False, "missing_av_evidence"
    if not any(max(s["start"], i["start"]) <= min(s["end"], i["end"])
               for s in speech for i in images):
        return False, "av_timestamps_do_not_overlap"
    scenario_valid, scenario_reason = scenario_ok(rule)
    if not scenario_valid:
        return False, scenario_reason
    r = rule.get("independent_comparison")
    if (not isinstance(r, dict) or not good_text(r.get("teacher_example_id"))
            or not good_text(r.get("reviewer")) or not good_text(r.get("review_evidence_id"))
            or r.get("independent") is not True or r.get("review_result") != "PASS"
            or r.get("expected_decision") not in DECISIONS
            or r.get("observed_decision") != r.get("expected_decision")):
        return False, "comparison_not_verified"
    return True, None


def audit(document):
    if not isinstance(document, dict):
        raise ValueError("document must be an object")
    sessions = document.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("sessions must be an array")
    by_number, errors = {}, []
    for session in sessions:
        if not isinstance(session, dict) or type(session.get("session")) is not int:
            errors.append("invalid session")
            continue
        n = session["session"]
        if not 1 <= n <= 25 or n in by_number:
            errors.append(f"duplicate/out-of-range session {n}")
            continue
        by_number[n] = session
    results = []
    for n in range(1, 26):
        if n not in by_number:
            results.append({"session": n, "status": "MISSING", "verified_rules": 0})
            continue
        rules = by_number[n].get("rules", [])
        if not isinstance(rules, list):
            errors.append(f"session {n} rules not a list")
            rules = []
        verified = 0
        for idx, rule in enumerate(rules):
            ok, reason = rule_ok(rule, n, document.get("source_registry", {}))
            if ok:
                verified += 1
            else:
                errors.append(f"session {n} rule {idx}: {reason}")
                if isinstance(rule, dict) and rule.get("status") == "VERIFIED":
                    errors.append(f"session {n} rule {idx}: unsupported VERIFIED claim")
        results.append({"session": n, "verified_rules": verified,
                        "status": "STRUCTURALLY_REVIEWED" if verified and verified == len(rules)
                        else "UNVERIFIED"})
    return {"complete": len(by_number) == 25 and not errors and all(
        r["status"] == "STRUCTURALLY_REVIEWED" for r in results),
        "semantic_fidelity_certified": False, "sessions": results, "errors": errors}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python artin_semantic_gate_v2.py evidence.json")
    with open(sys.argv[1], encoding="utf-8") as stream:
        outcome = audit(json.load(stream))
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    sys.exit(0 if outcome["complete"] else 1)
