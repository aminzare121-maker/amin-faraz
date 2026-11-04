"""Explicit readonly CSV ingestion and causal, hypothetical quality policies."""
import csv
import hashlib
import io
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .types import Bar

DATA_SHA256 = "8a0ecb9bf47096541bd581b5c21c3cc355930f8a110cad21cc64f6235fe13cdd"
QUALITIES = ("strict", "flat_inclusive_weekdays", "inclusive_irregular")


def load_csv(path):
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != DATA_SHA256:
        raise ValueError("CSV identity differs from authorized input")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != ["timestamp", "open", "high", "low", "close"]:
        raise ValueError("Unexpected CSV schema")
    bars = []
    for row in reader:
        ms = int(row["timestamp"])
        values = [float(row[k]) for k in ("open", "high", "low", "close")]
        o, h, l, c = values
        if (ms % 900000 or not all(math.isfinite(v) and v > 0 for v in values)
                or not l <= o <= h or not l <= c <= h
                or (bars and ms // 1000 <= bars[-1].time)):
            raise ValueError("Invalid or unordered input bar")
        bars.append(Bar(ms // 1000, o, h, l, c))
    gaps = [b.time-a.time for a, b in zip(bars, bars[1:]) if b.time-a.time > 900]
    return bars, {
        "sha256": sha, "bytes": len(raw), "records": len(bars),
        "first_utc": datetime.fromtimestamp(bars[0].time, timezone.utc).isoformat(),
        "last_utc": datetime.fromtimestamp(bars[-1].time, timezone.utc).isoformat(),
        "gap_events": len(gaps), "maximum_gap_seconds": max(gaps),
        "missing_calendar_slots_not_market_sessions": sum(d//900-1 for d in gaps),
        "flat_ohlc": sum(b.open == b.high == b.low == b.close for b in bars),
        "volume_present": False, "historical_ask_spread_present": False,
        "provenance": "UNVERIFIED", "rights": "UNVERIFIED", "session_calendar": "UNVERIFIED",
        "development_only_previously_seen_data": True,
    }


def quality_gate(bars, index, quality):
    if quality not in QUALITIES:
        raise ValueError("Unknown quality policy")
    if index < 63:
        return "warmup"
    past = bars[index-63:index+1]
    if quality != "inclusive_irregular":
        if any(b.time-a.time != 900 for a, b in zip(past, past[1:])):
            return "historical_gap"
        if datetime.fromtimestamp(bars[index].time+900, timezone.utc).weekday() >= 5:
            return "utc_weekend_proxy_not_true_session"
    if quality == "strict" and any(b.open == b.high == b.low == b.close for b in past):
        return "flat_in_past64"
    return None


def build_signals(bars, quality, producer):
    signals = {}
    counts = Counter()
    for i in range(len(bars)):
        reason = quality_gate(bars, i, quality)
        if reason:
            counts[reason] += 1
            continue
        counts["eligible_decision_bars"] += 1
        candidate = producer(bars, i, allow_history_gaps=quality == "inclusive_irregular")
        if candidate is None:
            counts["no_rule_setup"] += 1
        else:
            signals[i] = candidate
            counts["rule_signals"] += 1
    counts["total_bars"] = len(bars)
    return signals, dict(counts)
