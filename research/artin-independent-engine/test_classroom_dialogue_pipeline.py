"""Synthetic ASR fixtures only; none of this data is from the teacher."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from classroom_dialogue_pipeline import inspect_course, _load_asr


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ClassroomDialoguePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def prepare(self, session, filename, segments, override_hash=None, override_count=None):
        folder = self.root/f"session_{session}"
        folder.mkdir(exist_ok=True)
        payload=json.dumps({"segments":segments},ensure_ascii=False).encode()
        (folder/filename).write_bytes(payload)
        return {"file":filename,
                "sha256":override_hash or sha(payload),
                "segment_count":len(segments) if override_count is None else override_count}

    def test_questions_are_candidates_not_student_or_teacher_claims(self):
        entry=self.prepare(21,"speech-000600.json",[
            {"start":10,"end":12,"text":"چرا این کندل را نمی‌گیریم؟"},
            {"start":12,"end":14,"text":"نه، اینجا باید مکث را بررسی کنیم."},
        ])
        inv={"sessions":[{"session":21,"audio_available":True,"video_available":False,
                          "transcript_files":[entry]}]}
        report,queue=inspect_course(self.root,inv,"relative")
        self.assertEqual(report["hash_verified_asr_files"],1)
        self.assertEqual(len(queue),2)
        self.assertEqual(queue[0]["start_seconds"],610)
        self.assertEqual(queue[0]["speaker"],"UNKNOWN")
        self.assertIsNone(queue[0]["teacher_answer_turn_id"])
        self.assertIn("QUESTION_LANGUAGE_CANDIDATE",queue[0]["machine_tags"])
        self.assertIn("POSSIBLE_CORRECTION_LANGUAGE",queue[1]["machine_tags"])
        self.assertFalse(report["all_original_audio_video_watched"])
        self.assertEqual(report["teacher_rules_verified"],0)

    def test_wrong_hash_is_not_valid_course_content(self):
        entry=self.prepare(2,"speech-000000.json",[
            {"start":1,"end":2,"text":"آزمون مصنوعی"}
        ],override_hash="0"*64)
        report,queue=inspect_course(self.root,{"sessions":[{"session":2,
            "transcript_files":[entry]}]},"relative")
        self.assertEqual(report["hash_verified_asr_files"],0)
        self.assertEqual(report["failures"][0]["reason"],"NOT_FOUND_OR_HASH_MISMATCH")
        self.assertEqual(queue,[])

    def test_mismatched_segment_count_is_rejected(self):
        entry=self.prepare(22,"speech-000000.json",[
            {"start":1,"end":2,"text":"این متن فقط نمونه است"}
        ],override_count=20)
        report,_=inspect_course(self.root,{"sessions":[{"session":22,
            "transcript_files":[entry]}]},"relative")
        self.assertEqual(report["failures"][0]["reason"],"SEGMENT_COUNT_MISMATCH")

    def test_missing_session_fails_full_coverage(self):
        inv={"sessions":[{"session":1,"audio_available":False,"video_available":False,
                          "transcript_files":[]}]}
        report,_=inspect_course(self.root,inv,"relative",allow_partial=True)
        self.assertEqual(report["registered_sessions"],1)
        with self.assertRaisesRegex(ValueError,"Incomplete course input"):
            inspect_course(self.root,inv,"relative",allow_partial=False)

    def test_absolute_timebase_keeps_original_values(self):
        entry=self.prepare(23,"speech-001200.json",[
            {"start":1201,"end":1205,"text":"آیا عدد ثابت داریم؟"}
        ])
        inv={"sessions":[{"session":23,"transcript_files":[entry]}]}
        _,queue=inspect_course(self.root,inv,"absolute")
        self.assertEqual(queue[0]["start_seconds"],1201.0)

    def test_invalid_asr_format_is_not_silently_transcribed(self):
        with self.assertRaisesRegex(ValueError,"ASR JSON"):
            _load_asr(json.dumps({"text":"not-segments"}).encode())

    def test_timebase_uncertainty_fails_closed(self):
        entry=self.prepare(23,"speech-001200.json",[
            {"start":1201,"end":1205,"text":"آیا این در زمان فایل نسبی است؟"}
        ])
        inv={"sessions":[{"session":23,"transcript_files":[entry]}]}
        report,queue=inspect_course(self.root,inv,"relative")
        self.assertEqual(queue,[])
        self.assertEqual(report["failures"][0]["reason"],"TIMEBASE_UNCERTAIN")


if __name__=="__main__":
    unittest.main()
