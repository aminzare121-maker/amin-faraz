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

    def test_lower_priority_entry_no_trade_blocks_high_priority_entry(self):
        rows = [rule("entry", "ENTER", 10),
                RuleOutcome("no_entry", "entry", "NO_TRADE", True,
                            "session-02@00:03:00", 1, 2),
                rule("exit", "HOLD"), rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "ENTRY_NO_TRADE_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_lower_priority_exit_not_silently_suppressed_by_hold(self):
        rows = [rule("exit", "EXIT", 1), rule("risk", "HOLD", 10)]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "EXIT_HOLD_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_veto_prevents_entry(self):
        rows = [rule("entry", "ENTER", 3), rule("exception", "NO_TRADE")]
        self.assertEqual(decide(rows)["decision"], "NO_TRADE")

    def test_simultaneous_exit_blocks_entry_even_at_lower_priority(self):
        rows = [rule("entry", "ENTER", 10), rule("exit", "EXIT", 1), rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "ENTRY_EXIT_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_truthy_string_is_not_verification(self):
        row = RuleOutcome("entry1", "entry", "ENTER", "yes", "session-01@00:01:00", 1, 1)
        self.assertEqual(decide([row])["reason"], "UNVERIFIED_OR_INVALID_RULE")

    def test_invalid_rule_kind_action_pairs_block(self):
        for kind, action in (("exit", "ENTER"), ("risk", "ENTER"),
                             ("exception", "EXIT")):
            with self.subTest(kind=kind, action=action):
                row = RuleOutcome("bad", kind, action, True, "session-01@00:01:00", 1, 1)
                self.assertEqual(decide([row])["decision"], "BLOCKED")

    def test_decision_order_cannot_authorize_entry_or_exit(self):
        for action in ("ENTER", "EXIT"):
            with self.subTest(action=action):
                rows = [rule("decision_order", action, 10), rule("exit", "HOLD"), rule("risk", "HOLD")]
                self.assertEqual(decide(rows)["reason"], "UNVERIFIED_OR_INVALID_RULE")

    def test_non_executable_even_when_allowed(self):
        rows = [rule("entry", "ENTER", 3), rule("exit", "HOLD"), rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["decision"], "ENTER")
        self.assertIs(result["executable"], False)

if __name__ == "__main__":
    unittest.main()
