"""All fixtures are invented media bytes, not actual teacher recordings."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from classroom_media_manifest import inventory,session_candidates

class ClassroomMediaManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def write(self,name,payload=b"synthetic bytes"):
        file=self.root/name
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(payload)
        return file

    def test_explicit_session_from_persian_filename(self):
        f=self.write("جلسه ۲۱.mp4",b"dummy video file")
        r=inventory(self.root)
        self.assertEqual(r["media_files_hashed"],1)
        self.assertEqual(r["media_kind_counts"]["VIDEO"],1)
        self.assertEqual(r["media"][0]["session_candidates"],[21])
        self.assertEqual(r["media"][0]["sha256"],hashlib.sha256(b"dummy video file").hexdigest())
        self.assertFalse(r["original_audio_video_reviewed"])
        self.assertFalse(r["media"][0]["teacher_content_reviewed"])

    def test_lesson_marker_in_parent_folder(self):
        f=self.write("session_22/audio.wav")
        self.assertEqual(session_candidates(f,self.root),[22])
        r=inventory(self.root)
        self.assertEqual(r["sessions"][21]["audio_candidates"],1)

    def test_ambiguous_session_markers_require_human_mapping(self):
        self.write("session_21/lesson_22.mp4")
        r=inventory(self.root)
        self.assertEqual(r["ambiguous_or_unassigned_files"],1)
        self.assertEqual(r["sessions"][20]["video_candidates"],0)
        self.assertEqual(r["sessions"][21]["video_candidates"],0)

    def test_unknown_file_is_not_attributed_to_teacher(self):
        self.write("lecture.mp4")
        r=inventory(self.root)
        self.assertEqual(r["media"][0]["session_candidates"],[])
        self.assertEqual(r["approved_teacher_rules"],0)
        self.assertIn(1,r["sessions_without_unambiguous_media"])

    def test_nonmedia_ignored(self):
        self.write("session21/speech-000000.json")
        self.write("session21/notes.txt")
        r=inventory(self.root)
        self.assertEqual(r["media_files_hashed"],0)

    def test_out_of_scope_session_is_not_assigned(self):
        self.write("session27/video.mp4")
        r=inventory(self.root)
        self.assertEqual(r["ambiguous_or_unassigned_files"],1)
        self.assertEqual(r["media"][0]["session_candidates"],[])

    def test_empty_root_is_explicitly_incomplete(self):
        r=inventory(self.root,26)
        self.assertEqual(r["media_files_hashed"],0)
        self.assertEqual(len(r["sessions_without_unambiguous_media"]),26)

    def test_missing_root_is_error(self):
        with self.assertRaisesRegex(ValueError,"folder not available"):
            inventory(self.root/"missing",26)

    def test_invalid_count_fails(self):
        with self.assertRaisesRegex(ValueError,"Invalid session count"):
            inventory(self.root,0)

if __name__=="__main__":
    unittest.main()
