"""Fail-closed image/audio timing audit: synthetic and original private artifacts."""
import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_original_visual_time_gate import (build_audit,_gap,_validate_zip,EXPECTED_WINDOWS,FRAME_NAME,SOURCE_BOARD_SHA256)
ROOT=Path(__file__).parent
ORIGINAL=ROOT/'RESTORED_SIX_ORIGINAL_AUDIO'/'ARTIN_RESTORED_SIX_AUDIO_AND_MACHINE_SPEECH_PRIVATE.json'
BOARD20=Path('/mnt/data/artin20_original_board.zip')
BOARD22=Path('/mnt/data/artin22_original_board.zip')

class SafeArchive(unittest.TestCase):
    def test_expected_citations_five_unique_intervals(self):
        self.assertEqual(len(EXPECTED_WINDOWS),6)
        self.assertEqual(len({x[1:] for x in EXPECTED_WINDOWS}),5)
    def test_distance_zero_inside_and_positive_outside(self):
        self.assertEqual(_gap(4215.,4210.14,4214.52),0.48)
        self.assertEqual(_gap(4215.,4201.3,4208.84),6.16)
        self.assertEqual(_gap(4725.,4694.,4728.),0.)
    def test_frame_filename_strict(self):
        self.assertIsNone(FRAME_NAME.fullmatch('../fake_board.png'))
        self.assertIsNone(FRAME_NAME.fullmatch('notes.txt'))
    def test_traversal_archive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'unsafe.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../board/escape.png',b'png')
            with zipfile.ZipFile(p) as z:
                with self.assertRaisesRegex(ValueError,'untrusted ZIP'):_validate_zip(z)
    def test_duplicate_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dup.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('board/a_t0004215000_board.png',b'one')
                z.writestr('board/b_t0004215000_board.png',b'two')
            with zipfile.ZipFile(p) as z:
                with self.assertRaisesRegex(ValueError,'duplicate frame timestamp'):_validate_zip(z)
    def test_empty_zip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'empty.zip'
            with zipfile.ZipFile(p,'w'):pass
            with zipfile.ZipFile(p) as z:
                with self.assertRaisesRegex(ValueError,'unexpected board'):_validate_zip(z)

@unittest.skipUnless(ORIGINAL.is_file() and BOARD20.is_file() and BOARD22.is_file(),'private original board/media absent on GitHub Actions')
class PrivateSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(ORIGINAL.read_text(encoding='utf-8'))
        cls.report=build_audit(cls.doc,{20:BOARD20,22:BOARD22})
    def test_original_board_zip_hash_is_pinned(self):
        self.assertEqual(self.report['original_board_zip_sha256'],{str(k):v for k,v in SOURCE_BOARD_SHA256.items()})
    def test_six_windows_zero_semantic_trade_certification(self):
        self.assertEqual(self.report['source_window_count'],6)
        self.assertEqual(self.report['unique_source_windows'],5)
        self.assertEqual(self.report['independently_verified_teacher_trade_rules'],0)
        self.assertFalse(self.report['mt5_orders_permitted'])
        self.assertTrue(all(not x['chart_referent_to_spoken_instruction_verified'] for x in self.report['windows']))
    def test_case_02_no_in_window_frame(self):
        w=self.report['windows'][1]
        self.assertEqual(w['in_window_frame_count'],0)
        self.assertEqual(w['temporal_status'],'NO_FRAME_WITHIN_SPEECH_INTERVAL')
        self.assertAlmostEqual(w['nearest_verified_frame_context'][0]['gap_to_speech_window_seconds'],6.16)
    def test_both_doji_cases_share_audio_and_have_no_in_window_frame(self):
        self.assertTrue(self.report['doji_ahead_and_tied_share_same_audio'])
        self.assertEqual(self.report['windows'][2]['in_window_frame_count'],0)
        self.assertEqual(self.report['windows'][3]['in_window_frame_count'],0)
    def test_case_01_frame_4125_chart_within_audio(self):
        w=self.report['windows'][0]
        self.assertTrue(any(x['timestamp_seconds']==4125 and x['inside_speech_interval'] and x['scene_label']=='CHART_VISIBLE' for x in w['nearest_verified_frame_context']))
    def test_case_06_has_both_meeting_and_chart(self):
        w=self.report['windows'][5]
        self.assertEqual(w['temporal_status'],'MIXED_SCENES_WITHIN_INTERVAL')
        self.assertTrue({'MEETING_INTERFACE','CHART_VISIBLE'}.issubset({x['scene_label'] for x in w['nearest_verified_frame_context'] if x['inside_speech_interval']}))
    def test_bad_citation_time_rejected(self):
        d=copy.deepcopy(self.doc);d['private_review_windows'][0]['start_seconds']+=1
        with self.assertRaisesRegex(ValueError,'citation identity'):build_audit(d,{20:BOARD20,22:BOARD22})
    def test_board_source_swap_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):build_audit(self.doc,{20:BOARD22,22:BOARD20})

if __name__=='__main__':unittest.main()