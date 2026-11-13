"""Offline exit-trigger lifecycle regression; not teacher or MT5 validation."""
import unittest
from decimal import Decimal as D
from types import SimpleNamespace
from capital import BoxPlan, Costs, Instrument
from entry_engine import Observation, Fact
from trade_machine import TradeMachine

class StubEngine:
    fingerprint = "offline-exit-test"
    def evaluate(self, rule_id, observation):
        return SimpleNamespace(status="ELIGIBLE", reasons=())

class ExitPendingFillTests(unittest.TestCase):
    def test_trigger_does_not_realize_pnl_or_allow_repeated_quote(self):
        m = TradeMachine(StubEngine(),
                         BoxPlan("exit-test", D("10"), "declared-target", ("saveprofit",), True),
                         Instrument(D("1"), D("1"), D("1")),
                         Costs(D("0"), D("0")))
        obs = Observation("BUY", 10, {"source_flag": Fact(True, 10, "offline-test")})
        self.assertEqual(m.prepare("test-rule", obs, D("100"), D("95"),
                                   D("110"), D("10"), D("1"))["status"], "PAPER_ENTRY_INTENT")
        self.assertEqual(m.fill_entry(D("100"), D("1"))["status"], "OPEN")
        trigger = m.quote(D("110"), D("111"), 11)
        self.assertEqual(trigger["status"], "EXIT_TRIGGER")
        self.assertEqual(m.state, "EXIT_PENDING_FILL")
        self.assertIsNone(trigger["realized_pnl"])
        self.assertFalse(trigger["fill_assumed"])
        with self.assertRaises(ValueError):
            m.quote(D("112"), D("113"), 12)
        with self.assertRaises(ValueError):
            m.manage("saveprofit", D("105"), Fact(True, 12, "offline-test"), 12)
        unknown = m.close(None, None)
        self.assertEqual(unknown["accounting"]["status"], "UNKNOWN")
        self.assertEqual(m.state, "EXIT_PENDING_FILL")
        pending = m.close(D("109"), None)
        self.assertEqual(pending["accounting"]["status"], "UNKNOWN")
        self.assertEqual(m.state, "CLOSED_PENDING_COST")
        closed = m.close(None, D("1"))
        self.assertEqual(closed["accounting"]["net_pnl"], D("8"))
        self.assertEqual(m.state, "CLOSED")
        self.assertTrue(all(not e["order_created"] for e in m.trace))

if __name__ == "__main__":
    unittest.main()
