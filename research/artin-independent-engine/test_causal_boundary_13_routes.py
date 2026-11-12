"""Regression tests for the existing Artin engine's no-lookahead boundary.

Software tests only; these do not establish teacher agreement or profitability.
"""
import unittest
from entry_engine import Engine, Fact, Observation, RULE_IDS
from run_engine import run_document


class EngineCausalBoundaryTests(unittest.TestCase):
    def test_future_sentiment_cannot_authorize_any_of_13_routes(self):
        engine = Engine("causal-boundary-test", tuple(RULE_IDS))
        for rule in RULE_IDS:
            with self.subTest(rule=rule):
                observation = Observation(
                    "BUY", 100,
                    {"sentiment_permission": Fact("TWO_SIDED", 101, "test-future-observation")},
                )
                decision = engine.evaluate(rule, observation)
                self.assertEqual(decision.status, "REVIEW")
                self.assertIn("FUTURE_INFORMATION:sentiment_permission", decision.reasons)
                self.assertFalse(decision.order_created)

    def test_offline_document_does_not_connect_broker_or_send_orders(self):
        document = {
            "mode": "ANNOTATED_OFFLINE",
            "plan_id": "no-order-test",
            "allowed_rules": [RULE_IDS[0]],
            "synthetic_only": True,
            "cases": [{
                "rule_id": RULE_IDS[0], "side": "BUY", "at": 100,
                "facts": {
                    "sentiment_permission": {
                        "value": "TWO_SIDED", "known_at": 101, "source": "test-future-observation"
                    }
                },
            }],
        }
        result = run_document(document)
        self.assertEqual(result["decisions"][0]["status"], "REVIEW")
        self.assertEqual(result["orders_sent"], 0)
        self.assertIs(result["broker_connected"], False)
        self.assertIs(result["profitability_tested"], False)
        self.assertIs(result["synthetic_only"], True)


if __name__ == "__main__":
    unittest.main()
