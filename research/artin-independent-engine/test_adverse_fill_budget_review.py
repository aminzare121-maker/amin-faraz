"""End-to-end offline regression for an adverse entry fill.

This tests engine risk handling, not teacher interpretation or MT5 performance.
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from capital import BoxPlan, Costs, Instrument
from entry_engine import Observation, Fact
from trade_machine import TradeMachine


class StubEngine:
    fingerprint = "offline-test-engine"
    def evaluate(self, rule_id, observation):
        return SimpleNamespace(status="ELIGIBLE", reasons=())


class AdverseFillRiskTests(unittest.TestCase):
    def test_adverse_fill_over_budget_blocks_management(self):
        D = Decimal
        box = BoxPlan("test-box", D("10"), "test-target", ("saveprofit",), True)
        instrument = Instrument(D("1"), D("1"), D("1"))
        costs = Costs(D("0"), D("0"))
        machine = TradeMachine(StubEngine(), box, instrument, costs)
        observation = Observation("BUY", 10, {"source_flag": Fact(True, 10, "offline-test")})
        intent = machine.prepare("test-rule", observation, D("100"), D("95"),
                                 D("110"), D("10"), D("1"))
        self.assertEqual(intent["status"], "PAPER_ENTRY_INTENT")
        fill = machine.fill_entry(D("108"), D("1"))
        self.assertEqual(fill["status"], "OPEN_REVIEW")
        self.assertTrue(machine.budget_overrun)
        self.assertEqual(fill["modeled_loss"], D("13"))
        stop_before = machine.current_stop
        result = machine.manage("saveprofit", D("109"), Fact(True, 11, "offline-test"), 11)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(machine.current_stop, stop_before)
        self.assertFalse(result["order_created"])
        self.assertIsNone(result["realized_pnl"])


if __name__ == "__main__":
    unittest.main()
