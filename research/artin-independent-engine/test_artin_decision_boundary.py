"""Synthetic software tests only; not evidence of teacher meaning or profitability."""
import unittest
from artin_decision_boundary import RuleOutcome, decide

def rule(kind, action, priority=1, verified=True):
    return RuleOutcome(kind + action, kind, action, verified, "session-01@00:01:00", priority, 1)

class DecisionBoundaryTests(unittest.TestCase):
    def test_exit_scoped_no_trade_requires_position_context(self):
        for rows in (
            [rule("exit", "NO_TRADE")],
            [rule("exit", "NO_TRADE", 10), rule("risk", "HOLD", 1)],
        ):
            with self.subTest(rows=rows):
                result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertEqual(result["reason"], "EXIT_NO_TRADE_POSITION_CONTEXT_UNVERIFIED")
                self.assertIs(result["executable"], False)

    def test_no_rules_blocks(self):
        self.assertEqual(decide([])["reason"], "NO_VERIFIED_TEACHER_RULES")

    def test_real_blocks(self):
        self.assertEqual(decide([], demo_only=False)["reason"], "REAL_DISABLED")

    def test_demo_boundary_rejects_truthy_non_boolean_values(self):
        for value in ("true", "false", "DEMO", 1, [True], {"demo": True}, None):
            with self.subTest(value=value):
                result = decide([], demo_only=value)
                self.assertEqual(result["reason"], "REAL_DISABLED")
                self.assertIs(result["executable"], False)

    def test_unverified_blocks(self):
        self.assertEqual(decide([rule("entry", "ENTER", verified=False)])["reason"], "UNVERIFIED_OR_INVALID_RULE")

    def test_entry_requires_exit_and_risk(self):
        self.assertEqual(decide([rule("entry", "ENTER")])["reason"], "EXIT_OR_RISK_UNVERIFIED")

    def test_conflict_blocks(self):
        self.assertEqual(decide([rule("entry", "ENTER"), rule("exit", "EXIT")])["reason"], "ENTRY_EXIT_PRECEDENCE_UNVERIFIED")

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

    def test_higher_ranked_entry_no_trade_cannot_suppress_exit(self):
        rows = [rule("exit", "EXIT", 1),
                rule("entry", "NO_TRADE", 10)]
        result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
        self.assertEqual(result["reason"], "EXIT_PRECEDENCE_UNVERIFIED")
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIs(result["executable"], False)

    def test_lower_ranked_entry_no_trade_does_not_suppress_exit(self):
        rows = [rule("exit", "EXIT", 10),
                rule("entry", "NO_TRADE", 1)]
        result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "EXIT_ENTRY_NO_TRADE_CONTEXT_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_high_priority_hold_cannot_hide_no_trade(self):
        rows = [rule("entry", "NO_TRADE", 1), rule("risk", "HOLD", 10)]
        result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "NO_TRADE_HOLD_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_high_priority_no_trade_cannot_hide_hold(self):
        rows = [rule("entry", "NO_TRADE", 10), rule("risk", "HOLD", 1)]
        result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
        self.assertEqual(result["reason"], "NO_TRADE_HOLD_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_veto_prevents_entry(self):
        rows = [rule("entry", "ENTER", 3), rule("exception", "NO_TRADE")]
        self.assertEqual(decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])["decision"], "NO_TRADE")

    def test_veto_without_replay_cannot_claim_verified_teacher_veto(self):
        rows = [rule("entry", "ENTER", 3), rule("exception", "NO_TRADE")]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")
        self.assertIs(result["executable"], False)

    def test_exit_not_suppressed_by_risk_veto(self):
        rows = [rule("exit", "EXIT", 1), rule("risk", "NO_TRADE", 10)]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "EXIT_VETO_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

    def test_exit_not_suppressed_by_exception_veto(self):
        rows = [rule("exit", "EXIT", 1), rule("exception", "NO_TRADE", 10)]
        result = decide(rows)
        self.assertEqual(result["reason"], "EXIT_VETO_PRECEDENCE_UNVERIFIED")
        self.assertIs(result["executable"], False)

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

    def test_verified_flag_without_replay_approval_blocks_entry(self):
        rows = [rule("entry", "ENTER", 3), rule("exit", "HOLD"), rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")
        self.assertIs(result["executable"], False)

    def test_partial_replay_approval_blocks_entry(self):
        rows = [rule("entry", "ENTER", 3), rule("exit", "HOLD"), rule("risk", "HOLD")]
        result = decide(rows, replay_approved_rule_ids=["entryENTER"])
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")

    def test_hold_without_replay_is_not_verified_teacher_decision(self):
        rows = [rule("risk", "HOLD")]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")
        self.assertIs(result["executable"], False)

    def test_standalone_no_trade_without_replay_is_blocked(self):
        rows = [rule("entry", "NO_TRADE")]
        result = decide(rows)
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")
        self.assertIs(result["executable"], False)

    def test_approved_hold_remains_non_executable(self):
        rows = [rule("risk", "HOLD")]
        result = decide(rows, replay_approved_rule_ids=[rows[0].rule_id])
        self.assertEqual(result["decision"], "HOLD")
        self.assertIs(result["executable"], False)

    def test_exit_requires_replay_approval(self):
        rows = [rule("exit", "EXIT", 3)]
        result = decide(rows)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertEqual(result["reason"], "REPLAY_APPROVAL_MISSING")
        self.assertIs(result["executable"], False)

    def test_exit_candidate_with_replay_still_non_executable(self):
        rows = [rule("exit", "EXIT", 3)]
        result = decide(rows, replay_approved_rule_ids=[rows[0].rule_id])
        self.assertEqual(result["decision"], "EXIT")
        self.assertIs(result["executable"], False)

    def test_non_executable_even_when_allowed(self):
        rows = [rule("entry", "ENTER", 3), rule("exit", "HOLD"), rule("risk", "HOLD")]
        result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
        self.assertEqual(result["decision"], "ENTER")
        self.assertIs(result["executable"], False)

if __name__ == "__main__":
    unittest.main()
