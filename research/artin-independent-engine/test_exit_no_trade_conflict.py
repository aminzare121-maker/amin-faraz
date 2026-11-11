"""Synthetic arbitration regression; not teacher replay or MT5 validation."""
import unittest
from artin_decision_boundary import RuleOutcome, decide


class ExitNoTradeConflictTests(unittest.TestCase):
    def test_conflict_blocks_at_both_priority_orders(self):
        for exit_priority, no_trade_priority in ((1, 10), (10, 1), (5, 5)):
            with self.subTest(priorities=(exit_priority, no_trade_priority)):
                rows = [
                    RuleOutcome("exit_signal", "exit", "EXIT", True, "session-01@00:01:00", exit_priority, 1),
                    RuleOutcome("exit_no_trade", "exit", "NO_TRADE", True, "session-01@00:02:00", no_trade_priority, 1),
                ]
                result = decide(rows, replay_approved_rule_ids=[r.rule_id for r in rows])
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertEqual(result["reason"], "EXIT_NO_TRADE_PRECEDENCE_UNVERIFIED")
                self.assertIs(result["executable"], False)


if __name__ == "__main__":
    unittest.main()
