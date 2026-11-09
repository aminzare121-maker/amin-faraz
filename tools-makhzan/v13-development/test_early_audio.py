import json
from pathlib import Path
import tempfile
import unittest

from extract_local import read, speech_input


class EarlyAudioTests(unittest.TestCase):
    def test_audio_starts_from_same_bytes_before_visual_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "media/private_original_user_movie.mp4"
            audio = root / "media/prepared/full_audio"
            audio.mkdir(parents=True)
            source.write_bytes(b"fixture")
            (audio / "part.wav").write_bytes(b"pcm")
            manifest = {"parts": [{"audio": "part.wav"}], "video_path_private": str(source)}
            early = speech_input(root, audio, manifest)
            self.assertTrue((audio / "part.wav").samefile(early / "part.wav"))
            result = read(early / "fast_av_manifest.json")
            self.assertNotIn("video_path_private", result)
            self.assertEqual(result["verified_original_movie_bytes"], 7)

    def test_finished_preparation_must_match_audio_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / "media/prepared/full_audio"
            audio.mkdir(parents=True)
            (audio.parent / "safe_source_prep_summary.json").write_text(
                json.dumps({"source_video_sha256": "other", "original_movie_bytes": 7}))
            with self.assertRaisesRegex(ValueError, "source changed"):
                speech_input(root, audio, {"video_sha256": "expected", "parts": []})
