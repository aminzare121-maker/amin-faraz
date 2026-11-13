"""Offline fixed-lot risk ceiling regression; no teacher or broker claims."""
import unittest
from decimal import Decimal as D
from types import SimpleNamespace
from capital import BoxPlan, Costs, Instrument
from entry_engine import Observation, Fact
from trade_machine import TradeMachine

class Stub:
    fingerprint = "offline"
    def evaluate(self, rule_id, observation):
        return SimpleNamespace(status="ELIGIBLE", reasons=())

class FixedLotTests(unittest.TestCase):
    def prepare_trade(self, lots, budget):
        t = TradeMachine(Stub(), BoxPlan("test", D("100"), "target", (), True),
                         Instrument(D("10"), D("0.01"), D("0.01")), Costs(D("0"), D("0")))
        obs = Observation("BUY", 10, {"test": Fact(True, 10, "synthetic")})
        return t, t.prepare("synthetic", obs, D("100"), D("95"), D("110"), budget, lots)

    def test_below_ceiling(self):
        t, r = self.prepare_trade(D("0.03"), D("10"))
        self.assertEqual(r["status"], "PAPER_ENTRY_INTENT")
        self.assertEqual(r["plan"]["lots"], D("0.03"))
        self.assertEqual(r["sizing"]["maximum_budget_lots"], D("0.20"))
        self.assertEqual(r["sizing"]["modeled_loss"], D("1.50"))
        self.assertFalse(r["execution_authorized"])

    def test_above_ceiling_rejected(self):
        t, r = self.prepare_trade(D("0.21"), D("10"))
        self.assertEqual(r["reason"], "REQUESTED_FIXED_LOT_EXCEEDS_DECLARED_RISK_BUDGET")
        self.assertEqual(t.state, "NEW")
        self.assertFalse(r["order_created"])

    def test_below_minimum_budget_rejected(self):
        t, r = self.prepare_trade(D("0.01"), D("0.40"))
        self.assertEqual(r["reason"], "MIN_LOT_EXCEEDS_RISK_BUDGET")
        self.assertFalse(r["order_created"])

if __name__ == "__main__":
    unittest.main()
