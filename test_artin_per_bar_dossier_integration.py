"""Integration of private dossier gate with actual M15 per-bar research bridge.
Synthetic fixture verifies safety only, not instructor semantics or profitability.
"""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from test_artin_dossier_decision_gate import fixture


class PerBarDossierIntegrationTests(unittest.TestCase):
    def test_private_dossier_never_authorizes_market_only_bar(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "m15.csv"
            with source.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["timestamp", "open", "high", "low", "close"])
                w.writeheader()
                for i in range(3):
                    w.writerow(dict(timestamp=900*(i+1), open=4000+i, high=4003+i,
                                    low=3999+i, close=4002+i))
            for dossier, reason in (
                (None, "INVALID_PRIVATE_DOSSIER"),
                (fixture(), "ORIGINAL_TEACHER_AV_REPLAY_NOT_CERTIFIED"),
            ):
                result = evaluate(str(source), dossier)
                self.assertEqual(result["source_rows"], 3)
                self.assertEqual(result["teacher_approved_entries"], 0)
                self.assertEqual(result["trades_executed"], 0)
                self.assertFalse(result["evidence_gate"]["trade_authorized"])
                self.assertEqual(result["evidence_gate"]["reason"], reason)
                self.assertEqual(len(result["routes"]), 13)

    def test_claimed_teacher_approval_cannot_turn_market_bars_into_orders(self):
        # An untrusted private JSON can claim approval, but cannot supply
        # independently replayed original audio/video or a certified rule.
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "m15.csv"
            source.write_text(
                "timestamp,open,high,low,close\n"
                "900,4000,4002,3999,4001\n"
                "1800,4001,4003,4000,4002\n"
                "2700,4002,4004,4001,4003\n", encoding="utf-8")
            dossier = fixture()
            dossier["semantics_independently_approved"] = 13
            dossier["trading_authorized"] = True
            for route in dossier["routes"]:
                route["teacher_case_certified"] = True
                route["orders_authorized"] = 1
                route["entry_signal"] = "BUY"
            result = evaluate(str(source), dossier)
            self.assertEqual(result["source_rows"], 3)
            self.assertEqual(result["total_route_bar_evaluations"], 39)
            self.assertEqual(result["teacher_approved_entries"], 0)
            self.assertEqual(result["trades_executed"], 0)
            self.assertEqual(result["evidence_gate"]["reason"],
                             "ORIGINAL_TEACHER_AV_REPLAY_NOT_CERTIFIED")
            self.assertFalse(result["evidence_gate"]["trade_authorized"])

    def test_corrupted_dossier_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "m15.csv"
            source.write_text("timestamp,open,high,low,close\\n900,4000,4002,3999,4001\\n".replace("\\n", "\n"))
            dossier = fixture()
            dossier["routes"][0]["citation_intervals"][0]["index"] = 25
            result = evaluate(str(source), dossier)
            self.assertEqual(result["evidence_gate"]["reason"], "INVALID_SOURCE_INTERVAL")
            self.assertEqual(result["trades_executed"], 0)


if __name__ == "__main__":
    unittest.main()
