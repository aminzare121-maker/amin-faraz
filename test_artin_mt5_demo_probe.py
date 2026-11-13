import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from artin_mt5_demo_probe import probe, ProbeBlocked


def fake_mt5(mode=0,connected=True):
    mt5=Mock()
    mt5.initialize.return_value=True
    mt5.ACCOUNT_TRADE_MODE_DEMO=0
    mt5.account_info.return_value=SimpleNamespace(trade_mode=mode)
    mt5.terminal_info.return_value=SimpleNamespace(connected=connected,trade_allowed=True)
    mt5.symbol_info.return_value=SimpleNamespace(name='XAUUSD')
    return mt5


class DemoProbeTests(unittest.TestCase):
    def test_readonly_demo_probe_does_not_trade(self):
        mt5=fake_mt5()
        result=probe(mt5)
        self.assertEqual(result['account_mode'],'DEMO')
        self.assertFalse(result['demo_trade_test_passed'])
        self.assertEqual(result['orders_sent'],0)
        mt5.order_send.assert_not_called()
        mt5.shutdown.assert_called_once()

    def test_real_account_blocked(self):
        mt5=fake_mt5(mode=2)
        with self.assertRaisesRegex(ProbeBlocked,'NOT_DEMO'):
            probe(mt5)
        mt5.order_send.assert_not_called()
        mt5.shutdown.assert_called_once()

    def test_disconnected_terminal_blocked(self):
        mt5=fake_mt5(connected=False)
        with self.assertRaisesRegex(ProbeBlocked,'DISCONNECTED'):
            probe(mt5)
        mt5.shutdown.assert_called_once()


if __name__=='__main__':
    unittest.main()
