"""Regression tests for offline Artin case identity and causal information boundaries.

These are software checks, NOT validation of the teacher's meaning.
"""
import unittest

from run_engine import run_document


def document(cases):
    return {
        "mode": "ANNOTATED_OFFLINE",
        "plan_id": "offline-regression-only",
        "allowed_rules": ["PULLBACK_STANDARD"],
        "synthetic_only": True,
        "cases": cases,
    }


def case(case_id, at=10, known_at=11):
    return {
        "case_id": case_id,
        "rule_id": "PULLBACK_STANDARD",
        "side": "BUY",
        "at": at,
        "facts": {
            "sentiment_permission": {
                "value": "TWO_SIDED", "known_at": known_at,
                "source": "synthetic-regression",
            }
        },
    }


class CaseIdentityAndCausality(unittest.TestCase):
    def test_duplicate_ids_fail_before_any_case_execution(self):
        with self.assertRaisesRegex(ValueError, "Duplicate case_id"):
            run_document(document([case("same"), case("same")]))

    def test_blank_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonempty case_id"):
            run_document(document([case(" ")]))

    def test_future_information_never_yields_eligible(self):
        result = run_document(document([case("future")]))
        decision = result["decisions"][0]
        self.assertEqual(decision["case_id"], "future")
        self.assertEqual(decision["case_index"], 0)
        self.assertEqual(decision["status"], "REVIEW")
        self.assertIn("FUTURE_INFORMATION:sentiment_permission", decision["reasons"])
        self.assertFalse(decision["order_created"])
        self.assertEqual(result["orders_sent"], 0)
        self.assertFalse(result["broker_connected"])


if __name__ == "__main__":
    unittest.main()
