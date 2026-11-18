"""Check BUY/SELL teacher dependencies against the legacy route manifest.

No instructor interpretation or order permission is inferred from this test.
"""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from artin_13_real_m15_gap_audit import REQUIRED, requirements


class RouteDependenciesTest(unittest.TestCase):
    def test_each_side_preserves_original_required_predicates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "closed.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["timestamp", "open", "high", "low", "close"])
                writer.writeheader()
                writer.writerow(dict(timestamp=900, open=4000, high=4003, low=3999, close=4002))
            result = evaluate(str(path), as_of=1800)
        self.assertEqual(len(result["routes"]), 13)
        for route in result["routes"]:
            route_id = route["route_id"]
            self.assertIn(route_id, REQUIRED)
            example = route["first_bar_example"]
            for side in ("BUY", "SELL"):
                expected = set(requirements(route_id, side))
                actual = set(example["unknown_by_side"][side]) | set(example["known_market_facts"])
                self.assertEqual(expected, actual, (route_id, side))
            self.assertEqual(route["states"]["UNRESOLVED_TEACHER_CONTEXT"], 1)
        self.assertEqual(result["teacher_approved_entries"], 0)
        self.assertEqual(result["trades_executed"], 0)


if __name__ == "__main__":
    unittest.main()
