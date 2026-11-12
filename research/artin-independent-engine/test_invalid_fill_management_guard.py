"""Regression: an invalid paper fill cannot be managed as a valid position.

This is an offline safety test, not evidence of Artin teaching or MT5 execution.
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from trade_machine import TradeMachine
from entry_engine import Fact

class InvalidFillManagementTests(unittest.TestCase):
    def test_review_fill_cannot_move_stop(self):
        # Bypass constructor solely to isolate the state guard.
        t = object.__new__(TradeMachine)
        t.state = 'OPEN_REVIEW'
        t.trace = []
        t.last_at = 10
        t._fixed = lambda: None
        t._time = lambda at: None
        t.current_stop = Decimal('99')
        t.box = SimpleNamespace(management_choices=('reduce','riskfree','saveprofit'))
        result = t.manage('saveprofit', Decimal('101'), Fact(True, 10, 'test-only'), 10)
        self.assertEqual(result['status'], 'REVIEW')
        self.assertEqual(result['reason'], 'INVALID_ENTRY_FILL_REQUIRES_REVIEW_BEFORE_MANAGEMENT')
        self.assertEqual(t.current_stop, Decimal('99'))
        self.assertIsNone(result['realized_pnl'])

if __name__ == '__main__':
    unittest.main()
