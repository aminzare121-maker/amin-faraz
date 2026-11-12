"""Regression: a management trigger must be an authentic, timed, sourced fact.

This is a software safety test, not validation of Artin's trading semantics.
"""
import unittest
from unittest.mock import Mock
from entry_engine import Fact
from trade_machine import TradeMachine


class ManagementTriggerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.trade = object.__new__(TradeMachine)
        self.trade._fixed = Mock()
        self.trade._time = Mock()
        self.trade.state = 'OPEN'
        self.trade.trace = []

    def test_rejects_invalid_timestamps_and_sources(self):
        bad = (
            Fact(True, -1, 'video'),
            Fact(True, True, 'video'),
            Fact(True, 11, 'video'),
            Fact(True, 5, ''),
            Fact(True, 5, '   '),
            Fact(True, 5, None),
        )
        for fact in bad:
            with self.subTest(fact=fact):
                result = self.trade.manage('reduce', None, fact, 10)
                self.assertEqual(result['status'], 'REVIEW')
                self.assertEqual(result['reason'], 'MANAGEMENT_TRIGGER_NOT_ESTABLISHED')
                self.assertEqual(result['realized_pnl'], None)

if __name__ == '__main__':
    unittest.main()
