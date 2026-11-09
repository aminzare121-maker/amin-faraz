"""Fail-closed checks for lossless Artin technical-speech triage."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_technical_speech_inventory import norm, topic_terms, scan_records, process

ROOT=Path(__file__).resolve().parent/'EXTRACTED_25_SESSIONS'
HAS_PRIVATE=ROOT.exists() and all((ROOT/f'session_{n:02d}_all_machine_speech_review.jsonl').is_file() for n in range(1,26))

class UnitTests(unittest.TestCase):
    def test_persian_normalization(self):
        self.assertEqual(norm('اين  پول‌بک'), 'این پول بک')

    def test_teacher_hypothetical_kept_as_topic(self):
        self.assertIn('price_action_chart',topic_terms('اگر قیمت به مقاومت رسید و پولبک زد'))

    def test_risk_and_condition_remain_distinct(self):
        t=topic_terms('اگه به استاپ لاس رسید ریسک معامله ما چقدره')
        self.assertIn('risk_management',t)
        self.assertIn('entry_exit_conditions',t)

    def test_nontechnical_not_guaranteed_nontechnical(self):
        self.assertEqual(topic_terms('دوستان صدا میاد'),{})

    def test_reject_bad_audio_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.jsonl'
            p.write_text(json.dumps({'session':1,'row':0,'source_audio_sha256':'x',
                                     'start_seconds':0,'end_seconds':1})+'\n')
            with self.assertRaisesRegex(ValueError,'Invalid audio SHA'):
                scan_records(p)

    def test_reject_time_reversal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.jsonl'
            p.write_text(json.dumps({'session':1,'row':0,'source_audio_sha256':'a'*64,
                                     'start_seconds':10,'end_seconds':1})+'\n')
            with self.assertRaisesRegex(ValueError,'Invalid timing'):
                scan_records(p)

@unittest.skipUnless(HAS_PRIVATE,'Private Artin machine-ASR archive not available in public GitHub CI')
class PrivateArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();p=Path(cls.temp.name)
        cls.z=p/'technical.zip';cls.summary=process(ROOT,cls.z,p/'summary.json')
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_lossless_25_session_source_roundtrip(self):
        self.assertEqual(self.summary['sessions'],25)
        self.assertEqual(self.summary['total_machine_speech_rows_preserved'],10235)
        s=self.summary
        self.assertEqual(s['direct_topic_candidate_rows']+s['context_only_candidate_rows']+s['unclassified_rows_preserved'],10235)
        with zipfile.ZipFile(self.z) as z:
            self.assertEqual(z.testzip(),None)
            for n in range(1,26):
                src=[json.loads(x) for x in (ROOT/f'session_{n:02d}_all_machine_speech_review.jsonl').read_text().splitlines() if x]
                dst=[json.loads(x) for x in z.read(f'technical_review_session_{n:02d}.jsonl').splitlines() if x]
                self.assertEqual(len(src),len(dst))
                self.assertEqual([(r['record_id'],r['machine_text_unverified'],r['source_audio_sha256']) for r in src],
                                 [(r['record_id'],r['raw_machine_text_unverified'],r['source_audio_sha256']) for r in dst])
    def test_all_decision_claims_remain_unverified(self):
        with zipfile.ZipFile(self.z) as z:
            for n in range(1,26):
                for line in z.read(f'technical_review_session_{n:02d}.jsonl').splitlines():
                    r=json.loads(line)
                    self.assertFalse(r['teacher_method_semantically_verified'])
                    self.assertFalse(r['motor_decision_approved'])
                    self.assertFalse(r['trade_permitted'])

if __name__=='__main__': unittest.main()