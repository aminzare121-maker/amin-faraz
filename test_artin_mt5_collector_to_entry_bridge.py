"""Synthetic contract tests only; no MT5 session, teacher approval or P&L."""
import csv
import tempfile
import unittest
from pathlib import Path

from artin_mt5_shadow_bridge import HEADER, LABEL, SourceRejected
from artin_mt5_collector_to_entry_bridge import evaluate_collector_csv


class CollectorToEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "collector.csv"
        self.rows = [
            [LABEL, 1800000000, "2027.01.15 10:00:00", "XAUUSD", "M15",
             4000, 4002, 3999, 4001, 100, 10, 0, 0, 0],
            [LABEL, 1800000900, "2027.01.15 10:15:00", "XAUUSD", "M15",
             4001, 4003, 4000, 4002, 100, 10, 0, 0, 0],
        ]
        self.write()
    def tearDown(self):
        self.tmp.cleanup()
    def write(self):
        with self.path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            w.writerows(self.rows)
    def test_real_engine_receives_collector_bars_but_no_orders(self):
        result = evaluate_collector_csv(self.path, as_of=1800001800)
        self.assertEqual(result["source_rows"], 2)
        self.assertEqual(result["collector_intake"]["source_rows"], 2)
        self.assertEqual(result["independent_engine"]["evaluations"], 52)
        self.assertEqual(result["independent_engine"]["orders_created"], 0)
        self.assertEqual(result["trades_executed"], 0)
        self.assertFalse(result["collector_intake"]["original_teacher_av_certified"])
        self.assertFalse(result["collector_intake"]["mt5_demo_account_independently_confirmed"])
    def test_unclosed_bar_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNCLOSED_OR_FUTURE_SOURCE_BAR"):
            evaluate_collector_csv(self.path, as_of=1800001799)
    def test_forged_authorization_rejected(self):
        self.rows[0][-1] = 1
        self.write()
        with self.assertRaises(SourceRejected):
            evaluate_collector_csv(self.path, as_of=1800001800)
    def test_nonmonotonic_broker_bars_rejected(self):
        self.rows[1][1] = 1800000000
        self.write()
        with self.assertRaises(SourceRejected):
            evaluate_collector_csv(self.path, as_of=1800001800)
    def test_dossier_flag_cannot_authorize(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PRIVATE_DOSSIER"):
            evaluate_collector_csv(self.path, dossier={"trading_authorized": True},
                                   as_of=1800001800)


if __name__ == "__main__":
    unittest.main()
