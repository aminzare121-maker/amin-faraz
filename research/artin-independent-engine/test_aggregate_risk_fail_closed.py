"""Regression: a batch cannot silently reuse a caller-declared risk allowance.

This is a structural safety test, not evidence of classroom semantics or MT5 results.
"""
import unittest
from run_engine import run_document


class AggregateRiskFailClosed(unittest.TestCase):
    def test_two_paper_trades_rejected_before_any_decision(self):
        document = {
            "mode": "ANNOTATED_OFFLINE",
            "plan_id": "safety-regression",
            "allowed_rules": [],
            "synthetic_only": True,
            "cases": [
                {"case_id": "a", "paper_trade": {}},
                {"case_id": "b", "paper_trade": {}},
            ],
        }
        with self.assertRaisesRegex(ValueError, "MULTI_TRADE_AGGREGATE_RISK_NOT_RESERVED"):
            run_document(document)

    def test_no_paper_trades_does_not_trigger_guard(self):
        # Empty batch does not consume aggregate budget.
        document = {
            "mode": "ANNOTATED_OFFLINE",
            "plan_id": "safety-regression",
            "allowed_rules": [],
            "synthetic_only": True,
            "cases": [],
        }
        result = run_document(document)
        self.assertEqual(result["paper_trades"], [])


if __name__ == "__main__":
    unittest.main()
