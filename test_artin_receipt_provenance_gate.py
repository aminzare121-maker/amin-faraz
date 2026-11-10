import hashlib
import tempfile
import unittest
from pathlib import Path
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
