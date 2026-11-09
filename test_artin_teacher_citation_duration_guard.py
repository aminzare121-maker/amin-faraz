import unittest
from artin_teacher_citation_duration_guard import audit,inspect_citation,VIDEO_DURATION_SECONDS

class DurationAuthorityTests(unittest.TestCase):
    def test_registry_has_25(self):
        self.assertEqual(len(VIDEO_DURATION_SECONDS),25)
    def test_all_13_and_24_original_legacy_references(self):
        result=audit()
        self.assertEqual(result['old_engine_rule_count'],13)
        self.assertEqual(result['old_engine_citation_count'],24)
    def test_ten_refs_beyond_current_queue_slot_duration(self):
        result=audit()
        self.assertEqual(result['citations_fit_current_queue_video_duration'],14)
        self.assertEqual(result['citations_beyond_current_queue_video_duration'],10)
    def test_four_impacted_entry_ids_blocked_not_remapped(self):
        result=audit()
        self.assertEqual(result['rules_with_unmatched_time_in_current_queue'],4)
        self.assertEqual(set(result['rules_requiring_source_identity_repair']),{
            'STOPPUNCH_SAME_COLOUR','STOPPUNCH_DOJI_AHEAD','STOPPUNCH_DOJI_TIED','STOPPUNCH_OPPOSITE_CONFIRMATION'})
        self.assertTrue(result['no_silent_reassignment_to_another_lesson'])
        self.assertFalse(result['replay_trade_and_profit_claims_permitted'])
    def test_legacy_video_21_citation_beyond_current_queue_end(self):
        x=inspect_citation(21,4597,4661)
        self.assertFalse(x['citation_fits_current_queue_video_duration'])
        self.assertGreater(x['seconds_start_after_current_queue_video_end'],995)
    def test_legacy_video_23_citation_beyond_current_queue_end(self):
        x=inspect_citation(23,4694,4728)
        self.assertFalse(x['citation_fits_current_queue_video_duration'])
    def test_legacy_may_have_different_source_21_index(self):
        r=audit()
        self.assertTrue(r['older_and_current_lesson_numbering_may_differ'])
        self.assertEqual(r['source_identity_mapping_verified_count'],0)
        self.assertEqual(r['legacy_source21_transcript_chunk_index_reaches_seconds'],6000)
    def test_boundary_valid_but_no_semantics_claim(self):
        x=inspect_citation(22,1888.1,1952.66)
        self.assertTrue(x['citation_fits_current_queue_video_duration'])
        self.assertEqual(x['evidence_status'],'TIME_WITHIN_CURRENT_QUEUE_SLOT_SOURCE_IDENTITY_UNVERIFIED')
    def test_bad_interval_rejected(self):
        for args in [(21,22,20),(21,0,0),(21,-1,1),(21,True,3),(26,1,2)]:
            with self.subTest(args=args),self.assertRaises(ValueError):inspect_citation(*args)
    def test_partial_overlap_not_accepted(self):
        x=inspect_citation(23,4199,4205)
        self.assertFalse(x['citation_fits_current_queue_video_duration'])
    def test_uncertain_mapping_does_not_approve_other_sourced_cases(self):
        r=audit()
        self.assertEqual(r['teacher_rules_certified'],0)
        self.assertTrue(all(not rule['method_backtest_permitted'] for rule in r['rules']))

if __name__=='__main__': unittest.main()