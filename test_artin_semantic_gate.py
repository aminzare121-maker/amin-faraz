import unittest
from artin_semantic_gate import audit


class SemanticGateTests(unittest.TestCase):
    def test_empty_sessions_fail_closed(self):
        result = audit({"sessions": []})
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["sessions"]), 25)
        self.assertEqual(result["sessions"][0]["status"], "MISSING")

    def test_unsupported_verified_claim_detected(self):
        result = audit({"sessions": [{
            "session": 1,
            "rules": [{"kind": "entry", "status": "VERIFIED"}]
        }]})
        self.assertFalse(result["complete"])
        self.assertIn("unsupported VERIFIED", result["errors"][0])

    def test_one_valid_review_still_does_not_complete_25(self):
        anchors = [
            {"modality": "speech", "source_sha256": "a" * 64, "start": 1, "end": 2},
            {"modality": "image", "source_sha256": "a" * 64, "start": 1, "end": 2},
        ]
        review = {
            "teacher_example_id": "lesson1-example1",
            "reviewer": "independent-reviewer",
            "expected_decision": "ENTER",
            "observed_decision": "ENTER",
            "independent": True,
            "review_result": "PASS",
        }
        rule = {
            "kind": "entry", "evidence": anchors,
            "independent_comparison": review,
            "cross_session_checked": True,
            "ambiguity_resolved": True,
        }
        result = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertFalse(result["complete"])
        self.assertEqual(result["sessions"][0]["status"], "REVIEWED")
        self.assertEqual(result["sessions"][1]["status"], "MISSING")

    def test_mismatched_audio_image_source_not_reviewed(self):
        speech = {"modality": "speech", "source_sha256": "a" * 64, "start": 1, "end": 2}
        image = {"modality": "image", "source_sha256": "b" * 64, "start": 1, "end": 2}
        rule = {
            "kind": "entry",
            "evidence": [speech, image],
            "independent_comparison": {
                "teacher_example_id": "synthetic-only",
                "reviewer": "test-reviewer",
                "expected_decision": "ENTER",
                "observed_decision": "ENTER",
                "independent": True,
                "review_result": "PASS",
            },
            "cross_session_checked": True,
            "ambiguity_resolved": True,
        }
        result = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(result["sessions"][0]["status"], "UNVERIFIED")
        self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()
