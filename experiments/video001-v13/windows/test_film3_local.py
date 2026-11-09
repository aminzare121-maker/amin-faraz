"""Offline fail-closed checks for the Windows V13 film-3 runner.

Run from the windows directory:
    python -m unittest discover -s . -p 'test_film3_local.py'
Does NOT download source, install models, submit GitHub jobs, or trade.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import film3_local as f


class WindowsFilm3FailClosedTests(unittest.TestCase):
    def test_manifest_is_exact_third_film(self):
        self.assertEqual(f.ID, "video-q-0003-artin-clip-01")
        self.assertEqual(f.MOVIE_PARTS, 18)
        self.assertEqual(len(f.MOVIE_SHA), 64)

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                f.source_valid(Path(temp) / "not-present.mp4")

    def test_wrong_video_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fake=Path(temp) / "other.mp4"
            fake.write_bytes(b"not the user's movie")
            with self.assertRaises(ValueError):
                f.source_valid(fake)

    def test_wrong_hash_rejected_even_when_size_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            fake=Path(temp) / "other.mp4"
            fake.write_bytes(b"fake file")
            with patch.object(f,"MOVIE_BYTES",len(b"fake file")):
                with self.assertRaises(ValueError):
                    f.source_valid(fake)

    def test_partial_prepare_refuses_silent_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            partial=root / "prepared"
            partial.mkdir()
            (partial/"private_marker").write_text("preserve",encoding="utf-8")
            with self.assertRaises(RuntimeError):
                f.prepare(root)
            self.assertEqual((partial/"private_marker").read_text(),"preserve")

    def test_atomic_json_persistence(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"safe_result.json"
            obj={"schema":"sample","source_video_sha256":f.MOVIE_SHA}
            f.write_json(target,obj)
            self.assertEqual(f.read_json(target),obj)
            self.assertFalse(target.with_suffix(".json.pending").exists())

    def test_no_trading_calls_present_in_runner(self):
        text=(Path(__file__).parent/"film3_local.py").read_text(encoding="utf-8")
        self.assertNotIn("order_send(",text)
        self.assertNotIn("MetaTrader5.initialize(",text)


if __name__=="__main__":
    unittest.main()
