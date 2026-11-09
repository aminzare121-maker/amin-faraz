"""Regression: a readback before queue handoff cannot complete the V13 cycle."""
import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("test_verify_run", here / "test_verify_run.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)

class ReadbackOrderingTests(unittest.TestCase):
    def test_readback_before_handoff_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            record = fixtures.ReceiptBindingTests().make_record(root)
            handoff = datetime.fromisoformat(record["next_handoff_committed_at"])
            record["behrooz_readback_verified_at"] = (handoff - timedelta(seconds=1)).isoformat()
            result = fixtures.module.verify_run(record, root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("timestamps out of order" in error for error in result["errors"]), result)

    def test_readback_after_handoff_fixture_passes_structurally(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = fixtures.module.verify_run(fixtures.ReceiptBindingTests().make_record(root), root)
            self.assertTrue(result["passed"], result["errors"])

if __name__ == "__main__":
    unittest.main()
