"""Regression: invalid paper entry fills must never acquire protected-profit stops.

This is a software safety test, not a reconstruction of Artin's teaching.
No broker is contacted and no trading rule is activated.
"""
import unittest
from decimal import Decimal as D
from types import SimpleNamespace

from capital import Instrument, Costs, BoxPlan
from trade_machine import TradeMachine
from entry_engine import Fact


class EligibleEngine:
    fingerprint = "isolated-regression-engine"

    def evaluate(self, rule_id, observation):
        return SimpleNamespace(status="ELIGIBLE", reasons=())


class InvalidFillReviewTest(unittest.TestCase):
    def test_adverse_fill_cannot_move_stop_or_realize_profit(self):
        box = BoxPlan("test-box", D("10"), "explicit-test-target",
                      ("reduce", "riskfree", "saveprofit"), True)
        machine = TradeMachine(EligibleEngine(), box,
                               Instrument(D("100"), D("0.01"), D("0.01")),
                               Costs(D("0"), D("0")))
        observation = SimpleNamespace(side="BUY", at=100)
        intent = machine.prepare("test-rule", observation, D("100"),
                                 D("99"), D("103"), D("10"), D("0.01"))
        self.assertEqual(intent["status"], "PAPER_ENTRY_INTENT")
        fill = machine.fill_entry(D("101"), D("0.01"))
        self.assertEqual(fill["status"], "OPEN_REVIEW")
        self.assertTrue(machine.budget_overrun)
        original_stop = machine.current_stop
        result = machine.manage("saveprofit", D("102"),
                                Fact(True, 101, "synthetic-test-trigger"), 101)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(machine.current_stop, original_stop)
        self.assertEqual(machine.state, "OPEN_REVIEW")
        self.assertIsNone(result["realized_pnl"])
        self.assertTrue(all(not e["order_created"] for e in machine.trace))


if __name__ == "__main__":
    unittest.main()
