"""Deterministic differential tests for Artin interval matching.

Synthetic data only. Passing does not certify teacher semantics or 180-second
end-to-end performance. The quadratic oracle is test-only and bounded.
"""
import random
import unittest
from artin_semantic_gate import audit


def reference_overlap(speech, images):
    return any(max(a[0], b[0]) <= min(a[1], b[1])
               for a in speech for b in images)


def make_rule(speech, images):
    source = "a" * 64
    evidence = [
        {"modality": modality, "source_sha256": source,
         "start": start, "end": end}
        for modality, intervals in (("speech", speech), ("image", images))
        for start, end in intervals
    ]
    return {
        "kind": "entry", "evidence": evidence,
        "independent_comparison": {
            "teacher_example_id": "synthetic-oracle",
            "reviewer": "synthetic-oracle",
            "expected_decision": "HOLD", "observed_decision": "HOLD",
            "independent": True, "review_result": "PASS",
        },
        "cross_session_checked": True,
        "ambiguity_resolved": True,
    }


class IntervalDifferentialTests(unittest.TestCase):
    def test_sweep_agrees_with_bruteforce_on_seeded_intervals(self):
        rng = random.Random(130180)
        for case in range(250):
            def intervals():
                out = []
                for _ in range(rng.randint(1, 18)):
                    start = rng.randint(0, 100)
                    end = start + rng.randint(0, 100)
                    out.append((start, end))
                rng.shuffle(out)
                return out

            speech, images = intervals(), intervals()
            expected = reference_overlap(speech, images)
            report = audit({"sessions": [
                {"session": 1, "rules": [make_rule(speech, images)]}
            ]})
            actual = report["sessions"][0]["verified_rules"] == 1
            self.assertEqual(actual, expected,
                             "case %s speech=%r images=%r" %
                             (case, speech, images))
            self.assertFalse(report["complete"])

    def test_nested_long_speech_interval_is_not_lost(self):
        # Regression: end-sorted two-pointer logic dropped a long enclosure.
        speech = [(19, 97), (29, 36), (73, 80), (12, 42)]
        images = [(60, 68)]
        self.assertTrue(reference_overlap(speech, images))
        report = audit({"sessions": [
            {"session": 1, "rules": [make_rule(speech, images)]}
        ]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 1)
        self.assertFalse(report["complete"])

    def test_nested_enclosure_with_unrelated_source_does_not_mask_match(self):
        # Real CI failure 42770151232: nested intervals must retain
        # a long enclosing speech anchor despite intervening short anchors.
        rule = make_rule([(19, 97), (29, 36), (73, 80), (12, 42)],
                         [(60, 68)])
        rule["evidence"].insert(0, {
            "modality": "image", "source_sha256": "b" * 64,
            "start": 0, "end": 200,
        })
        report = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 1)

        # Removing the only same-source image must fail closed even when
        # the unrelated image completely encloses the speech timestamps.
        rule["evidence"] = [
            anchor for anchor in rule["evidence"]
            if not (anchor["modality"] == "image"
                    and anchor["source_sha256"] == "a" * 64)
        ]
        report = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 0)

    def test_disjoint_intervals_remain_unmatched(self):
        report = audit({"sessions": [
            {"session": 1, "rules": [make_rule([(10, 20), (80, 90)],
                                               [(30, 60)])]}
        ]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 0)

    def test_cross_source_cannot_substitute_for_same_source_overlap(self):
        rule = make_rule([(1, 10)], [(1, 10)])
        rule["evidence"][1]["source_sha256"] = "b" * 64
        report = audit({"sessions": [{"session": 1, "rules": [rule]}]})
        self.assertEqual(report["sessions"][0]["verified_rules"], 0)


if __name__ == "__main__":
    unittest.main()
