"""Regression: a rejected event cannot rewind the coordinator's causal clock.

This is a software invariant test only, not teacher-method validation.
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from trade_machine import TradeMachine, execution_event
from capital import Instrument, Costs, BoxPlan

class CoordinatorClockTests(unittest.TestCase):
    def test_reject_rewind_before_mutation(self):
        class DummyEngine:
            fingerprint = "fixed"
        box = BoxPlan("clock-test", Decimal("10"), "manual target", ("reduce",), True)
        machine = TradeMachine(
            DummyEngine(), box,
            Instrument(Decimal("1"), Decimal("0.01"), Decimal("0.01")),
            Costs(Decimal("0"), Decimal("0")),
        )
        machine.last_coordinator_at = 200
        machine.last_at = 10
        with self.assertRaisesRegex(ValueError, "coordinator clock must be nondecreasing"):
            execution_event(machine, {
                "event": "quote", "at": 11, "known_at": 11,
                "source": "offline-regression", "bid": "100", "ask": "101",
            }, available_at=199)
        self.assertEqual(machine.last_coordinator_at, 200)
        self.assertEqual(machine.last_at, 10)
        self.assertEqual(machine.trace, [])

    def test_reject_future_availability_before_mutation(self):
        class DummyEngine:
            fingerprint = "fixed"
        machine = TradeMachine(
            DummyEngine(),
            BoxPlan("clock-test", Decimal("10"), "manual target", (), True),
            Instrument(Decimal("1"), Decimal("0.01"), Decimal("0.01")),
            Costs(Decimal("0"), Decimal("0")),
        )
        with self.assertRaisesRegex(ValueError, "event availability inconsistent"):
            execution_event(machine, {
                "event": "quote", "at": 10, "known_at": 20,
                "source": "offline-regression", "bid": "100", "ask": "101",
            }, available_at=19)
        self.assertIsNone(machine.last_coordinator_at)
        self.assertEqual(machine.trace, [])

if __name__ == "__main__":
    unittest.main()
