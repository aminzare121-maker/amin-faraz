"""Regression: malformed unhashable rule fields must fail closed, not raise."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("artin_decision_boundary.py")
spec = importlib.util.spec_from_file_location("artin_decision_boundary", MODULE)
engine = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class UnhashableRuleFieldsTest(unittest.TestCase):
    def test_unhashable_kind_and_action_block(self):
        for field, value in (("kind", []), ("kind", {}), ("action", []), ("action", {})):
            with self.subTest(field=field, value=value):
                fields = dict(rule_id="x", kind="entry", action="ENTER",
                              verified=True, evidence_id="session1:00:00",
                              priority=1, session=1)
                fields[field] = value
                result = engine.decide([engine.RuleOutcome(**fields)],
                                       replay_approved_rule_ids=("x",))
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertEqual(result["reason"], "UNVERIFIED_OR_INVALID_RULE")


if __name__ == "__main__":
    unittest.main()
