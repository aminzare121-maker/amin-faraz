"""Regression tests for the full V13 verifier, including Behrooz readback."""
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("v13_verify_run", Path(__file__).with_name("v13_verify_run.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def digest(data):
    return hashlib.sha256(data).hexdigest()

class ReceiptBindingTests(unittest.TestCase):
    def make_record(self, root, corrupt_queue=False, corrupt_archive=False):
        record = {"queue_id": "video-q-0021-artin-test", "next_queue_id": "video-q-0022-artin-test"}
        for key in ("source", "speech_evidence", "visual_evidence", "semantic_review", "archive"):
            data = ("source-backed artifact " + key).encode()
            (root / (key + ".bin")).write_bytes(data)
            record[key + "_path"] = key + ".bin"
            record[key + "_sha256"] = digest(data)
        receipt = {key: record[key] for key in ("source_sha256", "archive_sha256", "next_queue_id")}
        receipt.update(semantic_review_passed=True, next_handoff_verified=True)
        if corrupt_queue:
            receipt["next_queue_id"] = "video-q-9999-wrong-film"
        data = json.dumps(receipt).encode()
        (root / "receipt.json").write_bytes(data)
        record["receipt_path"] = "receipt.json"
        record["receipt_sha256"] = digest(data)
        review = (root / "semantic_review.bin").read_bytes()
        archive = (root / "archive.bin").read_bytes()
        index = {"videos": [{"queue_id": record["queue_id"], "video": 21,
                              "archive": "RAW/video21.bin",
                              "sha256": digest(archive)}]}
        with zipfile.ZipFile(root / "behrooz.zip", "w") as z:
            z.writestr("BEHROOZ_INDEX.json", json.dumps(index))
            z.writestr("RAW/video21.bin", archive + (b"tamper" if corrupt_archive else b""))
            z.writestr("DERIVED_NOT_RAW/VIDEO_21/REVIEW_FA.md", review)
        record.update(behrooz_readback_path="behrooz.zip",
                      behrooz_library_file_id="test-library-id", behrooz_version=1)
        start = datetime(2026, 11, 9, tzinfo=timezone.utc)
        stages = ("source_started_at", "download_verified_at", "speech_complete_at",
                  "visual_complete_at", "semantic_review_complete_at", "archive_committed_at",
                  "receipt_committed_at", "next_handoff_committed_at",
                  "behrooz_readback_verified_at")
        for index, stage in enumerate(stages):
            record[stage] = (start + timedelta(seconds=index * 20)).isoformat()
        record.update(evidence_mode="real-production", semantic_review_passed=True,
                      next_handoff_verified=True, source_integrity_verified=True)
        return record

    def test_consistent_fixture_passes_structural_checks_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = module.verify_run(self.make_record(root), root)
            self.assertTrue(result["passed"], result["errors"])

    def test_wrong_queue_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = module.verify_run(self.make_record(root, corrupt_queue=True), root)
            self.assertFalse(result["passed"])
            self.assertIn("receipt binding mismatch: next_queue_id", result["errors"])

    def test_tampered_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = self.make_record(root)
            (root / "receipt.json").write_text("{}")
            self.assertFalse(module.verify_run(record, root)["passed"])

    def test_behrooz_archive_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            result = module.verify_run(self.make_record(root, corrupt_archive=True), root)
            self.assertFalse(result["passed"])
            self.assertTrue(any("Behrooz readback verification failed" in e for e in result["errors"]))

    def test_missing_behrooz_readback_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            record = self.make_record(root)
            (root / "behrooz.zip").unlink()
            self.assertFalse(module.verify_run(record, root)["passed"])

if __name__ == "__main__":
    unittest.main()
