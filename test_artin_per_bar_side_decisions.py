"""Fail-closed side decision regression for the real per-bar Artin bridge."""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from artin_13_real_m15_gap_audit import REQUIRED


class TestSideDecisions(unittest.TestCase):
    def test_both_sides_remain_blocked_without_original_teacher_av(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "m15.csv"
            with source.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close"])
                writer.writeheader()
                writer.writerow(dict(timestamp=900, open=100, high=102, low=99, close=101))
                writer.writerow(dict(timestamp=1800, open=101, high=103, low=100, close=102))
            result = evaluate(str(source), None, as_of=2700)
        self.assertEqual(result["side_decision_evaluations"], 4 * len(REQUIRED))
        self.assertEqual(result["teacher_approved_entries"], 0)
        self.assertEqual(result["trades_executed"], 0)
        for route in result["routes"]:
            for side in ("BUY", "SELL"):
                self.assertFalse(route["side_decisions"][side]["trade_permitted"])
                self.assertEqual(route["side_decisions"][side]["states"],
                                 {"BLOCKED_TEACHER_AV_UNVERIFIED": 2})

if __name__ == "__main__":
    unittest.main()
