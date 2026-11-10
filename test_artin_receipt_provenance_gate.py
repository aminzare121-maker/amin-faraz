import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from artin_receipt_provenance_gate import REQUIRED, audit_artifacts, audit_file_backed_cycle
from test_artin_real_cycle_receipt_gate import CycleReceiptTests

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.receipt = CycleReceiptTests().receipt()
        self.receipt["artifacts"] = {}
        for kind in REQUIRED:
            data = ("original-" + kind).encode()
            (self.root / kind).write_bytes(data)
            self.receipt["artifacts"][kind] = {"path": kind, "sha256": hashlib.sha256(data).hexdigest()}

    def test_file_backed_receipt(self):
        self.assertTrue(audit_file_backed_cycle(self.receipt, self.root)["passed"])

    def test_duplicate_evidence_file_fails(self):
        # Different stages must not be backed by the very same bytes/file.
        self.receipt["artifacts"]["visual"] = dict(self.receipt["artifacts"]["speech"])
        result = audit_artifacts(self.receipt, self.root)
        self.assertFalse(result["passed"])
        self.assertIn("duplicate artifact file: visual", result["errors"])

    def test_symlink_alias_of_same_file_fails(self):
        alias = self.root / "speech-alias"
        try:
            alias.symlink_to(self.root / "speech")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.receipt["artifacts"]["visual"] = {
            "path": "speech-alias",
            "sha256": self.receipt["artifacts"]["speech"]["sha256"],
        }
        result = audit_artifacts(self.receipt, self.root)
        self.assertFalse(result["passed"])
        self.assertIn("duplicate artifact file: visual", result["errors"])

    def test_descriptor_metadata_is_read_before_and_after_hash(self):
        from artin_receipt_provenance_gate import fstat_artifact
        calls = []
        def guarded_fstat(file):
            calls.append(file.name)
            return fstat_artifact(file)
        with patch("artin_receipt_provenance_gate.fstat_artifact", side_effect=guarded_fstat):
            result = audit_artifacts(self.receipt, self.root)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(len(calls), 2 * len(REQUIRED))

    def test_directory_cannot_impersonate_evidence(self):
        (self.root / "speech").unlink()
        (self.root / "speech").mkdir()
        result = audit_artifacts(self.receipt, self.root)
        self.assertFalse(result["passed"])
        self.assertTrue(any(message in result["errors"] for message in ("missing or unsafe file: speech", "missing or unreadable file: speech")), result["errors"])

    def test_stream_size_limit_fails_closed(self):
        # The byte limit must also apply to bytes actually read, not just
        # metadata collected before streaming.
        with patch("artin_receipt_provenance_gate.MAX_BYTES", 3):
            result = audit_artifacts(self.receipt, self.root)
        self.assertFalse(result["passed"])
        self.assertTrue(any("artifact exceeds size limit" in e for e in result["errors"]))

    def test_hash_uses_opened_descriptor_not_path_stat(self):
        # Resolution can stat directories, but artifact integrity must rely
        # on fstat() of its opened descriptor, not Path.stat() on artifacts.
        original_stat = Path.stat
        def allow_resolution_only(path, *args, **kwargs):
            if path.name in REQUIRED:
                raise AssertionError("artifact path stat called")
            return original_stat(path, *args, **kwargs)
        with patch.object(Path, "stat", allow_resolution_only):
            result = audit_artifacts(self.receipt, self.root)
        self.assertTrue(result["passed"], result["errors"])

    def test_tampering_fails(self):
        (self.root / "speech").write_bytes(b"changed")
        self.assertFalse(audit_artifacts(self.receipt, self.root)["passed"])

    def test_missing_artifact_fails(self):
        (self.root / "visual").unlink()
        self.assertFalse(audit_artifacts(self.receipt, self.root)["passed"])

    def test_path_traversal_fails(self):
        self.receipt["artifacts"]["speech"]["path"] = "../outside"
        self.assertFalse(audit_artifacts(self.receipt, self.root)["passed"])

    def test_self_reported_flags_are_not_enough(self):
        del self.receipt["artifacts"]
        self.assertFalse(audit_file_backed_cycle(self.receipt, self.root)["passed"])

    def test_over_180_fails_even_with_files(self):
        self.receipt["timestamps"]["next_handoff_complete"] = "2026-11-10T00:03:00+00:00"
        self.assertFalse(audit_file_backed_cycle(self.receipt, self.root)["passed"])

if __name__ == "__main__":
    unittest.main()
