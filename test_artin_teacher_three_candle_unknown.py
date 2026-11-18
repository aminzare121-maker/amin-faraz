"""Regression: three bullish raw bars cannot certify teacher three-candle semantics."""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate


class TestTeacherThreeCandleUnknown(unittest.TestCase):
    def test_three_same_direction_remains_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "bars.csv"
            with source.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(("timestamp", "open", "high", "low", "close"))
                for i in range(3):
                    writer.writerow((900 * (i + 1), 100 + i, 102 + i, 99 + i, 101 + i))
            result = evaluate(str(source), as_of=3600)
            route = next(x for x in result["routes"] if x["route_id"] == "REVERSAL_THREE")
            example = route["first_bar_example"]
            self.assertIn("three_same_direction_sequence", example["unknown_teacher_predicates"])
            self.assertNotIn("three_same_direction_sequence", example["known_market_facts"])
            self.assertEqual(result["teacher_approved_entries"], 0)
            self.assertEqual(result["trades_executed"], 0)


if __name__ == "__main__":
    unittest.main()
