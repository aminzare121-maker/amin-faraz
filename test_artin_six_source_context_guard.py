"""Regression guards for six original source-backed Artin ASR citation windows."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from artin_six_source_context_guard import EXPECTED_SPANS, inspect, write_reports

ROOT=Path(__file__).resolve().parent
PRIVATE_ROOT=ROOT/'RESTORED_SIX_ORIGINAL_AUDIO'
RESTORED=PRIVATE_ROOT/'ARTIN_RESTORED_SIX_AUDIO_AND_MACHINE_SPEECH_PRIVATE.json'
REMAP=ROOT/'ARTIN_LEGACY_26_TO_25_REMAP_PUBLIC_20261110.json'

class BaselineTests(unittest.TestCase):
    def test_six_citations_five_distinct_intervals(self):
        self.assertEqual(len(EXPECTED_SPANS),6)
        self.assertEqual(len(set((x[1],x[2],x[3]) for x in EXPECTED_SPANS)),5)

@unittest.skipUnless(RESTORED.exists() and REMAP.exists(),"private ASR/audio missing from public GitHub")
class PrivateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=json.loads(RESTORED.read_text(encoding='utf8'))
        cls.legacy=json.loads(REMAP.read_text(encoding='utf8'))
    def test_full_24_citations_get_machine_speech_not_semantic_approval(self):
        r=inspect(self.src,self.legacy,PRIVATE_ROOT)
        self.assertEqual((r['machine_speech_citations_now_present'],r['citations_without_machine_asr_after_recovery']),(24,0))
        self.assertFalse(r['independent_audio_listening_complete'])
        self.assertEqual(r['teacher_rule_verified_count'],0)
        self.assertEqual(r['mt5_entries_authorized'],0)
    def test_doji_shared_audio_is_not_independent_confirmation(self):
        r=inspect(self.src,self.legacy,PRIVATE_ROOT)
        self.assertEqual(r['unique_new_timed_intervals'],5)
        self.assertTrue(any(x['topic']=='day_count_doji_branch_cannot_be_proved_from_shared_segment' for x in r['context_links']))
    def test_missing_source_excerpt_fails_closed(self):
        x=copy.deepcopy(self.src)
        x['private_review_windows'][0]['audio_excerpt_file']='does-not-exist.wav'
        with self.assertRaisesRegex(ValueError,'WAV excerpt digest'):
            inspect(x,self.legacy,PRIVATE_ROOT)
    def test_speaker_fabrication_fails_closed(self):
        x=copy.deepcopy(self.src)
        x['private_review_windows'][0]['teacher_speaker_verified']=True
        with self.assertRaisesRegex(ValueError,'source authority'):
            inspect(x,self.legacy,PRIVATE_ROOT)
    def test_altered_citation_fails_closed(self):
        x=copy.deepcopy(self.src)
        x['private_review_windows'][0]['start_seconds']+=1
        with self.assertRaisesRegex(ValueError,'altered'):
            inspect(x,self.legacy,PRIVATE_ROOT)
    def test_forged_asr_speaker_rejected(self):
        x=copy.deepcopy(self.src)
        x['private_review_windows'][0]['recovered_machine_asr_segments'][0]['speaker_status']='TEACHER'
        with self.assertRaisesRegex(ValueError,'speaker'):
            inspect(x,self.legacy,PRIVATE_ROOT)
    def test_two_reports_privacy_separation(self):
        with tempfile.TemporaryDirectory() as d:
            write_reports(RESTORED,REMAP,PRIVATE_ROOT,Path(d))
            private=(Path(d)/'ARTIN_SIX_RECOVERED_SOURCE_REVIEW_PRIVATE.json').read_text()
            public=(Path(d)/'ARTIN_SIX_RECOVERED_SOURCE_REVIEW_PUBLIC.json').read_text()
            self.assertIn('text_unverified',private)
            self.assertNotIn('text_unverified',public)
            self.assertNotIn('raw_machine_asr_review_windows',public)

if __name__=='__main__':unittest.main()