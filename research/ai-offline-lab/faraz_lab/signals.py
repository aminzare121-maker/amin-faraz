"""Causal, fixed offline signals; no engine, account or network imports.

B1 adapts the frozen release's strategy.plan(Candidate('breakout', 20, 1.5))
and the exact seven raw learning features.  All supplied Bar objects represent
closed, observed candles.  This lab additionally requires 64 history candles.
B2 is the predeclared SMA5/20 cross, with the same stop and feature calculation.
Flat/weekend entry gates belong to the caller's declared quality scenario.
"""

import math
from decimal import Decimal
from statistics import mean

from .types import Bar, Candidate


FEATURES = (
    'price_slope', 'body', 'wick_imbalance', 'range_expansion',
    'relative_tick_volume', 'location', 'side',
)
FEATURE_METADATA = {
    'relative_tick_volume': {
        'imputed': True,
        'value': 1.0,
        'reason': 'CSV_has_no_tick_volume',
    },
}
SOURCE_PROVENANCE = {
    'release': '20261031T061122830201Z',
    'strategy_source_sha256': 'ef535a69968c62e97567197d8a259a53f8a5f155ce7998888a922e718197945f',
    'strategy_snapshot_sha256': 'a701beabb418d476220877af69cf9f47def064fe865f47a421ca16781ffd1bd5',
    'analysis_source_sha256': '4e053a53d5227a42a5a887a1d1f646117922f018382418a477756867d7ab4d1c',
    'source_commit': 'ed4591a22349621ce2ac70fbb4554ce4f402f2b5',
    'b1': 'fixed-breakout-20-stop-1.5; exact raw seven features',
    'b2': 'predeclared-SMA5-20-cross; not an original engine strategy',
}


def _history(bars: list[Bar], index: int, allow_history_gaps: bool):
    if not isinstance(index, int) or isinstance(index, bool):
        raise ValueError('Signal index must be an integer')
    if not isinstance(allow_history_gaps, bool):
        raise ValueError('History gap permission must be explicit boolean')
    if index < 63 or index >= len(bars):
        return None
    history = bars[index - 63:index + 1]
    previous = None
    for bar in history:
        if not isinstance(bar.time, int) or isinstance(bar.time, bool) or bar.time < 0:
            return None
        values = (bar.open, bar.high, bar.low, bar.close)
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            return None
        opened, high, low, close = values
        if min(values) <= 0 or high < max(opened, low, close) or low > min(opened, high, close):
            return None
        if previous is not None:
            if bar.time <= previous:
                return None
            if not allow_history_gaps and bar.time - previous != 900:
                return None
        previous = bar.time
    return history


def _candidate(history: list[Bar], index: int, side: str) -> Candidate | None:
    """Preserve strategy.py:59-70 numeric operations and .01 half-even stop."""
    prior, last = history[-21:-1], history[-1]
    high = max(Decimal(str(bar.high)) for bar in prior)
    low = min(Decimal(str(bar.low)) for bar in prior)
    close, opened = Decimal(str(last.close)), Decimal(str(last.open))
    span = max(Decimal(str(last.high)) - Decimal(str(last.low)), Decimal('.01'))
    range_atr_proxy = mean(float(bar.high) - float(bar.low) for bar in history[-14:])
    distance = max(Decimal(str(range_atr_proxy)) * Decimal('1.5'), Decimal('0.5'))
    stop = (close - distance if side == 'buy' else close + distance).quantize(Decimal('.01'))
    volatility = max(float(range_atr_proxy), .01)
    recent = history[-20:]
    average_range = sum(float(bar.high) - float(bar.low) for bar in recent) / 20
    # Source strategy.py defaults each absent tick_volume to 1.  The approved
    # CSV has no volume column: do not manufacture a varying volume feature.
    volumes = [1.0 for _ in recent]
    vector = [
        (float(close) - float(history[-6].close)) / volatility,
        float(close - opened) / float(span),
        float((min(opened, close) - Decimal(str(last.low)))
              - (Decimal(str(last.high)) - max(opened, close))) / float(span),
        float(span) / max(average_range, .01),
        volumes[-1] / max(sum(volumes) / len(volumes), 1),
        (float(close) - float((high + low) / 2)) / volatility,
        1.0 if side == 'buy' else -1.0,
    ]
    if stop <= 0 or any(not math.isfinite(value) for value in vector):
        return None
    return Candidate(side=side, stop=float(stop), features=vector, signal_index=index)


def b1(bars: list[Bar], index: int, allow_history_gaps: bool = False) -> Candidate | None:
    """Fixed breakout20/stop1.5 from closed history through index only."""
    history = _history(bars, index, allow_history_gaps)
    if history is None:
        return None
    prior, last = history[-21:-1], history[-1]
    high = max(Decimal(str(bar.high)) for bar in prior)
    low = min(Decimal(str(bar.low)) for bar in prior)
    close = Decimal(str(last.close))
    side = 'buy' if close > high else 'sell' if close < low else None
    trend = 'up' if mean(float(bar.close) for bar in history[-5:]) > mean(
        float(bar.close) for bar in history[-20:]
    ) else 'down'
    if side is None or (side == 'buy') != (trend == 'up'):
        return None
    return _candidate(history, index, side)


def b2(bars: list[Bar], index: int, allow_history_gaps: bool = False) -> Candidate | None:
    """Predeclared SMA5/20 crossover; equality belongs to the prior side."""
    history = _history(bars, index, allow_history_gaps)
    if history is None:
        return None
    fast = mean(float(bar.close) for bar in history[-5:])
    slow = mean(float(bar.close) for bar in history[-20:])
    previous_fast = mean(float(bar.close) for bar in history[-6:-1])
    previous_slow = mean(float(bar.close) for bar in history[-21:-1])
    side = ('buy' if previous_fast <= previous_slow and fast > slow else
            'sell' if previous_fast >= previous_slow and fast < slow else None)
    return _candidate(history, index, side) if side else None
