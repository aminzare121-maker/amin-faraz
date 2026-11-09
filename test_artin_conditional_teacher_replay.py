"""Fail-closed tests for exact text-anchored conditional lesson replay."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from artin_conditional_teacher_replay import compile_review, symbolic_contrast, recheck_source

ROOT=Path(__file__).parent
FILE=ROOT/'ARTIN_TEACHER_10_PROVISIONAL_DECISION_CASES_PRIVATE.json'

class ConditionalTests(unittest.TestCase):
    def test_weak_trend_forbids_provisional_trend_following(self):
        r=symbolic_contrast('A13-WEAK-TREND-REVERSE',{'trend_regime':'weak','proposal':'WITH_TREND'})
        self.assertTrue(r['provisional_text_conflict'])
        self.assertFalse(r['real_or_demo_order_permitted'])
    def test_weak_trend_reversal_is_not_auto_entry(self):
        r=symbolic_contrast('A13-WEAK-TREND-REVERSE',{'trend_regime':'weak','proposal':'REVERSAL','correction_seen':True})
        self.assertFalse(r['provisional_text_conflict'])
        self.assertFalse(r['teacher_expected_action_certified'])
    def test_piercing_condition_not_met(self):
        r=symbolic_contrast('A19-PIERCING-EXAMPLE',{'piercing_condition_met':False,'proposal':'ENTER'})
        self.assertTrue(r['provisional_text_conflict'])
    def test_piercing_condition_met_not_certified_entry(self):
        r=symbolic_contrast('A19-PIERCING-EXAMPLE',{'piercing_condition_met':True,'proposal':'ENTER'})
        self.assertFalse(r['provisional_text_conflict'])
        self.assertFalse(r['engine_matches_teacher_certified'])
    def test_breakout_two_branches_neither_auto_selected(self):
        for typ in ['IMMEDIATE','AFTER_PULLBACK']:
            x=symbolic_contrast('A15-BREAKOUT-VS-PULLBACK',{'breakout_occurred':True,'proposal':typ})
            self.assertEqual(x['text_candidate_result'],'UNKNOWN_BREAKOUT_BRANCH_CANNOT_AUTO_SELECT_ENTRY')
    def test_target2_hypothetical_not_universal_stop(self):
        for b in [True,False]:
            x=symbolic_contrast('A25-TARGET2-RISKFREE',{'target2_reached':b,'proposal':'MOVE_STOP'})
            self.assertFalse(x['real_or_demo_order_permitted'])
    def test_rr_example_only(self):
        x=symbolic_contrast('A24-RR-ARITHMETIC',{'risk':10,'reward':13})
        self.assertEqual(x['contextual_notes'][0]['illustrative_reward_to_risk_ratio'],1.3)
        self.assertIn('NOT_MINIMUM_RR',x['text_candidate_result'])
    def test_rr_nonfinite_invalid(self):
        x=symbolic_contrast('A24-RR-ARITHMETIC',{'risk':float('nan'),'reward':13})
        self.assertEqual(x['text_candidate_result'],'INVALID_RISK_REWARD_EXAMPLE')
    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):symbolic_contrast('UNAVAILABLE',{})
    def test_state_not_dict_rejected(self):
        with self.assertRaises(TypeError):symbolic_contrast('A19-PIERCING-EXAMPLE',[])

@unittest.skipUnless(FILE.is_file(),'Private teacher case corpus not available in public runner')
class PrivateCorpusTests(unittest.TestCase):
    def setUp(self):self.cases=json.loads(FILE.read_text(encoding='utf8'))
    def test_exact_original_10_source_anchors(self):
        for case in self.cases:
            self.assertEqual(len(recheck_source(case)['anchor_text_sha256']),64)
    def test_all_10_replayed_without_trades_or_fake_teacher_match(self):
        r=compile_review(FILE)
        self.assertEqual(r['source_anchored_cases'],10)
        self.assertGreaterEqual(r['counterfactual_tests'],20)
        self.assertFalse(r['teacher_audio_25_sessions_certified'])
        self.assertEqual(r['teacher_motor_decision_matches_certified'],0)
        self.assertTrue(all(not k['trade_permission'] for k in r['cases']))
    def test_missing_original_condition_refused(self):
        cases=copy.deepcopy(self.cases)
        cases[6]['machine_context']=[{'text':'missing source wording'}]*5
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text(json.dumps(cases,ensure_ascii=False),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'missing anchor phrases'):compile_review(p)
    def test_source_anchor_tampering_refused(self):
        cases=copy.deepcopy(self.cases)
        cases[0]['source_audio_sha256']='bogus'
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text(json.dumps(cases,ensure_ascii=False),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'invalid source_audio_sha256'):compile_review(p)
    def test_historical_execution_false_claim_refused(self):
        cases=copy.deepcopy(self.cases)
        cases[-1]['historical_order_proven']=True
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text(json.dumps(cases,ensure_ascii=False),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'unsupported certification'):compile_review(p)

if __name__=='__main__':unittest.main()