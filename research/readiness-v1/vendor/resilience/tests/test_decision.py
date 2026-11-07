from dataclasses import replace
from decimal import localcontext
import unittest

from faraz_core.decision import EntryContext, decide_entry
from faraz_core.risk import VolumeRules, LinearRiskModel, RiskRequest
from faraz_core.temporal import Quote


def fixture():
    request = RiskRequest('synthetic-account', 'XAUUSD.SYNTHETIC', 'BUY',
                          '4000.20', '3995', '10',
                          VolumeRules('.01', '.01', '1', '2'),
                          LinearRiskModel('100', '10', '10', '10', '0', '1000'),
                          (), '1000', '100000', '30', '0', '0', '0', '0', '0')
    context = EntryContext(1000, 'synthetic-account', 'synthetic-account', 0, 0,
                           'DEMO', 'USD', 'HEDGING', True, True, True, True, 1000,
                           True, 1000, True, 1000, 1000,
                           Quote(1000, 1000, '4000', '4000.20'),
                           'synthetic-signal-1', 1000, 'BUY', 'synthetic-policy-v1',
                           '.01', '0', '.50', '0', '20', '0', '50', 0, 2,
                           'XAUUSD.SYNTHETIC', 0, 1000)
    return context, request


class DecisionTests(unittest.TestCase):
    def test_success_is_only_a_deterministic_proposal(self):
        c, r = fixture()
        a, b = decide_entry(c, r), decide_entry(c, r)
        self.assertEqual(a, b)
        self.assertEqual(a.action, 'ENTRY_PROPOSAL')
        self.assertEqual(str(a.risk.volume), '0.01')
        self.assertEqual(str(a.risk.risk), '5.5000')
        self.assertFalse(a.can_execute)

    def test_no_signal_no_trade(self):
        c, r = fixture()
        self.assertIn('NO_SIGNAL', decide_entry(replace(c, signal_side=None), r).reasons)

    def test_each_independent_veto_blocks_entry(self):
        c, r = fixture()
        changes = [{'account_mode': 'REAL'}, {'currency': 'EUR'}, {'connected': False},
                   {'clock_verified': False}, {'synthetic_source': False},
                   {'session_open': False}, {'news_clear': False}, {'ownership_clear': False},
                   {'account_revision': 1}, {'account_key': 'another-account'},
                   {'positions_and_pending': 2}, {'daily_loss': '20'}, {'total_loss': '50'},
                   {'account_observed_ms': 2001}, {'news_available_ms': 2001},
                   {'signal_available_ms': 2001}, {'max_spread': '.10'}, {'price_tick': '0'},
                   {'minimum_stop_distance': '10'}]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(decide_entry(replace(c, **change), r).action, 'NO_TRADE')

    def test_account_and_request_binding_cannot_diverge(self):
        c, r = fixture()
        self.assertEqual(decide_entry(c, replace(r, account_id='other')).action, 'NO_TRADE')

    def test_same_signal_key_different_payload_is_visible_to_executor(self):
        c, r = fixture()
        a = decide_entry(c, r)
        b = decide_entry(replace(c, max_spread='.60'), r)
        self.assertEqual(a.client_intent_id, b.client_intent_id)
        self.assertNotEqual(a.payload_hash, b.payload_hash)

    def test_bid_ask_entry_and_stop_grid_are_enforced(self):
        c, r = fixture()
        self.assertEqual(decide_entry(c, replace(r, entry='4000')).action, 'NO_TRADE')
        self.assertEqual(decide_entry(c, replace(r, stop='3995.001')).action, 'NO_TRADE')

    def test_unknown_costs_are_not_zero(self):
        c, r = fixture()
        bad = replace(r, model=replace(r.model, exit_cost_per_lot=None))
        self.assertEqual(decide_entry(c, bad).action, 'NO_TRADE')

    def test_loss_headroom_includes_new_and_unknown_risk(self):
        c, r = fixture()
        self.assertIn('DAILY_LOSS_HEADROOM', decide_entry(replace(c, daily_loss='19'), r).reasons)
        self.assertIn('TOTAL_LOSS_HEADROOM', decide_entry(replace(c, total_loss='49'), r).reasons)
        self.assertIn('DAILY_LOSS_HEADROOM', decide_entry(c, replace(r, held_unknown_risk='15')).reasons)

    def test_quote_symbol_and_risk_snapshot_binding(self):
        c, r = fixture()
        self.assertIn('QUOTE_SYMBOL_MISMATCH', decide_entry(c, replace(r, symbol='OTHER')).reasons)
        self.assertIn('ACCOUNT_BINDING_CHANGED', decide_entry(replace(c, account_revision=1, bound_account_revision=1), r).reasons)
        self.assertIn('RISK_SOURCE_UNAVAILABLE_OR_STALE', decide_entry(replace(c, risk_observed_ms=2000), r).reasons)

    def test_low_ambient_precision_does_not_accept_too_close_stop(self):
        c, r = fixture()
        c = replace(c, quote=Quote(1000,1000,'2.129','2.13'),
                    minimum_stop_distance='1.13', price_tick='.001')
        r = replace(r, entry='2.13', stop='1')
        normal = decide_entry(c,r)
        with localcontext() as ctx:
            ctx.prec = 3
            low_precision = decide_entry(c,r)
        self.assertEqual(normal, low_precision)
        self.assertIn('INVALID_STOP_DISTANCE', normal.reasons)
