"""Coverage tests: real private archive executed locally; CI skips private archives."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_full_coverage_index import build

ROOT = Path(__file__).resolve().parent
NEEDED = ['بهروز.zip', 'Artin_22_Sessions_Speech_OCR_Review_20261109.zip']

@unittest.skipUnless(all((ROOT / p).exists() for p in NEEDED), 'Private Behrooz archives not available in public runner')
class RealSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.zip_path = Path(cls.tmp.name) / 'inventory.zip'
        cls.summary_path = Path(cls.tmp.name) / 'inventory.json'
        cls.report = build(ROOT, cls.zip_path, cls.summary_path)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def test_25_sessions_all_speech_covered(self):
        self.assertEqual(len(self.report['files']), 25)
        self.assertEqual(sum(x['rows'] for x in self.report['files']), 10235)
        self.assertEqual(self.report['machine_speech_rows_covered'], 10235)
    def test_every_entry_is_unverified(self):
        with zipfile.ZipFile(self.zip_path) as z:
            for n in range(1, 26):
                name = f'session_{n:02d}_all_machine_speech_review.jsonl'
                entries = [json.loads(line) for line in z.read(name).splitlines() if line]
                self.assertEqual(len(entries), self.report['files'][n-1]['rows'])
                self.assertTrue(all(not row['teacher_meaning_verified'] and not row['trade_permitted'] for row in entries))
    def test_source_hashes_and_archive_roundtrip(self):
        import hashlib
        with zipfile.ZipFile(self.zip_path) as z:
            for item in self.report['files']:
                raw = z.read(item['file'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256'])
                self.assertTrue(all(len(json.loads(line)['source_audio_sha256']) == 64 for line in raw.splitlines() if line))
    def test_hypothetical_scenarios_remain_candidate_not_historical(self):
        with zipfile.ZipFile(self.zip_path) as z:
            for item in self.report['files']:
                for line in z.read(item['file']).splitlines():
                    row=json.loads(line)
                    self.assertTrue(row['hypothetical_case_not_rejected_as_invalid'])
                    self.assertFalse(row['observed_historical_trade_proven'])

if __name__ == '__main__': unittest.main()