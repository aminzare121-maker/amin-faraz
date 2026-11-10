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
        # An isolated entry rule cannot certify the session. All four kinds
        # (entry, exit, exception, decision_order) are mandatory.
        self.assertEqual(result["sessions"][0]["status"], "UNVERIFIED")
        self.assertEqual(set(result["sessions"][0]["missing_rule_kinds"]),
                         {"exit", "exception", "decision_order"})
        self.assertEqual(result["sessions"][0]["verified_rules"], 1)
        self.assertEqual(result["sessions"][1]["status"], "MISSING")

    def test_four_kinds_structurally_reviewed_but_25_sessions_still_incomplete(self):
        # Fixture is entirely synthetic; it tests only the gate's structure.
        anchors = [
            {"modality": "speech", "source_sha256": "a" * 64, "start": 1, "end": 2},
            {"modality": "image", "source_sha256": "a" * 64, "start": 1, "end": 2},
        ]
        compare = {
            "teacher_example_id": "synthetic-case",
            "reviewer": "synthetic-test-reviewer",
            "expected_decision": "NO_TRADE",
            "observed_decision": "NO_TRADE",
            "independent": True,
            "review_result": "PASS",
        }
        kinds = ("entry", "exit", "exception", "decision_order")
        rules = [
            {"kind": kind, "evidence": anchors, "independent_comparison": compare,
             "cross_session_checked": True, "ambiguity_resolved": True}
            for kind in kinds
        ]
        report = audit({"sessions": [{"session": 1, "rules": rules}]})
        self.assertEqual(report["sessions"][0]["status"], "REVIEWED")
        self.assertEqual(report["sessions"][0]["missing_rule_kinds"], [])
        self.assertFalse(report["complete"])

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


    def test_excessive_anchor_count_fails_closed(self):
        # Synthetic stress fixture: must not enter an unbounded O(n^2) join.
        from artin_semantic_gate import MAX_ANCHORS_PER_RULE
        anchor = {"modality": "speech", "source_sha256": "a" * 64,
                  "start": 1, "end": 2}
        frame = {"modality": "image", "source_sha256": "a" * 64,
                 "start": 1, "end": 2}
        evidence = [anchor] * MAX_ANCHORS_PER_RULE + [frame]
        rule = {
            "kind": "entry", "status": "VERIFIED", "evidence": evidence,
            "independent_comparison": {
                "teacher_example_id": "synthetic", "reviewer": "test",
                "expected_decision": "ENTER", "observed_decision": "ENTER",
                "independent": True, "review_result": "PASS"},
            "cross_session_checked": True, "ambiguity_resolved": True,
        }
        report = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 0)
        self.assertTrue(any("unsupported VERIFIED" in e for e in report["errors"]))

if __name__ == "__main__":
    unittest.main()
