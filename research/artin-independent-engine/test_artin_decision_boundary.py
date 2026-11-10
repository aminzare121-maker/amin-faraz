"""Synthetic software tests only; not evidence of teacher meaning or profitability."""
import unittest
from artin_decision_boundary import RuleOutcome, decide

def rule(kind, action, priority=1, verified=True):
    return RuleOutcome(kind + action, kind, action, verified, "session-01@00:01:00", priority, 1)

class DecisionBoundaryTests(unittest.TestCase):
    def test_no_rules_blocks(self):
        self.assertEqual(decide([])["reason"], "NO_VERIFIED_TEACHER_RULES")

    def test_real_blocks(self):
        self.assertEqual(decide([], demo_only=False)["reason"], "REAL_DISABLED")

    def test_unverified_blocks(self):
        self.assertEqual(decide([rule("entry", "ENTER", verified=False)])["reason"], "UNVERIFIED_OR_INVALID_RULE")

    def test_entry_requires_exit_and_risk(self):
        self.assertEqual(decide([rule("entry", "ENTER")])["reason"], "EXIT_OR_RISK_UNVERIFIED")

    def test_conflict_blocks(self):
        self.assertEqual(decide([rule("entry", "ENTER"), rule("exit", "EXIT")])["reason"], "PRIORITY_CONFLICT")

    def test_veto_prevents_entry(self):
        rows = [rule("entry", "ENTER", 3), rule("exception", "NO_TRADE")]
        self.assertEqual(decide(rows)["decision"], "NO_TRADE")

    def test_non_executable_even_when_allowed(self):
        rows = [rule("entry", "ENTER", 3), rule("exit", "EXIT"), rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["decision"], "ENTER")
        self.assertIs(result["executable"], False)

if __name__ == "__main__":
    unittest.main()
