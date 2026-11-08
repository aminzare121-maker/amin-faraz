"""Causal structural quality-gate audit; no inference of market/feed validity.

Every history-ready observation uses only its current closed candle and the
preceding63 candles. Public output is aggregate counts, never masks/quotes/rows.
The priority reproduces frozen strict gating while marginal counts disclose
overlapping reasons that a priority-only table would otherwise hide.
"""

import math
from collections import deque
from datetime import datetime, timezone


INTERVAL = 900
HISTORY = 64
PRIMARY = ("warmup", "gap", "weekend", "flat_past64", "eligible")
FLAGS = ("gap_past64", "weekend_proxy", "flat_past64")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _counts():
    return {
        "total_rows": 0,
        "history_ready_rows": 0,
        "raw_current_flat_rows": 0,
        "primary_priority_counts": {name: 0 for name in PRIMARY},
        "marginal_history_ready_counts": {name: 0 for name in FLAGS},
        "exact_bitmask_counts": {str(mask): 0 for mask in range(8)},
    }


def _add(group, flat_now, ready, mask, reason):
    group["total_rows"] += 1
    group["raw_current_flat_rows"] += int(flat_now)
    group["primary_priority_counts"][reason] += 1
    if ready:
        group["history_ready_rows"] += 1
        group["exact_bitmask_counts"][str(mask)] += 1
        group["marginal_history_ready_counts"]["gap_past64"] += int(bool(mask & 1))
        group["marginal_history_ready_counts"]["weekend_proxy"] += int(bool(mask & 2))
        group["marginal_history_ready_counts"]["flat_past64"] += int(bool(mask & 4))


def audit_quality(bars):
    """Return structural aggregate flags/overlaps and conditional counts.

    Bit1=any non900-second adjacent observation interval in past64;
    bit2=current decision close falls on a UTC Saturday/Sunday proxy;
    bit4=any OHLC-identical candle in past64. Warmup belongs to none of these
    ready-history denominators. Month/weekday are based on decision close,
    exactly as the frozen strict weekend gate. Missing observations are never
    interpolated, and a structural flag never establishes its actual cause.
    """
    totals = _counts()
    conditional = {"current_flat": _counts(), "current_nonflat": _counts()}
    months = {}
    weekdays = {name: _counts() for name in WEEKDAYS}
    flat_window = deque()
    gap_window = deque()
    flat_count = gap_count = 0
    previous_time = None

    for index, bar in enumerate(bars):
        if type(bar.time) is not int or bar.time < 0:
            raise ValueError("Quality audit requires nonnegative integer observation times")
        if previous_time is not None and bar.time <= previous_time:
            raise ValueError("Quality audit requires strictly ordered observations")
        values = (bar.open, bar.high, bar.low, bar.close)
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("Quality audit requires finite observed OHLC")
        if min(values) <= 0 or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high:
            raise ValueError("Quality audit requires structurally consistent observed OHLC")

        flat_now = bar.open == bar.high == bar.low == bar.close
        flat_window.append(flat_now)
        flat_count += int(flat_now)
        if len(flat_window) > HISTORY:
            flat_count -= int(flat_window.popleft())
        if previous_time is not None:
            gap = bar.time - previous_time != INTERVAL
            gap_window.append(gap)
            gap_count += int(gap)
            if len(gap_window) > HISTORY - 1:
                gap_count -= int(gap_window.popleft())
        previous_time = bar.time

        decision = datetime.fromtimestamp(bar.time + INTERVAL, timezone.utc)
        ready = index >= HISTORY - 1
        mask = ((int(gap_count > 0) | (int(decision.weekday() >= 5) << 1)
                 | (int(flat_count > 0) << 2)) if ready else 0)
        reason = ("warmup" if not ready else "gap" if mask & 1 else
                  "weekend" if mask & 2 else "flat_past64" if mask & 4 else "eligible")
        month = decision.strftime("%Y-%m")
        group = months.setdefault(month, _counts())
        current = conditional["current_flat" if flat_now else "current_nonflat"]
        for destination in (totals, current, group, weekdays[WEEKDAYS[decision.weekday()]]):
            _add(destination, flat_now, ready, mask, reason)

    if sum(totals["primary_priority_counts"].values()) != totals["total_rows"]:
        raise AssertionError("Primary quality counts do not reconcile")
    if sum(totals["exact_bitmask_counts"].values()) != totals["history_ready_rows"]:
        raise AssertionError("Quality overlap counts do not reconcile")
    return {
        **totals,
        "schema": 1,
        "history_closed_bars": HISTORY,
        "primary_priority_order": list(PRIMARY),
        "bitmask_definition": {"1": "gap_past64", "2": "weekend_proxy", "4": "flat_past64"},
        "conditional_on_current_flat": conditional,
        "by_month": dict(sorted(months.items())),
        "by_utc_weekday": weekdays,
        "denominators": {
            "primary": "all observations including warmup",
            "marginal_and_intersections": "history-ready observations only",
            "current_flat": "current candle OHLC exactly identical, including warmup",
            "month_and_weekday": "current closed-candle decision time = observation time+900, UTC",
        },
        "causal": True,
        "rows_modified": False,
        "interpolation_performed": False,
        "market_invalidity_inferred": False,
        "flat_ohlc_actual_cause": "UNKNOWN",
        "feed_validity": "UNVERIFIED",
        "session_calendar_validity": "UNVERIFIED",
        "interpretation": (
            "Structural rules describe this frozen eligibility filter only. "
            "Priority exclusions are conditional on higher-priority reasons; "
            "marginal flags overlap. A current nonflat candle can have a flat "
            "within its past64. Flat/gap/weekend flags do not identify the "
            "cause, quote validity, or whether a real market session was open."
        ),
    }
