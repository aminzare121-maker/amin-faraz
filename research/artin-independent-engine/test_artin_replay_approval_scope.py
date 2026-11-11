"""Regression tests for replay approval scope; no broker or teacher claims."""
from artin_decision_boundary import RuleOutcome, decide


def _row():
    return RuleOutcome(
        rule_id="lesson-1-rule", kind="entry", action="HOLD",
        verified=True, evidence_id="placeholder-not-authentic",
        priority=1, session=1,
    )


def test_unrelated_approval_is_blocked():
    result = decide([_row()], replay_approved_rule_ids=["lesson-1-rule", "other-rule"])
    assert result == {
        "decision": "BLOCKED",
        "reason": "REPLAY_APPROVAL_SET_MISMATCH",
        "executable": False,
    }


def test_missing_approval_stays_blocked():
    result = decide([_row()], replay_approved_rule_ids=[])
    assert result["reason"] == "REPLAY_APPROVAL_MISSING"
    assert result["executable"] is False


def test_matching_approval_is_non_executable():
    result = decide([_row()], replay_approved_rule_ids=["lesson-1-rule"])
    assert result["decision"] == "HOLD"
    assert result["executable"] is False
