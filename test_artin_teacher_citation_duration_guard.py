import unittest
from artin_teacher_citation_duration_guard import audit,inspect_citation,VIDEO_DURATION_SECONDS

class DurationAuthorityTests(unittest.TestCase):
    def test_registry_has_25(self):
        self.assertEqual(len(VIDEO_DURATION_SECONDS),25)
    def test_all_13_and_24_original_legacy_references(self):
        result=audit()
        self.assertEqual(result['old_engine_rule_count'],13)
        self.assertEqual(result['old_engine_citation_count'],24)
    def test_exactly_ten_references_past_original_video_end(self):
        result=audit()
        self.assertEqual(result['citations_inside_video_duration'],14)
        self.assertEqual(result['citations_outside_video_duration'],10)
    def test_four_impacted_entry_ids_blocked_not_remapped(self):
        result=audit()
        self.assertEqual(result['rules_with_invalid_citation'],4)
        self.assertEqual(set(result['rules_blocked_by_source_identity']),{
            'STOPPUNCH_SAME_COLOUR','STOPPUNCH_DOJI_AHEAD','STOPPUNCH_DOJI_TIED','STOPPUNCH_OPPOSITE_CONFIRMATION'})
        self.assertTrue(result['no_silent_reassignment_to_another_lesson'])
        self.assertFalse(result['replay_trade_and_profit_claims_permitted'])
    def test_legacy_video_21_citation_after_actual_film_end(self):
        x=inspect_citation(21,4597,4661)
        self.assertFalse(x['source_citation_within_original_video'])
        self.assertGreater(x['seconds_start_after_original_end'],995)
    def test_legacy_video_23_citation_after_actual_film_end(self):
        x=inspect_citation(23,4694,4728)
        self.assertFalse(x['source_citation_within_original_video'])
    def test_boundary_valid_but_no_semantics_claim(self):
        x=inspect_citation(22,1888.1,1952.66)
        self.assertTrue(x['source_citation_within_original_video'])
        self.assertEqual(x['evidence_status'],'WITHIN_VIDEO_BOUNDS_UNVERIFIED_SEMANTICS')
    def test_bad_interval_rejected(self):
        for args in [(21,22,20),(21,0,0),(21,-1,1),(21,True,3),(26,1,2)]:
            with self.subTest(args=args),self.assertRaises(ValueError):inspect_citation(*args)
    def test_partial_overlap_not_accepted(self):
        x=inspect_citation(23,4199,4205)
        self.assertFalse(x['source_citation_within_original_video'])
    def test_uncertain_mapping_does_not_approve_other_sourced_cases(self):
        r=audit()
        self.assertEqual(r['teacher_rules_certified'],0)
        self.assertTrue(all(not rule['method_backtest_permitted'] for rule in r['rules']))

if __name__=='__main__': unittest.main()