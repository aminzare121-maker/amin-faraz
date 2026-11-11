"""Regression: every blocked decision explicitly forbids execution."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "artin_decision_boundary", Path(__file__).with_name("artin_decision_boundary.py"))
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class BlockedNonExecutableTests(unittest.TestCase):
    def test_empty_outcomes(self):
        result = module.decide([])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIs(result["executable"], False)

    def test_invalid_rule(self):
        bad = module.RuleOutcome("x", "entry", "ENTER", False, "e", 1, 1)
        result = module.decide([bad])
        self.assertEqual(result["reason"], "UNVERIFIED_OR_INVALID_RULE")
        self.assertIs(result["executable"], False)

    def test_duplicate_ids(self):
        r = module.RuleOutcome("x", "entry", "HOLD", True, "e", 1, 1)
        result = module.decide([r, r])
        self.assertEqual(result["reason"], "DUPLICATE_RULE_ID")
        self.assertIs(result["executable"], False)

    def test_priority_conflict(self):
        a = module.RuleOutcome("a", "entry", "ENTER", True, "e1", 5, 1)
        b = module.RuleOutcome("b", "exit", "EXIT", True, "e2", 5, 1)
        result = module.decide([a, b], replay_approved_rule_ids=["a", "b"])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIs(result["executable"], False)

if __name__ == "__main__":
    unittest.main()
