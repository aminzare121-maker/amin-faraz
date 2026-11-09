"""Regression: a session cannot pass with only one of four required rule kinds."""
import unittest
from artin_semantic_gate import audit

H = "a" * 64

def rule(kind):
    return {
        "kind": kind, "cross_session_checked": True,
        "ambiguity_resolved": True, "status": "VERIFIED",
        "evidence": [
            {"modality": "speech", "source_sha256": H, "start": 1, "end": 2},
            {"modality": "image", "source_sha256": H, "start": 1, "end": 2},
        ],
        "independent_comparison": {
            "teacher_example_id": "example", "reviewer": "reviewer",
            "expected_decision": "HOLD", "observed_decision": "HOLD",
            "independent": True, "review_result": "PASS",
        },
    }

class CompletenessTests(unittest.TestCase):
    def test_one_kind_cannot_complete_session(self):
        row = audit({"sessions": [{"session": 1, "rules": [rule("entry")]}]})["sessions"][0]
        self.assertEqual(row["status"], "UNVERIFIED")
        self.assertEqual(row["verified_rules"], 1)
        self.assertEqual(row["missing_rule_kinds"], ["decision_order", "exception", "exit"])

    def test_all_four_kinds_can_review_one_session_not_all_25(self):
        kinds = ("entry", "exit", "exception", "decision_order")
        report = audit({"sessions": [{"session": 1, "rules": [rule(k) for k in kinds]}]})
        self.assertEqual(report["sessions"][0]["status"], "REVIEWED")
        self.assertEqual(report["sessions"][0]["missing_rule_kinds"], [])
        self.assertFalse(report["complete"])

    def test_invalid_rule_blocks_review_despite_four_valid_kinds(self):
        kinds = ("entry", "exit", "exception", "decision_order")
        report = audit({"sessions": [{"session": 1, "rules": [rule(k) for k in kinds] + [{}]}]})
        self.assertEqual(report["sessions"][0]["status"], "UNVERIFIED")

if __name__ == "__main__":
    unittest.main()
