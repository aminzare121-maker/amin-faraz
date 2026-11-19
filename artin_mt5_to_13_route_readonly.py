"""Connect validated closed MT5 M15 bars to the existing 13-route decision bridge.

Read-only: the output is never an entry signal or order authorization.
"""
from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

from artin_mt5_shadow_bridge import parse_csv_bytes, HEADER
from artin_13_per_bar_teacher_bridge import evaluate


def evaluate_mt5_closed_bars(raw: bytes, dossier=None, *, as_of=None) -> dict:
    """Validate the original collector format, then replay identical bar timestamps.

    The collector's broker_epoch is a bar OPEN time; the per-bar bridge checks
    that bar close (open+900 seconds) precedes as_of when supplied.
    """
    source = parse_csv_bytes(raw)
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    normalized = io.StringIO()
    writer = csv.DictWriter(normalized, fieldnames=("timestamp", "open", "high", "low", "close"))
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "timestamp": row["broker_epoch"],
            "open": row["open"], "high": row["high"],
            "low": row["low"], "close": row["close"],
        })
    # Existing decision bridge takes a file path; use a temporary file and
    # remove it before returning. Never write private dossier data to disk.
    with tempfile.TemporaryDirectory(prefix="artin_mt5_bridge_") as folder:
        path = Path(folder) / "closed_m15.csv"
        path.write_text(normalized.getvalue(), encoding="utf-8")
        result = evaluate(path, dossier, as_of=as_of)
    if result["source_rows"] != source["source_rows"]:
        raise AssertionError("MT5_BRIDGE_ROW_COUNT_MISMATCH")
    if result["teacher_approved_entries"] or result["trades_executed"]:
        raise AssertionError("UNEXPECTED_EXECUTABLE_BRIDGE_RESULT")
    return {
        "schema": "artin_mt5_closed_bar_to_13_route_readonly_v1",
        "source": source,
        "decisions": result,
        "teacher_semantics_certified": False,
        "trade_authorized": False,
        "orders_sent": 0,
    }
