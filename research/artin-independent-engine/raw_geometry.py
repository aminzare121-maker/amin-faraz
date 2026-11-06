"""Causal raw geometry only; no strong/fullbody/doji threshold or trade signal.

API: Candle(opened_at, closed_at, open, high, low, close), integer times and
finite positive Decimal prices. extract(candles, *, at, interval_seconds) requires
explicit fixed bar duration and strict chronological input. Only candles closed
by `at` produce geometry/candidates. Missing intervals are reported and break all
three-bar candidates. FVG_CANDIDATE means uncovered first/third wick geometry,
not a verified strong move, valid zone, inevitable fill, or entry permission.
Source: method_reference fvg_three_candle_scope, session19 2135..2595,
2900..2999,3357..3395,3761..3814 (prior text-study evidence, not fresh audio).
"""
from dataclasses import dataclass
from decimal import Decimal

FVG_SOURCES=((19,2135,2595),(19,2900,2999),(19,3357,3395),(19,3761,3814))

def _time(value):
    if type(value) is not int or value<0:raise ValueError('nonnegative integer time required')

def _price(value):
    if not isinstance(value,Decimal) or not value.is_finite() or value<=0:
        raise ValueError('positive finite Decimal price required')

@dataclass(frozen=True)
class Candle:
    opened_at: int
    closed_at: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        _time(self.opened_at);_time(self.closed_at)
        if self.closed_at<=self.opened_at:raise ValueError('closed_at must follow opened_at')
        for value in (self.open,self.high,self.low,self.close):_price(value)
        if not self.low<=min(self.open,self.close)<=max(self.open,self.close)<=self.high:
            raise ValueError('inconsistent OHLC')

@dataclass(frozen=True)
class Geometry:
    opened_at: int
    known_at: int
    body: Decimal
    upper_wick: Decimal
    lower_wick: Decimal
    range: Decimal
    color: str
    body_midpoint: Decimal

@dataclass(frozen=True)
class Candidate:
    kind: str
    direction: str
    candle_open_times: tuple
    known_at: int
    low: object
    high: object
    sources: tuple
    signal: bool=False

def geometry(candle):
    if not isinstance(candle,Candle):raise ValueError('Candle required')
    return Geometry(candle.opened_at,candle.closed_at,abs(candle.close-candle.open),
                    candle.high-max(candle.open,candle.close),min(candle.open,candle.close)-candle.low,
                    candle.high-candle.low,'UP' if candle.close>candle.open else 'DOWN' if candle.close<candle.open else 'FLAT',
                    (candle.open+candle.close)/Decimal(2))

def touches(candidate,price):
    """Inclusive raw boundary contact only; never means consumption or entry."""
    _price(price)
    if not isinstance(candidate,Candidate) or candidate.kind!='FVG_CANDIDATE':
        raise ValueError('FVG candidate required')
    return candidate.low<=price<=candidate.high

def extract(candles,*,at,interval_seconds):
    _time(at)
    if type(interval_seconds) is not int or interval_seconds<=0:raise ValueError('explicit positive interval required')
    bars=tuple(candles)
    previous=None
    for candle in bars:
        if not isinstance(candle,Candle):raise ValueError('Candle required')
        if candle.closed_at-candle.opened_at!=interval_seconds:raise ValueError('bar duration differs from declared interval')
        if previous is not None and (candle.opened_at<=previous.opened_at or candle.opened_at<previous.closed_at):
            raise ValueError('strict ascending nonoverlapping candles required')
        previous=candle
    closed=tuple(c for c in bars if c.closed_at<=at)
    shapes=tuple(geometry(c) for c in closed)
    gaps=tuple((a.closed_at,b.opened_at) for a,b in zip(closed,closed[1:]) if a.closed_at!=b.opened_at)
    candidates=[]
    for i in range(2,len(closed)):
        a,b,c=closed[i-2:i+1]
        if a.closed_at!=b.opened_at or b.closed_at!=c.opened_at:continue
        times=(a.opened_at,b.opened_at,c.opened_at)
        colors=tuple(s.color for s in shapes[i-2:i+1])
        if colors[0] in ('UP','DOWN') and colors[0]==colors[1]==colors[2]:
            candidates.append(Candidate('THREE_SAME_DIRECTION_CANDIDATE',colors[0],times,c.closed_at,None,None,()))
        if a.high<c.low:
            candidates.append(Candidate('FVG_CANDIDATE','UP',times,c.closed_at,a.high,c.low,FVG_SOURCES))
        elif c.high<a.low:
            candidates.append(Candidate('FVG_CANDIDATE','DOWN',times,c.closed_at,c.high,a.low,FVG_SOURCES))
    return dict(geometry=shapes,candidates=tuple(candidates),gaps=gaps,as_of=at,
                interval_seconds=interval_seconds,classification='RAW_GEOMETRY_ONLY')
