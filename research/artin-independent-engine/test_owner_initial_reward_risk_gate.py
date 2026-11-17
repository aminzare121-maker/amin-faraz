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

    def test_adverse_fill_rechecks_two_to_one_and_enters_review(self):
        machine, observation = self.make()
        machine.instrument.money_per_price_unit_per_lot = D("1")
        machine.costs.adverse_price_allowance = D("0")
        machine.costs.round_trip_fee_per_lot = D("0")
        sized = {"status": "ACCEPT", "lots": D("0.01"), "modeled_loss": D("0.05")}
        with patch("trade_machine.size_position", return_value=sized):
            machine.prepare("ANY", observation, D("100"), D("95"), D("110"), D("100"))
        result = machine.fill_entry(D("101"), D("0.01"))
        self.assertEqual(result["status"], "OPEN_REVIEW")
        self.assertEqual(machine.state, "OPEN_REVIEW")

    def test_exact_two_to_one_fill_remains_open(self):
        machine, observation = self.make()
        machine.instrument.money_per_price_unit_per_lot = D("1")
        machine.costs.adverse_price_allowance = D("0")
        machine.costs.round_trip_fee_per_lot = D("0")
        sized = {"status": "ACCEPT", "lots": D("0.01"), "modeled_loss": D("0.05")}
        with patch("trade_machine.size_position", return_value=sized):
            machine.prepare("ANY", observation, D("100"), D("95"), D("110"), D("100"))
        result = machine.fill_entry(D("100"), D("0.01"))
        self.assertEqual(result["status"], "OPEN")

    def test_sell_adverse_fill_requires_review_without_order(self):
        machine, observation = self.make()
        observation.side = "SELL"
        machine.instrument.money_per_price_unit_per_lot = D("1")
        machine.costs.adverse_price_allowance = D("0")
        machine.costs.round_trip_fee_per_lot = D("0")
        sized = {"status": "ACCEPT", "lots": D("0.01"), "modeled_loss": D("0.05")}
        with patch("trade_machine.size_position", return_value=sized):
            intent = machine.prepare("ANY", observation, D("100"), D("105"), D("90"), D("100"))
        self.assertEqual(intent["status"], "PAPER_ENTRY_INTENT")
        self.assertFalse(intent["order_created"])
        adverse = machine.fill_entry(D("99"), D("0.01"))
        self.assertEqual(adverse["status"], "OPEN_REVIEW")
        self.assertFalse(adverse["order_created"])

    def test_sell_exact_two_to_one_fill_remains_paper_only(self):
        machine, observation = self.make()
        observation.side = "SELL"
        machine.instrument.money_per_price_unit_per_lot = D("1")
        machine.costs.adverse_price_allowance = D("0")
        machine.costs.round_trip_fee_per_lot = D("0")
        sized = {"status": "ACCEPT", "lots": D("0.01"), "modeled_loss": D("0.05")}
        with patch("trade_machine.size_position", return_value=sized):
            machine.prepare("ANY", observation, D("100"), D("105"), D("90"), D("100"))
        result = machine.fill_entry(D("100"), D("0.01"))
        self.assertEqual(result["status"], "OPEN")
        self.assertFalse(result["order_created"])

    def test_sell_wrong_side_stop_rejected_before_sizing(self):
        machine, observation = self.make()
        observation.side = "SELL"
        with patch("trade_machine.size_position", side_effect=AssertionError("must not size")):
            result = machine.prepare("ANY", observation, D("100"), D("95"), D("90"), D("100"))
        self.assertEqual(result["reason"], "INITIAL_STOP_WRONG_SIDE")
        self.assertFalse(result["order_created"])
        self.assertEqual(machine.state, "NEW")

    def test_sell_insufficient_reward_rejected_before_sizing(self):
        machine, observation = self.make()
        observation.side = "SELL"
        with patch("trade_machine.size_position", side_effect=AssertionError("must not size")):
            result = machine.prepare("ANY", observation, D("100"), D("105"), D("91"), D("100"))
        self.assertEqual(result["reason"], "INITIAL_REWARD_RISK_BELOW_TWO")
        self.assertFalse(result["order_created"])
        self.assertEqual(machine.state, "NEW")

if __name__ == "__main__":
    unittest.main()
