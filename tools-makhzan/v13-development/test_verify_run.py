import hashlib
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("v13_verify_run", Path(__file__).with_name("v13_verify_run.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReceiptBindingTests(unittest.TestCase):
    def make_record(self, root, corrupt=False):
        keys = ("source", "speech_evidence", "visual_evidence", "semantic_review", "archive")
        record = {}
        for key in keys:
            data = ("source-backed artifact " + key).encode()
            (root / (key + ".bin")).write_bytes(data)
            record[key + "_path"] = key + ".bin"
            record[key + "_sha256"] = hashlib.sha256(data).hexdigest()
        record["next_queue_id"] = "video-q-0021-artin-test"
        receipt = {key: record[key] for key in ("source_sha256", "archive_sha256", "next_queue_id")}
        receipt.update(semantic_review_passed=True, next_handoff_verified=True)
        if corrupt:
            receipt["next_queue_id"] = "video-q-9999-wrong-film"
        data = json.dumps(receipt).encode()
        (root / "receipt.json").write_bytes(data)
        record["receipt_path"] = "receipt.json"
        record["receipt_sha256"] = hashlib.sha256(data).hexdigest()
        start = datetime(2026, 11, 9, tzinfo=timezone.utc)
        stages = ("source_started_at", "download_verified_at", "speech_complete_at",
                  "visual_complete_at", "semantic_review_complete_at", "archive_committed_at",
                  "receipt_committed_at", "next_handoff_committed_at")
        for index, stage in enumerate(stages):
            record[stage] = (start + timedelta(seconds=index * 20)).isoformat()
        record.update(evidence_mode="real-production", semantic_review_passed=True,
                      next_handoff_verified=True, source_integrity_verified=True)
        return record

    def test_consistent_receipt_passes_structural_checks_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertTrue(module.verify_run(self.make_record(root), root)["passed"])

    def test_valid_digest_with_wrong_queue_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = module.verify_run(self.make_record(root, corrupt=True), root)
            self.assertFalse(result["passed"])
            self.assertIn("receipt binding mismatch: next_queue_id", result["errors"])

    def test_tampered_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = self.make_record(root)
            (root / "receipt.json").write_text("{}")
            self.assertFalse(module.verify_run(record, root)["passed"])

if __name__ == "__main__":
    unittest.main()
