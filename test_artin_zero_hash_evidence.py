"""Regression: placeholder source hashes cannot establish teacher evidence."""
import unittest
from artin_semantic_gate import audit

GOOD = "a" * 64
ZERO = "0" * 64


def make_rule(source):
    return {
        "kind": "entry",
        "cross_session_checked": True,
        "ambiguity_resolved": True,
        "status": "VERIFIED",
        "evidence": [
            {"source_sha256": source, "modality": "speech", "start": 2, "end": 4},
            {"source_sha256": source, "modality": "image", "start": 3, "end": 3},
        ],
        "independent_comparison": {
            "teacher_example_id": "example-1",
            "reviewer": "reviewer-1",
            "expected_decision": "ENTER",
            "observed_decision": "ENTER",
            "independent": True,
            "review_result": "PASS",
        },
    }


class ZeroHashEvidenceTests(unittest.TestCase):
    def test_placeholder_hash_does_not_verify_rule(self):
        outcome = audit({"sessions": [{"session": 1, "rules": [make_rule(ZERO)]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 0)
        self.assertIn("unsupported VERIFIED claim", outcome["errors"][0])

    def test_nonzero_hash_still_accepts_overlapping_anchors(self):
        outcome = audit({"sessions": [{"session": 1, "rules": [make_rule(GOOD)]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 1)

    def test_different_sources_never_match(self):
        rule = make_rule(GOOD)
        rule["evidence"][1]["source_sha256"] = "b" * 64
        outcome = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(outcome["sessions"][0]["verified_rules"], 0)


if __name__ == "__main__":
    unittest.main()
