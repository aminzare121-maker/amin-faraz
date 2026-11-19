"""Contract tests for the real MT5 collector -> 13-route blocked replay."""
import csv
import io
import unittest

from artin_mt5_shadow_bridge import HEADER, LABEL, SourceRejected
from artin_mt5_to_13_route_readonly import evaluate_mt5_closed_bars


def collector_csv():
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=HEADER)
    writer.writeheader()
    for i in range(2):
        writer.writerow(dict(
            source_label=LABEL, broker_epoch=str(1800000000 + i * 900),
            broker_walltime="2027.01.01 00:%02d:00" % (i * 15),
            symbol="XAUUSD", timeframe="M15", open="4000", high="4002",
            low="3998", close="4001", tick_volume="50", spread="10",
            real_volume="0", teacher_semantics_verified="0", trade_authorized="0"))
    return buf.getvalue().encode()


class TestMt5To13Route(unittest.TestCase):
    def test_closed_bars_replay_all_routes_without_order(self):
        raw = collector_csv()
        result = evaluate_mt5_closed_bars(raw, as_of=1800001800)
        self.assertEqual(result["source"]["source_rows"], 2)
        self.assertEqual(result["decisions"]["total_route_bar_evaluations"], 26)
        self.assertEqual(result["decisions"]["side_decision_evaluations"], 52)
        self.assertEqual(result["orders_sent"], 0)
        self.assertFalse(result["trade_authorized"])
        self.assertEqual(result["decisions"]["teacher_approved_entries"], 0)

    def test_unclosed_bar_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNCLOSED_OR_FUTURE_SOURCE_BAR"):
            evaluate_mt5_closed_bars(collector_csv(), as_of=1800001799)

    def test_forged_teacher_authorization_rejected(self):
        raw = collector_csv().replace(b",0,0\\r\\n", b",1,1\\r\\n")
        with self.assertRaises(SourceRejected):
            evaluate_mt5_closed_bars(raw)


if __name__ == "__main__":
    unittest.main()
