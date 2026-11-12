"""Synthetic offline lifecycle regression; not a teacher replay or MT5 test."""
import unittest
from decimal import Decimal
from trade_machine import TradeMachine

D = Decimal

class ExitTriggerPendingFillTests(unittest.TestCase):
    def test_trigger_freezes_management_and_quotes_until_exit_fill(self):
        trade = object.__new__(TradeMachine)
        trade._fixed = lambda: None
        trade._time = lambda at: None
        trade.state = 'OPEN'
        trade.trace = []
        trade.plan = {'side': 'BUY', 'target': D('110')}
        trade.current_stop = D('95')
        trade.last_at = 0
        result = trade.quote(D('94'), D('95'), 1)
        self.assertEqual(result['status'], 'EXIT_TRIGGER')
        self.assertEqual(trade.state, 'EXIT_PENDING_FILL')
        self.assertIsNone(result['realized_pnl'])
        with self.assertRaises(ValueError):
            trade.quote(D('100'), D('101'), 2)
        with self.assertRaises(ValueError):
            trade.manage('reduce', D('96'), None, 2)

    def test_no_trigger_keeps_open_state(self):
        trade = object.__new__(TradeMachine)
        trade._fixed = lambda: None
        trade._time = lambda at: None
        trade.state = 'OPEN'
        trade.trace = []
        trade.plan = {'side': 'BUY', 'target': D('110')}
        trade.current_stop = D('95')
        trade.last_at = 0
        result = trade.quote(D('100'), D('101'), 1)
        self.assertEqual(result['status'], 'NO_EXIT_TRIGGER')
        self.assertEqual(trade.state, 'OPEN')

if __name__ == '__main__':
    unittest.main()
