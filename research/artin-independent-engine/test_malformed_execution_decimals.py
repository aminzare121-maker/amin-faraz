"""Malformed numeric execution inputs must fail closed without state mutation."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from trade_machine import execution_event


class MalformedExecutionDecimalTests(unittest.TestCase):
    def test_malformed_quote_rejected_before_state_mutation(self):
        trade = SimpleNamespace(last_coordinator_at=None, last_event_known_at=None, last_at=None)
        trade._time = lambda at: None
        event = dict(event='quote', at=10, known_at=10, source='fixture', bid='not-a-number', ask='4001')
        with self.assertRaisesRegex(ValueError, 'valid finite event decimal required'):
            execution_event(trade, event, 10)
        self.assertIsNone(trade.last_coordinator_at)
        self.assertIsNone(trade.last_event_known_at)
        self.assertIsNone(trade.last_at)

    def test_nonfinite_quote_rejected(self):
        trade = SimpleNamespace(last_coordinator_at=None, last_event_known_at=None, last_at=None)
        trade._time = lambda at: None
        event = dict(event='quote', at=10, known_at=10, source='fixture', bid='NaN', ask='4001')
        with self.assertRaisesRegex(ValueError, 'finite event decimal required'):
            execution_event(trade, event, 10)


if __name__ == '__main__':
    unittest.main()
