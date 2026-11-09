import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("verify_artifacts", Path(__file__).with_name("verify_artifacts.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ArtifactByteTests(unittest.TestCase):
    def test_real_bytes_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = {}
            for key in module.ARTIFACT_KEYS:
                data = ("actual bytes " + key).encode()
                (root / (key + ".bin")).write_bytes(data)
                record[key + "_path"] = key + ".bin"
                record[key + "_sha256"] = hashlib.sha256(data).hexdigest()
            self.assertTrue(module.verify(record, root)["passed"])
            (root / "speech_evidence.bin").write_bytes(b"tampered")
            self.assertFalse(module.verify(record, root)["passed"])
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = {key + "_path": "../outside" for key in module.ARTIFACT_KEYS}
            self.assertFalse(module.verify(record, root)["passed"])
    def test_missing_files_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(module.verify({}, Path(d))["passed"])

if __name__ == "__main__":
    unittest.main()
