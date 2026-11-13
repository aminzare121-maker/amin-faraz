"""SELL-side adverse fill must fail closed without inventing a broker order.

Offline accounting regression only; not evidence of teacher rules or MT5 performance.
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from capital import BoxPlan, Costs, Instrument
from entry_engine import Observation, Fact
from trade_machine import TradeMachine


class StubEngine:
    fingerprint = "sell-fill-risk-regression"

    def evaluate(self, rule_id, observation):
        return SimpleNamespace(status="ELIGIBLE", reasons=())


class SellAdverseFillTests(unittest.TestCase):
    def test_sell_adverse_fill_exceeds_risk_and_blocks_stop_management(self):
        D = Decimal
        machine = TradeMachine(
            StubEngine(),
            BoxPlan("sell-risk", D("10"), "explicit-test-target", ("reduce", "riskfree", "saveprofit"), True),
            Instrument(D("1"), D("1"), D("1")),
            Costs(D("0"), D("0")),
        )
        observation = Observation("SELL", 10, {"test_fact": Fact(True, 10, "offline-test")})
        intent = machine.prepare("test-rule", observation, D("100"), D("105"),
                                 D("90"), D("10"), D("1"))
        self.assertEqual(intent["status"], "PAPER_ENTRY_INTENT")
        fill = machine.fill_entry(D("92"), D("1"))
        self.assertEqual(fill["status"], "OPEN_REVIEW")
        self.assertEqual(fill["modeled_loss"], D("13"))
        self.assertTrue(machine.budget_overrun)
        stop_before = machine.current_stop
        decision = machine.manage("saveprofit", D("91"), Fact(True, 11, "offline-test"), 11)
        self.assertEqual(decision["status"], "REVIEW")
        self.assertEqual(machine.current_stop, stop_before)
        self.assertFalse(decision["order_created"])
        self.assertIsNone(decision["realized_pnl"])


if __name__ == "__main__":
    unittest.main()
