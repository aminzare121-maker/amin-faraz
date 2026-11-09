"""Private archive integration and fail-closed review queue tests (local only)."""
import json
import unittest
from pathlib import Path
from artin_full_review_queue import build, load, SHA, candidate_score, norm

HERE = Path(__file__).resolve().parent
class SyntheticTests(unittest.TestCase):
    def test_orthography_normalization(self):
        self.assertEqual(norm('اگر   قيمت به مقاومت  برسد'), 'اگر قیمت به مقاومت برسد')
    def test_hypothetical_market_example_is_candidate(self):
        x=[{'start':1., 'end':2., 'text':'اگر قیمت مقاومت را شکست بعد از پولبک ورود', 'raw_visual':[]}]
        score,topics,conditional,context=candidate_score(x,0)
        self.assertTrue(conditional)
        self.assertIn('entry',topics)
        self.assertIn('market_state',topics)
        self.assertGreater(score,0)
    def test_short_invalid_source_digest(self):
        self.assertFalse(SHA.fullmatch('not-a-sha'))

@unittest.skipUnless(all((Path(__file__).resolve().parent / name).exists() for name in
 ('بهروز.zip','Artin_22_Sessions_Speech_OCR_Review_20261109.zip')),
 'Private Behrooz archives are not available in public CI')
class RealArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.summary = build(HERE)
    def test_25_lessons_have_speech_evidence(self):
        self.assertEqual(self.out['session_count'], 25)
        self.assertEqual([s['session'] for s in self.out['per_session']],list(range(1,26)))
        self.assertTrue(all(s['machine_speech_rows']>0 for s in self.out['per_session']))
    def test_review_queue_covers_25_in_original_order(self):
        self.assertTrue(all(s['candidate_review_cases']>0 for s in self.out['per_session']))
        self.assertEqual(self.out['cases_for_human_audio_visual_review'],len(self.out['cases']))
        self.assertTrue(all(c['time_start_seconds']<=c['time_end_seconds'] for c in self.out['cases']))
    def test_sha_and_nearby_visual_references(self):
        for c in self.out['cases']:
            self.assertTrue(SHA.fullmatch(c['source_anchor']['source_audio_sha256']))
            for v in c['visual_candidates']:
                self.assertTrue(SHA.fullmatch(v['sha']))
                self.assertLessEqual(abs(v['delta_seconds']),8)
    def test_hypotheticals_not_rejected_and_no_historical_fabrication(self):
        self.assertGreater(self.out['hypothetical_scenarios_preserved'],0)
        for case in self.out['cases']:
            self.assertTrue(case['hypothetical_is_legitimate_teaching_scenario'])
            self.assertFalse(case['source_verified_to_be_historical_trade'])
            self.assertIsNone(case['teacher_expected_decision'])
    def test_precedence_links_are_ordered_but_not_teacher_verified(self):
        cases={x['case_id']:x for x in self.out['cases']}
        for link in self.out['links']:
            self.assertLess(cases[link['earlier']]['session'], cases[link['later']]['session'])
            self.assertFalse(link['instruction_supersession_verified'])
    def test_no_trading_permission_in_review_stage(self):
        self.assertFalse(self.out['allow_mt5_trade'])
        self.assertEqual(self.out['independently_verified_teacher_decisions'],0)
        self.assertTrue(all(not c['allow_mt5_trade'] for c in self.out['cases']))
        self.assertTrue(all(not c['teaching_meaning_verified'] for c in self.out['cases']))
    def test_general_analogies_not_auto_classified_as_trade_rules(self):
        self.assertEqual(self.out['general_analogies_needing_classroom_relevance_review'],
                         sum(c['candidate_class']=='GENERAL_ANALOGY_NOT_A_TRADE_RULE' for c in self.out['cases']))

if __name__=='__main__':unittest.main(verbosity=2)