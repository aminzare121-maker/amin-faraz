import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("v13_acceptance_gate.py"))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

def fixture(seconds=179):
    start = datetime(2026, 11, 9, tzinfo=timezone.utc)
    d = {key: (start + timedelta(seconds=seconds*i/(len(gate.REQUIRED)-1))).isoformat()
         for i, key in enumerate(gate.REQUIRED)}
    d.update({key: (format(i+1, "064x") if key.endswith("_sha256") else "video-q-0019-artin-test") for i, key in enumerate(gate.EVIDENCE)})
    d["evidence_mode"] = "real-production"
    d.update(semantic_review_passed=True, next_handoff_verified=True, source_integrity_verified=True)
    return d

class AcceptanceGateTests(unittest.TestCase):
    def test_synthetic_under180_is_accepted_by_gate_only(self):
        self.assertTrue(gate.check(fixture())["passed"])
    def test_reused_digest_across_artifacts_fails(self):
        d=fixture(); d["receipt_sha256"]=d["source_sha256"]
        result=gate.check(d)
        self.assertFalse(result["passed"])
        self.assertIn("duplicate SHA-256 across distinct evidence artifacts", result["errors"])
    def test_exactly_180_misses_strict_target(self):
        self.assertFalse(gate.check(fixture(180))["passed"])
        self.assertFalse(gate.check(fixture(180.001))["passed"])
    def test_receipt_without_semantic_review_fails(self):
        d=fixture();d["semantic_review_passed"]=False
        self.assertFalse(gate.check(d)["passed"])
    def test_missing_handoff_fails(self):
        d=fixture();d.pop("next_handoff_committed_at")
        self.assertFalse(gate.check(d)["passed"])
    def test_synthetic_evidence_rejected(self):
        d=fixture();d["evidence_mode"]="synthetic"
        self.assertFalse(gate.check(d)["passed"])
    def test_invalid_digest_rejected(self):
        d=fixture();d["source_sha256"]="not-a-hash"
        self.assertFalse(gate.check(d)["passed"])
    def test_missing_hash_fails(self):
        d=fixture();d.pop("source_sha256")
        self.assertFalse(gate.check(d)["passed"])
    def test_out_of_order_fails(self):
        d=fixture();d["speech_complete_at"]=d["archive_committed_at"]
        self.assertFalse(gate.check(d)["passed"])

if __name__=="__main__":
    unittest.main()
