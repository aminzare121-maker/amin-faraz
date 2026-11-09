import unittest
from pathlib import Path
from artin_13_source_coverage_audit import SOURCE_CITATIONS,inspect_window,load_source,audit,spans_union_duration

ROOT=Path(__file__).resolve().parent/'EXTRACTED_25_SESSIONS'
class PureTests(unittest.TestCase):
    def test_exactly_13_entry_ids(self):
        self.assertEqual(len(SOURCE_CITATIONS),13)
    def test_merges_overlapping_ASR_without_double_counting(self):
        self.assertEqual(spans_union_duration([(0,5),(3,8),(20,30)],0,10),8)
    def test_no_speech_overlap_not_complaint_about_original_audio(self):
        s={21:{'rows':[{'start_seconds':10,'end_seconds':12,'visual_source_nearby':[],
                        'teacher_meaning_verified':False,'independent_speaker_and_wording_review_passed':False}],
               'first_observed_seconds':10,'last_observed_seconds':12,'file_sha256':'a'*64}}
        v=inspect_window(s,21,15,16)
        self.assertEqual(v['evidence_status'],'BEYOND_LAST_SAMPLED_ASR')
        self.assertTrue(v['missing_asr_not_proof_of_missing_original_audio'])
        self.assertFalse(v['teacher_semantics_certified'])
    def test_private_text_not_in_public(self):
        s={21:{'rows':[{'start_seconds':10,'end_seconds':12,'record_id':'id1','machine_text_unverified':'PRIVATE',
                'visual_source_nearby':[],'teacher_meaning_verified':False,
                'independent_speaker_and_wording_review_passed':False}],
                'first_observed_seconds':10,'last_observed_seconds':12,'file_sha256':'a'*64}}
        self.assertNotIn('PRIVATE',str(inspect_window(s,21,10,12)))
        self.assertIn('PRIVATE',str(inspect_window(s,21,10,12,include_private=True)))

@unittest.skipUnless((ROOT/'session_25_all_machine_speech_review.jsonl').is_file(),
                    'Private user lesson archive not on public GitHub runners')
class RealArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.result=audit(load_source(ROOT))
    def test_all_25_lessons_loaded_and_13_rules_counted(self):
        self.assertEqual(self.result['entry_rule_ids'],13)
        self.assertEqual(len(self.result['source_rules']),13)
    def test_all_source_citations_have_correct_lesson(self):
        self.assertTrue(all(all(w['session'] in range(1,26) for w in r['source_windows'])
                            for r in self.result['source_rules']))
    def test_no_teacher_verified_trade_claim(self):
        self.assertEqual(self.result['teacher_trade_rules_semantically_certified'],0)
        self.assertFalse(self.result['trading_permitted'])
    def test_session23_4694_citation_outside_sample(self):
        windows=[w for r in self.result['source_rules'] for w in r['source_windows']]
        v=next(x for x in windows if x['session']==23 and x['start_seconds']==4694)
        self.assertEqual(v['evidence_status'],'BEYOND_LAST_SAMPLED_ASR')
    def test_session21_4597_citation_outside_sample(self):
        windows=[w for r in self.result['source_rules'] for w in r['source_windows']]
        v=next(x for x in windows if x['session']==21 and x['start_seconds']==4597)
        self.assertEqual(v['evidence_status'],'BEYOND_LAST_SAMPLED_ASR')
if __name__=='__main__': unittest.main()