"""Case identity preflight must reject invalid batches before evaluating trades.

Software-only regression: not evidence of teacher agreement or MT5 performance.
"""
import unittest
from unittest.mock import patch
from entry_engine import RULE_IDS
from run_engine import run_document


class CaseIdentityPreflightTests(unittest.TestCase):
    def test_late_duplicate_rejected_before_any_evaluation(self):
        document = {
            "mode": "ANNOTATED_OFFLINE",
            "plan_id": "identity-preflight",
            "allowed_rules": [RULE_IDS[0]],
            "cases": [
                {"case_id": "lesson-01", "rule_id": RULE_IDS[0],
                 "side": "BUY", "at": 10, "facts": {}},
                {"case_id": "lesson-01", "rule_id": RULE_IDS[0],
                 "side": "BUY", "at": 20, "facts": {}},
            ],
        }
        with patch("run_engine.Engine.evaluate", side_effect=AssertionError("evaluated before preflight")) as evaluate:
            with self.assertRaisesRegex(ValueError, "Duplicate case_id"):
                run_document(document)
            evaluate.assert_not_called()

    def test_implicit_id_collision_rejected_before_evaluation(self):
        document = {
            "mode": "ANNOTATED_OFFLINE",
            "plan_id": "identity-preflight",
            "allowed_rules": [RULE_IDS[0]],
            "cases": [
                {"case_id": "case-0001", "rule_id": RULE_IDS[0],
                 "side": "BUY", "at": 10, "facts": {}},
                {"rule_id": RULE_IDS[0], "side": "BUY", "at": 20, "facts": {}},
            ],
        }
        with patch("run_engine.Engine.evaluate", side_effect=AssertionError("evaluated before preflight")) as evaluate:
            with self.assertRaisesRegex(ValueError, "Duplicate case_id"):
                run_document(document)
            evaluate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
