import unittest
from pathlib import Path
from artin_replay_stage import build, decision_comparison
ROOT=Path(__file__).resolve().parent
NEEDED=(
    'Artin_Six_Source_Semantic_Cases_20261109.zip',
    'Artin_Four_Additional_Semantic_Cases_20261109.zip',
    'Artin_22_Sessions_Speech_OCR_Review_20261109.zip',
)
def verified_case():
    return {'speaker_verified':True,'audio_visual_meaning_verified':True,
            'decision_conditions_complete':True,'exceptions_complete':True,
            'cross_session_precedence_resolved':True,
            'teacher_expected_decision_verified':'NO_TRADE'}

class Tests(unittest.TestCase):
    @unittest.skipUnless(all((ROOT / name).is_file() for name in NEEDED),
                         'Private archives not available in public GitHub runner')
    def test_actual_25_sessions_and_10_cases(self):
        r=build(ROOT)
        self.assertEqual(r['session_count'],25)
        self.assertEqual(r['candidate_cases_count'],10)
        self.assertEqual(len(r['cross_session_candidate_links']),8)
        self.assertEqual(len(r['chronology_errors']),1)
        self.assertFalse(r['semantic_certificate'])
        self.assertFalse(r['allow_mt5_trading'])
        self.assertTrue(all(c['replay_status']=='BLOCKED_UNVERIFIED_TEACHER_DECISION'
                            for c in r['candidate_cases']))
    def test_hypothetical_keeps_value_without_unverified_trade(self):
        case=verified_case()
        case['scenario_class']='TEACHING_HYPOTHETICAL_MARKET_STATE'
        case['speaker_verified']=False
        self.assertEqual(decision_comparison(case,'NO_TRADE'),
                         'BLOCKED_UNVERIFIED_TEACHER_DECISION')
    def test_verified_teacher_motor_agree_or_disagree(self):
        case=verified_case()
        self.assertEqual(decision_comparison(case,'NO_TRADE'),'PASS')
        self.assertEqual(decision_comparison(case,'ENTER'),'FAIL_MOTOR_DISAGREES_WITH_TEACHER')
        self.assertEqual(decision_comparison(case,None),'BLOCKED_NO_ENGINE_DECISION')
    def test_unknown_condition_blocks(self):
        case=verified_case()
        case['decision_conditions_complete']=False
        self.assertEqual(decision_comparison(case,'NO_TRADE'),
                         'BLOCKED_UNVERIFIED_TEACHER_DECISION')
if __name__=='__main__':unittest.main()
