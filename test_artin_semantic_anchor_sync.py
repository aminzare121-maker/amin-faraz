"""Regression tests for synchronized semantic evidence; no fabricated video claims."""
import unittest
from artin_semantic_gate import audit

HASH_A = "a" * 64
HASH_B = "b" * 64


def rule(speech_hash=HASH_A, image_hash=HASH_A, image_start=2, speech_start=1):
    return {
        "kind": "entry", "cross_session_checked": True,
        "ambiguity_resolved": True, "status": "VERIFIED",
        "evidence": [
            {"modality": "speech", "source_sha256": speech_hash, "start": speech_start, "end": 3},
            {"modality": "image", "source_sha256": image_hash, "start": image_start, "end": 4},
        ],
        "independent_comparison": {
            "teacher_example_id": "example-1", "reviewer": "reviewer-1",
            "expected_decision": "HOLD", "observed_decision": "HOLD",
            "independent": True, "review_result": "PASS"
        }
    }


def evaluate(item):
    return audit({"sessions": [{"session": 1, "rules": [item]}]})


class SemanticEvidenceTests(unittest.TestCase):
    def test_matching_source_and_overlapping_time_is_eligible(self):
        result = evaluate(rule())
        self.assertEqual(result["sessions"][0]["verified_rules"], 1)
        self.assertFalse(result["complete"])  # other 24 sessions still missing

    def test_different_source_hash_is_rejected(self):
        result = evaluate(rule(image_hash=HASH_B))
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)
        self.assertIn("unsupported VERIFIED claim", result["errors"][0])

    def test_nonoverlapping_timestamps_are_rejected(self):
        result = evaluate(rule(image_start=3.1))
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)

    def test_placeholder_hash_is_rejected(self):
        result = evaluate(rule(speech_hash="placeholder"))
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)

    def test_boolean_timestamp_is_rejected(self):
        result = evaluate(rule(speech_start=True))
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)

    def test_nonfinite_timestamp_is_rejected(self):
        result = evaluate(rule(speech_start=float("nan")))
        self.assertEqual(result["sessions"][0]["verified_rules"], 0)


if __name__ == "__main__":
    unittest.main()
