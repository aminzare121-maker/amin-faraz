"""Regression: even rejected management observations consume their timestamp.

This is a software invariant test, not validation of teacher rules or MT5 fills.
"""
import unittest
from types import SimpleNamespace

from entry_engine import Fact
from trade_machine import TradeMachine


class ManagementCausalClockTest(unittest.TestCase):
    def test_rejected_management_cannot_be_followed_by_backdated_review(self):
        box = SimpleNamespace(fingerprint="box-v1", management_choices=())
        engine = SimpleNamespace(fingerprint="engine-v1")
        instrument = object()
        costs = object()
        trade = TradeMachine(engine, box, instrument, costs)
        trade.state = "OPEN"
        trade.last_at = 10
        trade.plan = {"side": "BUY"}
        first = trade.manage("unsupported", None, Fact(True, 15, "test-observation"), 15)
        self.assertEqual(first["status"], "REJECT")
        self.assertEqual(trade.last_at, 15)
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            trade.manage("unsupported", None, Fact(True, 12, "test-observation"), 12)

    def test_open_review_also_advances_clock(self):
        box = SimpleNamespace(fingerprint="box-v1", management_choices=())
        engine = SimpleNamespace(fingerprint="engine-v1")
        instrument = object()
        costs = object()
        trade = TradeMachine(engine, box, instrument, costs)
        trade.state = "OPEN_REVIEW"
        trade.last_at = 10
        result = trade.manage("unsupported", None, Fact(True, 18, "test-observation"), 18)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(trade.last_at, 18)
        with self.assertRaisesRegex(ValueError, "nondecreasing"):
            trade.manage("unsupported", None, Fact(True, 17, "test-observation"), 17)


if __name__ == "__main__":
    unittest.main()
