import unittest
from pathlib import Path
from artin_visual_supplement import FRAME_TIME, audit

ROOT=Path(__file__).resolve().parent
PRIVATE=['Artin_Six_Source_Semantic_Cases_20261109.zip','Artin_66_Original_Frames_SourceLinked_20261109.zip','EXTRACTED_25_SESSIONS/session_15_all_machine_speech_review.jsonl']

class SourceFrameTests(unittest.TestCase):
    def test_extract_time_from_real_source_naming_convention(self):
        m=FRAME_TIME.search('board/b001_s06_g000006_t0001545000_board.png')
        self.assertEqual(int(m.group(1))/1000,1545)
    def test_unrelated_path_has_no_frame_time(self):
        self.assertIsNone(FRAME_TIME.search('random.png'))

    @unittest.skipUnless(all((ROOT/p).exists() for p in PRIVATE),'Private original archives unavailable on public runner')
    def test_original_six_source_board_frames(self):
        result=audit(ROOT)
        self.assertEqual(result['verified_original_board_frames'],6)
        self.assertEqual(result['missing_from_automatic_nearby_index'],1)
        self.assertEqual([x['case_id'] for x in result['cases'] if x['supplement_required']],['A15-BREAKOUT-VS-PULLBACK'])
        self.assertTrue(all(x['original_image_sha256_verified'] for x in result['cases']))
        self.assertTrue(all(x['abs_delta_seconds']<=8 for x in result['cases']))
        self.assertFalse(result['trading_allowed'])
        self.assertEqual(result['semantic_rules_certified'],0)
if __name__=='__main__':unittest.main()