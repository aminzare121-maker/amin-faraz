"""Regression: empty files cannot establish evidence of completed Artin stages."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from artin_receipt_provenance_gate import REQUIRED, audit_artifacts


class EmptyArtifactTests(unittest.TestCase):
    def test_each_empty_stage_fails_closed(self):
        for empty_kind in REQUIRED:
            with self.subTest(stage=empty_kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                receipt = {"artifacts": {}}
                for kind in REQUIRED:
                    data = b"" if kind == empty_kind else ("evidence-" + kind).encode()
                    (root / kind).write_bytes(data)
                    receipt["artifacts"][kind] = {
                        "path": kind,
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                result = audit_artifacts(receipt, root)
                self.assertFalse(result["passed"], result)
                self.assertIn("empty artifact: " + empty_kind, result["errors"])


if __name__ == "__main__":
    unittest.main()
