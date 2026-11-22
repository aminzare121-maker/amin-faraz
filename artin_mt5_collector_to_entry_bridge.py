"""Read-only bridge from MT5 DEMO collector CSV to existing 13-route M15 engine.

The CSV is untrusted even if its label says DEMO. This adapter does not
authenticate the broker, certify the teacher, or send any order.
"""
from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

from artin_mt5_shadow_bridge import parse_csv_bytes
from artin_13_per_bar_teacher_bridge import evaluate


def evaluate_collector_csv(source: Path, *, dossier=None, as_of: int):
    """Run the actual entry engine on validated, CLOSED collector bars only.

    as_of is an explicit integer decision clock; future/unfinished bars fail.
    The private dossier is never written to the temporary OHLC stream.
    """
    if type(as_of) is not int or as_of < 0:
        raise ValueError("INVALID_DECISION_CLOCK")
    raw = Path(source).read_bytes()
    metrics = parse_csv_bytes(raw)
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    with tempfile.TemporaryDirectory(prefix="artin_readonly_") as temp:
        path = Path(temp) / "closed_m15.csv"
        with path.open("w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(("timestamp", "open", "high", "low", "close"))
            for row in rows:
                writer.writerow((row["broker_epoch"], row["open"], row["high"],
                                 row["low"], row["close"]))
        result = evaluate(path, dossier, as_of=as_of)
    if result["source_rows"] != metrics["source_rows"]:
        raise AssertionError("COLLECTOR_ENGINE_ROW_COUNT_MISMATCH")
    if result["independent_engine"]["orders_created"] != 0 or result["trades_executed"] != 0:
        raise AssertionError("READ_ONLY_ENGINE_SENT_ORDERS")
    result["collector_intake"] = {
        **metrics,
        "source_claim_not_independently_authenticated": True,
        "original_teacher_av_certified": False,
        "mt5_demo_account_independently_confirmed": False,
        "orders_sent": 0,
    }
    return result
