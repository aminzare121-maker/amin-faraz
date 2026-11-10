"""Regression: hard links must not impersonate independent stage artifacts."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from artin_receipt_provenance_gate import REQUIRED, audit_artifacts


class HardLinkEvidenceTests(unittest.TestCase):
    def test_distinct_paths_same_inode_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = {}
            original = root / "source.bin"
            original.write_bytes(b"source")
            digest = hashlib.sha256(b"source").hexdigest()
            for index, kind in enumerate(REQUIRED):
                path = root / (kind + ".bin")
                if index == 0:
                    original.rename(path)
                    first = path
                else:
                    os.link(first, path)
                artifacts[kind] = {"path": path.name, "sha256": digest}
            result = audit_artifacts({"artifacts": artifacts}, root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("duplicate artifact inode" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
