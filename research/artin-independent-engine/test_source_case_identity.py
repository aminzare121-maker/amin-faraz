"""Regression: real-source decision batches cannot silently invent example IDs.

Software-only tests; not teacher replay or MT5 validation.
"""
import unittest
from run_engine import run_document


def doc(synthetic, cases):
    return {
        "mode": "ANNOTATED_OFFLINE",
        "plan_id": "case-identity-regression",
        "allowed_rules": ["PULLBACK_STANDARD"],
        "synthetic_only": synthetic,
        "cases": cases,
    }


def case(case_id=None):
    c = {
        "rule_id": "PULLBACK_STANDARD",
        "side": "BUY",
        "at": 10,
        "facts": {},
    }
    if case_id is not None:
        c["case_id"] = case_id
    return c


class SourceCaseIdentityTest(unittest.TestCase):
    def test_non_synthetic_missing_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires explicit case_id"):
            run_document(doc(False, [case()]))

    def test_non_synthetic_rejects_missing_id_before_first_decision(self):
        with self.assertRaisesRegex(ValueError, "requires explicit case_id"):
            run_document(doc(False, [case("original-1"), case()]))

    def test_non_synthetic_preserves_explicit_id(self):
        result = run_document(doc(False, [case("session21-example-1")]))
        self.assertEqual(result["decisions"][0]["case_id"], "session21-example-1")
        self.assertFalse(result["decisions"][0]["order_created"])
        self.assertEqual(result["orders_sent"], 0)

    def test_synthetic_fixture_keeps_legacy_generated_id(self):
        result = run_document(doc(True, [case()]))
        self.assertEqual(result["decisions"][0]["case_id"], "case-0000")
        self.assertTrue(result["synthetic_only"])


if __name__ == "__main__":
    unittest.main()
