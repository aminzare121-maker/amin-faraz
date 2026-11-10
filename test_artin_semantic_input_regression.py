"""Regression tests for fail-closed semantic evidence validation."""
import unittest
from artin_semantic_gate import audit

SHA = "a" * 64

def rule(kind, reviewer="human-reviewer", example="lesson-01-example"):
    return {
        "kind": kind, "cross_session_checked": True,
        "ambiguity_resolved": True,
        "evidence": [
            {"source_sha256": SHA, "start": 1, "end": 2, "modality": "speech"},
            {"source_sha256": SHA, "start": 1.5, "end": 1.5, "modality": "image"},
        ],
        "independent_comparison": {
            "teacher_example_id": example, "reviewer": reviewer,
            "expected_decision": "HOLD", "observed_decision": "HOLD",
            "independent": True, "review_result": "PASS",
        },
    }

class SemanticInputRegression(unittest.TestCase):
    def test_non_object_document_is_rejected(self):
        for value in (None, [], 42, "text"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit(value)

    def test_blank_reviewer_cannot_verify(self):
        outcome = audit({"sessions": [{"session": 1, "rules": [
            rule(k, reviewer="  ") for k in
            ("entry", "exit", "exception", "decision_order")
        ]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 0)
        self.assertEqual(outcome["sessions"][0]["status"], "UNVERIFIED")
        self.assertFalse(outcome["complete"])

    def test_blank_teacher_example_cannot_verify(self):
        outcome = audit({"sessions": [{"session": 1, "rules": [
            rule(k, example="\t") for k in
            ("entry", "exit", "exception", "decision_order")
        ]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 0)

    def test_non_string_reviewer_cannot_verify(self):
        outcome = audit({"sessions": [{"session": 1, "rules": [
            rule(k, reviewer=123) for k in
            ("entry", "exit", "exception", "decision_order")
        ]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 0)

if __name__ == "__main__":
    unittest.main()
