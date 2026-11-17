"""Owner-defined research gate tests; not teacher semantic certification."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from trade_machine import TradeMachine

D = Decimal

class RewardRiskGateTests(unittest.TestCase):
    def make(self):
        engine = SimpleNamespace(fingerprint="engine", evaluate=lambda rule, obs: SimpleNamespace(status="ELIGIBLE"))
        box = SimpleNamespace(fingerprint="box", risk_budget=D("100"), target_definition="fixed",
                              management_choices=(), declared_before_box=True)
        instrument = SimpleNamespace(min_lot=D("0.01"), lot_step=D("0.01"))
        costs = SimpleNamespace()
        observation = SimpleNamespace(side="BUY", at=100)
        return TradeMachine(engine, box, instrument, costs), observation

    def test_below_two_to_one_rejected_before_sizing(self):
        machine, observation = self.make()
        with patch("trade_machine.size_position", side_effect=AssertionError("must not size")):
            result = machine.prepare("ANY", observation, D("100"), D("95"), D("109"), D("100"))
        self.assertEqual(result["reason"], "INITIAL_REWARD_RISK_BELOW_TWO")
        self.assertEqual(machine.state, "NEW")

    def test_wrong_side_stop_rejected_before_sizing(self):
        machine, observation = self.make()
        with patch("trade_machine.size_position", side_effect=AssertionError("must not size")):
            result = machine.prepare("ANY", observation, D("100"), D("101"), D("110"), D("100"))
        self.assertEqual(result["reason"], "INITIAL_STOP_WRONG_SIDE")

    def test_exact_two_to_one_reaches_sizing(self):
        machine, observation = self.make()
        sized = {"status": "ACCEPT", "lots": D("0.01"), "modeled_loss": D("5")}
        with patch("trade_machine.size_position", return_value=sized) as sizing:
            result = machine.prepare("ANY", observation, D("100"), D("95"), D("110"), D("100"))
        self.assertEqual(result["status"], "PAPER_ENTRY_INTENT")
        sizing.assert_called_once()

if __name__ == "__main__":
    unittest.main()
