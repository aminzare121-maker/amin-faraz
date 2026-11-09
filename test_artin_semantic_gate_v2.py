import unittest
from artin_semantic_gate_v2 import audit

SHA = "a" * 64

def fixture():
    return {"source_registry": {"1": SHA}, "sessions": [{"session": 1, "rules": [{
        "kind": "entry", "cross_session_checked": True, "ambiguity_resolved": True,
        "evidence": [
            {"modality": "speech", "source_sha256": SHA, "start": 1, "end": 3, "evidence_id": "asr"},
            {"modality": "image", "source_sha256": SHA, "start": 2, "end": 2.5, "evidence_id": "frame"}],
        "independent_comparison": {"teacher_example_id": "example", "reviewer": "test-reviewer",
            "review_evidence_id": "review-1", "expected_decision": "ENTER",
            "observed_decision": "ENTER", "independent": True, "review_result": "PASS"}
    }]}]}

class Tests(unittest.TestCase):
    def test_empty(self):
        self.assertFalse(audit({"sessions": []})["complete"])
    def test_valid_structure_not_semantic(self):
        self.assertEqual(audit(fixture())["sessions"][0]["status"], "STRUCTURALLY_REVIEWED")
        self.assertFalse(audit(fixture())["semantic_fidelity_certified"])
    def test_timestamp_disagreement(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["evidence"][1].update({"start": 4, "end": 5})
        self.assertIn("av_timestamps_do_not_overlap", audit(d)["errors"][0])
    def test_source_mismatch(self):
        d = fixture()
        d["sessions"][0]["rules"][0]["evidence"][1]["source_sha256"] = "b" * 64
        self.assertIn("invalid_or_unmatched_source_anchor", audit(d)["errors"][0])
    def test_review_proof_missing(self):
        d = fixture()
        del d["sessions"][0]["rules"][0]["independent_comparison"]["review_evidence_id"]
        self.assertIn("comparison_not_verified", audit(d)["errors"][0])
    def test_empty_rules_fail(self):
        d = fixture()
        d["sessions"][0]["rules"] = []
        self.assertEqual(audit(d)["sessions"][0]["status"], "UNVERIFIED")

if __name__ == "__main__":
    unittest.main()
