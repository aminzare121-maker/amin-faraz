"""Automatic, causal *price observations* for instructor pivot/break/pullback.

Teacher materials: Technical(1).pdf pp.2 (pivot), 5 (pullback), 14
(break entry), 17 (structural SL), and S12 machine speech ~2950s.
These observations never claim teacher-confirmed MAJOR/MINOR pivot, relative
last-leg selection, economic sentiment, or permission to place an order.

No heuristic threshold, swing size, lookahead, broker API or guessed prices.
A strict 3-bar extremum is only a *candidate* geometry, NOT teacher's rule.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

SOURCE = ('Technical(1).pdf#page=2', 'Technical(1).pdf#page=5',
          'Technical(1).pdf#page=14', 'Technical(1).pdf#page=17',
          'S12_MACHINE_SPEECH_UNVERIFIED#2950-2965')


@dataclass(frozen=True)
class _Pivot:
    side: str
    level: Decimal
    opened_at: int
    confirmed_at: int


class StructureObserver:
    """Consume M15 bars oldest-to-newest, emitting only known-at-close facts."""
    def __init__(self, interval_seconds: int = 900):
        if type(interval_seconds) is not int or interval_seconds <= 0:
            raise ValueError('INVALID_INTERVAL')
        self.interval = interval_seconds
        self.recent = []
        self.previous_close = None
        self.last_time = None
        self.pivots = {'BUY': None, 'SELL': None}
        self.breaks = {'BUY': None, 'SELL': None}
        self.counts = {'bars': 0, 'gaps': 0, 'raw_pivot_highs': 0,
                       'raw_pivot_lows': 0, 'raw_breaks': 0,
                       'raw_retests': 0}

    @staticmethod
    def _price(b, name):
        try: v=Decimal(str(getattr(b, name)))
        except (ValueError,TypeError,AttributeError): raise ValueError('BAD_BAR_'+name) from None
        if not v.is_finite() or v <= 0: raise ValueError('BAD_BAR_'+name)
        return v

    def step(self, bar):
        t=getattr(bar, 't', None)
        if type(t) is not int or t < 0:
            raise ValueError('BAD_NATIVE_OPEN_TIME')
        op,hi,lo,cl=(self._price(bar,k) for k in ('open','high','low','close'))
        if lo>min(op,cl) or hi<max(op,cl):
            raise ValueError('BAD_OHLC')
        if self.last_time is not None and t<=self.last_time:
            raise ValueError('DUPLICATE_OR_UNSORTED')
        gap=self.last_time is not None and t!=self.last_time+self.interval
        if gap:
            # Session closure must not silently become a continuous pattern.
            self.recent=[]
            self.pivots={'BUY':None,'SELL':None}
            self.breaks={'BUY':None,'SELL':None}
            self.previous_close=None
            self.counts['gaps']+=1
        known_at=t+self.interval
        observed={'schema':'artin_teacher_auto_structure_v1',
                  'bar_open_native':t, 'known_at_native':known_at,
                  'gap_reset':gap, 'sources':SOURCE,
                  'new_pivot_candidates':[], 'new_break_candidates':[],
                  'new_retest_candidates':[], 'teacher_semantics_verified':False,
                  'teacher_trade_authorized':False}
        # An identified candidate level must have been confirmed before the
        # current candle opened; do not use a pivot formed by this candle.
        for side in ('BUY','SELL'):
            pivot=self.pivots[side]
            if pivot is None or pivot.confirmed_at>t or self.previous_close is None:
                continue
            crossed=(self.previous_close<=pivot.level and cl>pivot.level
                     if side=='BUY' else self.previous_close>=pivot.level and cl<pivot.level)
            if crossed:
                event={'side':side, 'level':str(pivot.level),
                       'pivot_candle_open':pivot.opened_at,
                       'pivot_confirmed_at':pivot.confirmed_at,
                       'break_bar_open':t, 'known_at':known_at,
                       'type':'CLOSED_PRICE_BEYOND_CANDIDATE_PIVOT',
                       'teacher_break_strength_verified':False}
                observed['new_break_candidates'].append(event)
                self.breaks[side]=event
                self.counts['raw_breaks']+=1
            oldbreak=self.breaks[side]
            # First later touch is measured, but touching is not teacher's
            # confirmation candle, and cannot itself authorize an entry.
            if oldbreak is not None and oldbreak['break_bar_open'] < t:
                if lo<=Decimal(oldbreak['level'])<=hi:
                    retest={'side':side,'level':oldbreak['level'],
                            'break_bar_open':oldbreak['break_bar_open'],
                            'retest_bar_open':t,'known_at':known_at,
                            'type':'GEOMETRIC_RETURN_TO_BROKEN_PIVOT',
                            'teacher_retest_confirmed':False}
                    observed['new_retest_candidates'].append(retest)
                    self.breaks[side]=None
                    self.counts['raw_retests']+=1
        self.recent.append((t,hi,lo))
        self.recent=self.recent[-3:]
        if len(self.recent)==3:
            (ta,ha,la),(tb,hb,lb),(tc,hc,lc)=self.recent
            # Two strict comparisons carry NO numeric tolerance. The name
            # 'candidate' explicitly separates geometry from teacher selection.
            for side,ok,level in (('BUY',hb>ha and hb>hc,hb),
                                  ('SELL',lb<la and lb<lc,lb)):
                if not ok:continue
                p=_Pivot(side,level,tb,known_at)
                self.pivots[side]=p
                observed['new_pivot_candidates'].append({
                    'side_of_future_break':side,'level':str(level),
                    'pivot_candle_open':tb,'known_at':known_at,
                    'type':'STRICT_LOCAL_THREE_BAR_EXTREMUM_CANDIDATE',
                    'teacher_major_minor_pivot_confirmed':False})
                self.counts['raw_pivot_highs' if side=='BUY' else 'raw_pivot_lows']+=1
        self.last_time=t
        self.previous_close=cl
        self.counts['bars']+=1
        observed['totals']=dict(self.counts)
        return observed


def observe_structure(bars: Sequence, interval_seconds: int=900):
    if not isinstance(bars, (list,tuple)) or not bars:
        raise ValueError('CLOSED_BARS_REQUIRED')
    engine=StructureObserver(interval_seconds)
    last=None
    for b in bars: last=engine.step(b)
    return last