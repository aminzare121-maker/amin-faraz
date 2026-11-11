"""Regression: duplicate replay approvals cannot be silently collapsed."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).with_name("artin_decision_boundary.py")
spec = importlib.util.spec_from_file_location("artin_decision_boundary", MODULE)
engine = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


def test_duplicate_replay_approval_blocks():
    row = engine.RuleOutcome(
        rule_id="teacher-rule-1", kind="entry", action="HOLD",
        verified=True, evidence_id="session-1-timestamp", priority=1, session=1
    )
    result = engine.decide([row], replay_approved_rule_ids=[
        "teacher-rule-1", "teacher-rule-1"
    ])
    assert result == {
        "decision": "BLOCKED",
        "reason": "DUPLICATE_REPLAY_APPROVAL",
        "executable": False,
    }


def test_single_replay_approval_preserves_existing_behavior():
    row = engine.RuleOutcome(
        rule_id="teacher-rule-1", kind="entry", action="HOLD",
        verified=True, evidence_id="session-1-timestamp", priority=1, session=1
    )
    result = engine.decide([row], replay_approved_rule_ids=["teacher-rule-1"])
    assert result["decision"] == "HOLD"
    assert result["executable"] is False
