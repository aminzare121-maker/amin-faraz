"""Regression: nested intervals must not hide a valid speech/image overlap."""
import unittest
from artin_semantic_gate import audit

SHA = "a" * 64

def anchor(modality, start, end):
    return {"source_sha256": SHA, "modality": modality, "start": start, "end": end}

def rule(evidence):
    return {
        "kind": "entry",
        "evidence": evidence,
        "cross_session_checked": True,
        "ambiguity_resolved": True,
        "independent_comparison": {
            "teacher_example_id": "example-1",
            "reviewer": "reviewer-1",
            "expected_decision": "ENTER",
            "observed_decision": "ENTER",
            "independent": True,
            "review_result": "PASS",
        },
    }

class NestedOverlapRegression(unittest.TestCase):
    def test_nested_speech_interval_is_not_skipped(self):
        # Sorting by start and advancing the shorter END misses [2, 3].
        evidence = [anchor("speech", 0, 100),
                    anchor("speech", 2, 3),
                    anchor("image", 2.5, 2.6)]
        report = audit({"sessions": [{"session": 1, "rules": [rule(evidence)]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 1)

    def test_nested_image_interval_is_not_skipped(self):
        evidence = [anchor("image", 0, 100),
                    anchor("image", 2, 3),
                    anchor("speech", 2.5, 2.6)]
        report = audit({"sessions": [{"session": 1, "rules": [rule(evidence)]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 1)

    def test_disjoint_intervals_still_rejected(self):
        evidence = [anchor("speech", 0, 1), anchor("image", 2, 3)]
        report = audit({"sessions": [{"session": 1, "rules": [rule(evidence)]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 0)

if __name__ == "__main__":
    unittest.main()
