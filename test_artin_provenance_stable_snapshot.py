"""Regression tests for in-flight artifact mutation detection (no real film claim)."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import artin_receipt_provenance_gate as gate


class StableSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.receipt = {"artifacts": {}}
        for kind in gate.REQUIRED:
            name = kind + ".bin"
            data = kind.encode()
            (root / name).write_bytes(data)
            self.receipt["artifacts"][kind] = {
                "path": name, "sha256": hashlib.sha256(data).hexdigest()
            }

    def test_stable_files_pass(self):
        self.assertTrue(gate.audit_artifacts(self.receipt, self.tmp.name)["passed"])

    def test_modified_metadata_during_read_fails_closed(self):
        original = gate.fstat_artifact
        calls = [0]

        def changing_second_snapshot(file):
            calls[0] += 1
            snapshot = original(file)
            if calls[0] == 2:
                class Changed:
                    pass
                altered = Changed()
                for attr in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode"):
                    setattr(altered, attr, getattr(snapshot, attr))
                altered.st_mtime_ns += 1
                return altered
            return snapshot

        with patch.object(gate, "fstat_artifact", side_effect=changing_second_snapshot):
            result = gate.audit_artifacts(self.receipt, self.tmp.name)
        self.assertFalse(result["passed"])
        self.assertTrue(any("changed during read" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
