"""Immutable, supplied-time market observations for the offline prototype.

All times are integer UTC milliseconds supplied by the caller.  No wall clock is
read.  A candle's OHLC becomes eligible only when it is final, its interval has
ended, and its final payload has arrived.  An open candle is never a peak source.
"""
from dataclasses import dataclass
from decimal import (Context, Decimal, DivisionByZero, InvalidOperation, Overflow,
                     ROUND_HALF_EVEN, localcontext)
from functools import wraps
from typing import Iterable

from .numbers import dec, natural


_CALCULATION_CONTEXT = Context(
    prec=512, rounding=ROUND_HALF_EVEN, Emin=-999999, Emax=999999,
    capitals=1, clamp=0, flags=[], traps=[InvalidOperation, DivisionByZero, Overflow],
)


def fixed_decimal(function):
    """Isolate deterministic arithmetic from a caller's Decimal context.

    Precision 512 covers the bounded decimal inputs of this offline prototype.
    A private local context also prevents our flags from changing the caller.
    """
    @wraps(function)
    def calculate(*args, **kwargs):
        with localcontext(_CALCULATION_CONTEXT):
            return function(*args, **kwargs)
    return calculate


@dataclass(frozen=True)
class EventAvailability:
    event_ms: int
    available_ms: int

    def __post_init__(self):
        natural(self.event_ms)
        natural(self.available_ms)

    def veto(self, decision_ms: int, max_age_ms: int | None = None) -> str | None:
        natural(decision_ms)
        if self.event_ms > self.available_ms or self.event_ms > decision_ms:
            return "FUTURE_SOURCE_CLOCK"
        if self.available_ms > decision_ms:
            return "NOT_YET_AVAILABLE"
        if max_age_ms is not None:
            natural(max_age_ms)
            if decision_ms - self.event_ms > max_age_ms:
                return "STALE_QUOTE"
        return None


@dataclass(frozen=True)
class Quote:
    event_ms: int
    available_ms: int
    bid: Decimal
    ask: Decimal
    executable: bool = True

    def __post_init__(self):
        natural(self.event_ms)
        natural(self.available_ms)
        object.__setattr__(self, "bid", dec(self.bid))
        object.__setattr__(self, "ask", dec(self.ask))
        if self.bid <= 0 or self.ask < self.bid:
            raise ValueError("INVALID_BID_ASK")
        if type(self.executable) is not bool:
            raise ValueError("EXECUTABLE_FLAG_REQUIRED")

    @property
    def availability(self) -> EventAvailability:
        return EventAvailability(self.event_ms, self.available_ms)

    def exit_price(self, side: str) -> Decimal:
        if side == "buy":
            return self.bid
        if side == "sell":
            return self.ask
        raise ValueError("SIDE_MUST_BE_BUY_OR_SELL")


@dataclass(frozen=True)
class Candle:
    open_ms: int
    duration_ms: int
    available_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    final: bool = True

    def __post_init__(self):
        natural(self.open_ms)
        natural(self.duration_ms)
        natural(self.available_ms)
        if self.duration_ms == 0:
            raise ValueError("POSITIVE_CANDLE_DURATION_REQUIRED")
        if type(self.final) is not bool:
            raise ValueError("FINAL_FLAG_REQUIRED")
        for name in ("open", "high", "low", "close"):
            object.__setattr__(self, name, dec(getattr(self, name)))
        if (self.low <= 0 or self.low > min(self.open, self.close)
                or self.high < max(self.open, self.close) or self.high < self.low):
            raise ValueError("INVALID_OHLC")

    @property
    def close_ms(self) -> int:
        return self.open_ms + self.duration_ms

    def available_at(self, decision_ms: int) -> bool:
        natural(decision_ms)
        return (self.final and self.available_ms >= self.close_ms
                and self.close_ms <= decision_ms and self.available_ms <= decision_ms)


def validate_quote(quote: Quote | None, decision_ms: int,
                   max_age_ms: int = 1000) -> str | None:
    """Return the veto reason; a valid executable observation returns None."""
    natural(decision_ms)
    natural(max_age_ms)
    if quote is None:
        return "MISSING_QUOTE"
    veto = quote.availability.veto(decision_ms, max_age_ms)
    if veto is not None:
        return veto
    if not quote.executable:
        return "NONEXECUTABLE_QUOTE"
    return None


def available_candles(candles: Iterable[Candle], decision_ms: int) -> tuple[Candle, ...]:
    """Future/unfinalized records cannot affect an earlier decision prefix."""
    natural(decision_ms)
    result = tuple(sorted((c for c in candles if c.available_at(decision_ms)),
                          key=lambda c: (c.close_ms, c.open_ms)))
    keys = [(c.open_ms, c.duration_ms) for c in result]
    if len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_AVAILABLE_CANDLE")
    return result


@dataclass(frozen=True)
class ATRResult:
    value: Decimal | None
    available_bars: int
    required_bars: int
    reason: str

    @property
    def ready(self) -> bool:
        return self.value is not None


@fixed_decimal
def atr_wilder(candles: Iterable[Candle], decision_ms: int,
               period: int = 14) -> ATRResult:
    """Wilder ATR: 14 TR observations need 15 closed available bars.

    The first bar supplies previous close only.  Seed is the arithmetic mean of
    the next ``period`` true ranges. Subsequent values use Wilder smoothing.
    Missing bars are not fabricated; distinct supplied intervals are required.
    """
    natural(period)
    if period == 0:
        raise ValueError("POSITIVE_ATR_PERIOD_REQUIRED")
    bars = available_candles(candles, decision_ms)
    required = period + 1
    if len(bars) < required:
        return ATRResult(None, len(bars), required, "ATR_WARMUP")
    durations = {bar.duration_ms for bar in bars}
    if len(durations) != 1:
        return ATRResult(None, len(bars), required, "MIXED_CANDLE_DURATION")
    if any(right.open_ms != left.close_ms for left, right in zip(bars, bars[1:])):
        return ATRResult(None, len(bars), required, "NONCONTIGUOUS_CANDLES")
    ranges = tuple(max(current.high - current.low,
                       abs(current.high - previous.close),
                       abs(current.low - previous.close))
                   for previous, current in zip(bars, bars[1:]))
    value = sum(ranges[:period], Decimal(0)) / period
    for true_range in ranges[period:]:
        value = (value * (period - 1) + true_range) / period
    return ATRResult(value, len(bars), required, "READY")
