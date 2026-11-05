from dataclasses import replace
from decimal import Decimal
import unittest

from faraz_core.decision import decide_entry
from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.execution import (DemoBinding, Intent, MemoryExecutor, MockBroker,
                                  intent_from_authorization)
from tests.test_decision import fixture
from tools.run_offline_demo import build_demo


class IntegrationTests(unittest.TestCase):
    def test_synthetic_decision_unknown_partial_and_abc_replay(self):
        report = build_demo()
        self.assertEqual(report['mock_attempts'], 1)
        self.assertTrue(report['duplicate_mock_send_blocked'])
        self.assertTrue(report['logical_replay_equal'])
        self.assertEqual(Decimal(report['partial']['open_risk']), Decimal('16.50'))
        self.assertEqual(Decimal(report['partial']['unknown_risk']), Decimal('11.00'))
        self.assertFalse(report['order_authority'])
        self.assertFalse(report['market_performance_validated'])
        self.assertEqual(Decimal(report['settlement']['held_risk_after_confirmed_close']), 0)
        self.assertEqual(Decimal(report['settlement']['charged_realized_loss']), Decimal('2.10'))
        self.assertEqual(Decimal(report['settlement']['epoch_cap_unchanged']), 30)
        notional = report['notional_guard']
        self.assertEqual(Decimal(notional['combined_notional']), Decimal('8000.40'))
        self.assertGreater(Decimal(notional['combined_notional']), Decimal(notional['notional_cap']))
        self.assertEqual(notional['rejection'], 'FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL')
        self.assertEqual(notional['mock_attempts_after_rejection'], 1)
        self.assertIn('NOTIONAL_CAP', notional['honest_snapshot_reasons'])
        self.assertEqual([r['candidate'] for r in report['candidate_comparison']], ['A','B','C'])

    def test_fresh_executor_has_no_previous_positions_models_or_requests(self):
        fresh = MemoryExecutor(DemoBinding('new-synthetic-account', 0))
        self.assertEqual(fresh.state.intents, ())
        self.assertEqual(fresh.state.requests, ())
        self.assertEqual(fresh.state.ledger.total, 0)

    def test_proposal_payload_conflict_cannot_become_second_mock_send(self):
        c, r = fixture()
        p = decide_entry(c,r)
        policy = pin_policy(c,r)
        authorization = authorize_entry(c,r,2000)
        intent = intent_from_authorization(authorization,policy)
        engine = MemoryExecutor(DemoBinding(c.account_key,0,policy=policy,
                                budget_epoch_id='synthetic-test-epoch',epoch_risk_limit='20'))
        engine.transition('propose',intent)
        with self.assertRaises(ValueError):
            engine.transition('propose',replace(intent,payload_hash='changed-policy-or-cost'))
        self.assertEqual(engine.state.requests, ())

    def test_demo_executor_refuses_an_arbitrary_broker_adapter(self):
        c, _ = fixture()
        engine = MemoryExecutor(DemoBinding(c.account_key,0))
        with self.assertRaises(ValueError):
            engine.send(object(),'no-intent')
        with self.assertRaises(ValueError):
            DemoBinding('anything',0,mode='REAL')
