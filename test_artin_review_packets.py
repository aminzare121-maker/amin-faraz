import unittest
from pathlib import Path
from artin_review_packets import packetize
P=Path(__file__).resolve().parent
FILES=('بهروز.zip','Artin_22_Sessions_Speech_OCR_Review_20261109.zip')
@unittest.skipUnless(all((P/f).exists() for f in FILES),'Private Behrooz files unavailable in public GitHub CI')
class RealArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private, cls.public=packetize(P)
    def test_150_cases_25_sessions(self):
        self.assertEqual(self.public['machine_speech_sessions'],25)
        self.assertEqual(self.public['review_packets_count'],150)
    def test_no_automatic_teacher_decisions(self):
        self.assertEqual(self.public['teacher_expected_decisions_verified'],0)
        self.assertEqual(self.public['engine_replays_against_teacher_verified'],0)
        self.assertFalse(self.public['mt5_trading_authorized'])
    def test_source_and_context_present(self):
        for case in self.private['packets']:
            self.assertTrue(case['source_audio_sha256'])
            self.assertTrue(case['spoken_context_unverified'])
    def test_flags_partition_selected_speech(self):
        n=self.public['flag_counts']
        self.assertGreater(n['short_speech_fragment'],0)
        self.assertEqual(n['literal_condition']+n['context_only_condition'],
                         sum(p['literal_condition_in_selected_segment'] or p['conditional_keyword_only_in_surrounding_context']
                             for p in self.private['packets']))
if __name__=='__main__':unittest.main()