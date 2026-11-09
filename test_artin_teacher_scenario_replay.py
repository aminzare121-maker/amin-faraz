import json
import tempfile
import unittest
from pathlib import Path
from artin_teacher_scenario_replay import evaluate, compile_private_cases

ROOT=Path(__file__).parent
CASES=ROOT/'ARTIN_TEACHER_10_PROVISIONAL_DECISION_CASES_PRIVATE.json'

class SymbolicTests(unittest.TestCase):
    def c(self,kind):return {'case_id':'test','scenario_type':kind}
    def test_true_hypothetical_weak_trend_not_executable(self):
        x=evaluate(self.c('WEAK_TREND'),{'trend_regime':'weak'})
        self.assertEqual(x['interpretation'],'REVERSAL_AFTER_CORRECTION_CONCEPT')
        self.assertFalse(x['trade_authorized'])
    def test_breakout_kind_not_inferred(self):
        x=evaluate(self.c('BREAKOUT'),{'breakout_occurred':True})
        self.assertEqual(x['interpretation'],'PULLBACK_VS_IMMEDIATE_BRANCH_UNRESOLVED')
        self.assertFalse(x['trade_authorized'])
    def test_piercing_illustration_not_trade(self):
        x=evaluate(self.c('PIERCING'),{'teacher_described_piercing':True})
        self.assertEqual(x['interpretation'],'CONDITIONAL_ENTRY_MENTIONED')
        self.assertFalse(x['trade_authorized'])
    def test_target2_riskfree_not_automatic_stop_change(self):
        x=evaluate(self.c('TARGET2_RISKFREE'),{'target2_reached':True})
        self.assertEqual(x['interpretation'],'BREAK_EVEN_STOP_MOVE_ILLUSTRATION')
        self.assertFalse(x['trade_authorized'])
        self.assertIn('commission_adjustment',x['missing_to_execute'])
    def test_risk_reward_math_only(self):
        x=evaluate(self.c('RR_ARITHMETIC'),{'risk':10,'reward':13})
        self.assertEqual(x['illustrative_rr'],1.3)
        self.assertFalse(x['trade_authorized'])
    def test_zero_risk_cannot_divide(self):
        x=evaluate(self.c('RR_ARITHMETIC'),{'risk':0,'reward':13})
        self.assertEqual(x['interpretation'],'NEED_VALID_NUMERIC_RISK_AND_REWARD')
        self.assertNotIn('illustrative_rr',x)
    @unittest.skipUnless(CASES.is_file(), 'Private candidate cases not available in public GitHub CI')
    def test_provenance_required(self):
        rows=json.loads(CASES.read_text())
        rows[0]['source_audio_sha256']=None
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text(json.dumps(rows))
            with self.assertRaises(ValueError): compile_private_cases(p)
    @unittest.skipUnless(CASES.is_file(), 'Private candidate cases not available in public GitHub CI')
    def test_claimed_historical_order_rejected(self):
        rows=json.loads(CASES.read_text())
        rows[0]['historical_order_proven']=True
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text(json.dumps(rows))
            with self.assertRaises(ValueError): compile_private_cases(p)
    @unittest.skipUnless(CASES.is_file(), 'Private candidate cases not available in public GitHub CI')
    def test_full_real_cases_source_hashes_and_no_orders(self):
        o=compile_private_cases(CASES)
        self.assertEqual(o['candidate_cases'],10)
        self.assertTrue(all(len(c['source_audio_sha256'])==64 for c in o['cases']))
        self.assertTrue(all(not c['execution_authorized'] and not c['replay']['trade_authorized'] for c in o['cases']))
        self.assertFalse(o['independent_teacher_meaning_verified'])
        self.assertFalse(o['trading_authorized'])

if __name__=='__main__':unittest.main()