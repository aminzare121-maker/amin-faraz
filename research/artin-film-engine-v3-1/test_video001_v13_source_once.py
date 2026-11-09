"""Executable V13 source-only integration test: synthetic local media, no class data."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from artin_chat_temporal_v8 import collect_index, raw_gray_frames
from artin_film_pipeline import file_sha256
from artin_visual_timeline_v6 import validate_visual_index, frame_times
from video001_v13_source_once import prepare


class V13RealExecutableStage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.base=Path(cls.tmp.name)
        cls.src=cls.base/"synthetic_with_audio.mp4"
        subprocess.run([
            "ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=640x360:rate=10",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=16000",
            "-t","91","-c:v","mpeg4","-q:v","6",
            "-c:a","aac","-shortest",str(cls.src)
        ],check=True,timeout=150)
        cls.sha=file_sha256(cls.src)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_entire_source_stage_and_existing_downstream_shards(self):
        folder=self.base/"v13_output"
        m=prepare(self.src,folder,expected_sha=self.sha,
                  audio_workers=1,ocr_workers=1,sample_seconds=30)
        self.assertTrue(m["v13_one_pass_visual_enabled"])
        self.assertFalse(m["v13_legacy_archives_overwritten"])
        self.assertTrue(m["source_integrity_verified"])
        self.assertTrue(m["all_original_audio_parts_assigned_once"])
        self.assertTrue(m["all_original_chat_images_assigned_once"])
        self.assertEqual(m["source_global_audio_chunks"],1)
        self.assertEqual(m["one_second_frames_scanned"],91)
        self.assertEqual(m["original_board_frames"],4)
        old=collect_index(raw_gray_frames(self.src),
            source_sha256=self.sha,duration_seconds=91)
        new=json.loads((folder/"original_second_by_second_chat_index.json").read_text())
        self.assertEqual([x["priority_capture"] for x in old["rows"]],
                         [x["priority_capture"] for x in new["rows"]])
        self.assertEqual([x["change_score"] for x in old["rows"]],
                         [x["change_score"] for x in new["rows"]])
        self.assertEqual(new["source_video_sha256"],self.sha)
        board=json.loads((folder/"full_board"/"visual_timeline_v6.json").read_text())
        manifest=json.loads((folder/"full_audio"/"fast_av_manifest.json").read_text())
        self.assertTrue(validate_visual_index(
            folder/"full_board",manifest,board,verify_files=True))
        self.assertEqual(board["rows"][-1]["time_seconds"],90)
        self.assertEqual(len(frame_times(manifest["parts"],30)),4)
        self.assertEqual(len(list((folder/"ocr_shards"/"worker_00").rglob("*.png"))),
                         m["original_chat_images_selected"])
        self.assertEqual(file_sha256(self.src),self.sha)

    def test_second_run_refuses_to_change_existing_extraction(self):
        folder=self.base/"v13_output"
        before=file_sha256(folder/"original_second_by_second_chat_index.json")
        with self.assertRaises(FileExistsError):
            prepare(self.src,folder,expected_sha=self.sha,
                    audio_workers=1,ocr_workers=1,sample_seconds=30)
        self.assertEqual(file_sha256(folder/"original_second_by_second_chat_index.json"),before)


if __name__=="__main__":unittest.main()
