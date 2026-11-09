"""Proof obligations and conservative fallbacks for the 26->25 Artin source shift."""
import unittest
from pathlib import Path
from artin_legacy_identity_reconciliation import (LEGACY_LAST_NONEMPTY_CHUNK_START,
    VIDEO_DURATION_SECONDS,remap_citation,validate_shift,reconcile)
from artin_13_source_coverage_audit import SOURCE_CITATIONS
ROOT=Path(__file__).resolve().parent/'EXTRACTED_25_SESSIONS'

class MappingTests(unittest.TestCase):
    def test_minus_one_all_25_chunks_fit_source_video_duration(self):
        out=validate_shift(-1)
        self.assertTrue(out['all_25_mapped_without_duration_conflict'])
        self.assertEqual(out['mapped'],25)
        self.assertEqual(out['chunk_start_exceeds_video'],[])
    def test_no_offset_does_not_fit_current_registry(self):
        self.assertFalse(validate_shift(0)['all_25_mapped_without_duration_conflict'])
        self.assertEqual(len(validate_shift(0)['chunk_start_exceeds_video']),9)
    def test_plus_one_not_a_complete_mapping(self):
        self.assertFalse(validate_shift(1)['all_25_mapped_without_duration_conflict'])
    def test_video21_maps_from_legacy22(self):
        self.assertEqual(remap_citation(22,1888.1,1952.66),(21,1888.1,1952.66))
    def test_legacy21_late_source_maps_to_queue20(self):
        self.assertEqual(remap_citation(21,4597,4661),(20,4597,4661))
    def test_legacy23_late_source_maps_to_queue22(self):
        self.assertEqual(remap_citation(23,4694,4728),(22,4694,4728))
    def test_old_legacy21_must_not_be_treated_as_current21(self):
        with self.assertRaises(ValueError):remap_citation(21,4597,4661,offset=0)
    def test_no_guess_on_impossible_timestamp(self):
        with self.assertRaises(ValueError):remap_citation(21,6000,7000)
    def test_negative_timestamp_rejected(self):
        with self.assertRaises(ValueError):remap_citation(21,-1,5)
    def test_legacy1_missing_is_not_filled_from_guess(self):
        with self.assertRaises(ValueError):remap_citation(1,100,110)
    def test_13_rule_24_source_windows_exact(self):
        r=reconcile()
        self.assertEqual(r['legacy_entry_rule_ids'],13)
        self.assertEqual(r['legacy_citation_windows'],24)
        self.assertEqual(r['legacy_citation_windows_out_of_current_video_duration'],0)
        self.assertFalse(r['m15_trade_backtest_authorized'])
    def test_converted_sources_keep_original_intervals(self):
        r=reconcile()
        for rule,refs in SOURCE_CITATIONS.items():
            new=r['candidate_source_map_not_auto_installed'][rule]
            self.assertEqual(new,[[s-1,a,b] for s,a,b in refs])
    def test_no_teacher_trading_or_audio_certification(self):
        r=reconcile()
        self.assertEqual(r['teacher_strategy_rules_certified'],0)
        self.assertFalse(r['teacher_speaker_and_wording_independently_verified'])
        self.assertFalse(r['mt5_trade_permitted'])
        self.assertTrue(all(not x['trade_permitted'] for x in r['rules']))
    def test_tampered_legacy_chunk_fails_whole_mapping(self):
        bad=dict(LEGACY_LAST_NONEMPTY_CHUNK_START);bad[21]=7000
        with self.assertRaises(ValueError):reconcile(chunk_starts=bad)
    def test_tampered_registry_duration_fails_whole_mapping(self):
        bad=dict(VIDEO_DURATION_SECONDS);bad[20]=3600
        with self.assertRaises(ValueError):reconcile(durations=bad)
    def test_bad_offset_type_rejected(self):
        with self.assertRaises(TypeError):validate_shift('minus one')
    def test_nonempty_citation_list_required(self):
        with self.assertRaises(ValueError):reconcile(citations={})

@unittest.skipUnless(ROOT.is_dir() and (ROOT/'session_25_all_machine_speech_review.jsonl').exists(),
                     'private archived speech files not available in public CI')
class OriginalPrivateArchiveTests(unittest.TestCase):
    def test_24_windows_no_out_of_video_with_original_source(self):
        r=reconcile(ROOT)
        self.assertEqual(r['legacy_citation_windows'],24)
        self.assertEqual(r['legacy_citation_windows_out_of_current_video_duration'],0)
        self.assertEqual(r['mapped_current_queue_videos'],25)
    def test_original_asr_18_present_6_absent(self):
        r=reconcile(ROOT)
        self.assertEqual(r['with_current_asr_overlap'],18)
        self.assertEqual(r['without_current_asr_overlap'],6)
    def test_no_original_speaker_verified_even_with_asr(self):
        r=reconcile(ROOT)
        self.assertEqual(r['teacher_strategy_rules_certified'],0)
        self.assertFalse(r['mt5_trade_permitted'])
        self.assertTrue(any(x['current_transcript_status']=='MISSING_TIMED_ASR_NEEDS_SOURCE_RECOVERY'
                            for y in r['rules'] for x in y['source_citations']))

if __name__=='__main__':unittest.main()