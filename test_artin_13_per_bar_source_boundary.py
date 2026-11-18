"""Real M15 input boundary regression; no teacher route is certified."""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate

FIELDS = ("timestamp", "open", "high", "low", "close")

class TestM15SourceBoundary(unittest.TestCase):
    def run_rows(self, rows, *, as_of=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            return evaluate(str(path), as_of=as_of)

    def test_replay_rejects_unclosed_and_future_m15_bars(self):
        bar = dict(zip(FIELDS, (900, 100, 110, 90, 105)))
        for clock in (900, 1799):
            with self.subTest(clock=clock):
                with self.assertRaisesRegex(ValueError, "UNCLOSED_OR_FUTURE_SOURCE_BAR"):
                    self.run_rows([bar], as_of=clock)
        result = self.run_rows([bar], as_of=1800)
        self.assertTrue(result["causal_close_clock_checked"])
        self.assertEqual(result["teacher_approved_entries"], 0)
        self.assertEqual(result["trades_executed"], 0)

    def test_invalid_decision_clock_rejected(self):
        bar = dict(zip(FIELDS, (900, 100, 110, 90, 105)))
        for clock in (True, -1, 1800.0, "1800"):
            with self.subTest(clock=clock):
                with self.assertRaisesRegex(ValueError, "INVALID_DECISION_CLOCK"):
                    self.run_rows([bar], as_of=clock)

    def test_empty_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "EMPTY_SOURCE_BARS"):
            self.run_rows([])

    def test_nonfinite_prices_rejected(self):
        for bad in ("nan", "inf", "-inf"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_BAR"):
                    self.run_rows([dict(zip(FIELDS, (900, 100, 110, 90, bad)))])

    def test_valid_market_observation_never_authorizes_teacher(self):
        result = self.run_rows([dict(zip(FIELDS, (900, 100, 110, 90, 105)))])
        self.assertEqual(result["source_rows"], 1)
        self.assertEqual(result["teacher_approved_entries"], 0)
        self.assertEqual(result["trades_executed"], 0)

if __name__ == "__main__":
    unittest.main()
