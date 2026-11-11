"""Causal last-leg *candidates*, never self-certified instructor leg selection.

Source boundary: Technical(1).pdf pages 2, 4, 5 and session 19 machine
speech around 3500--3525 and 4273--4299 seconds (NOT independently reviewed).
This code implements exact OHLC comparisons with zero arbitrary strength/ATR
threshold.  A three-bar geometric pivot is NOT a teacher-major/minor pivot.
No broker API and no order authorisation.
"""
from __future__ import annotations
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SOURCES = ('Technical(1).pdf#page=2', 'Technical(1).pdf#page=4',
           'ARTIN_SESSION_19_MACHINE_UNVERIFIED#3500-3525',
           'ARTIN_SESSION_19_MACHINE_UNVERIFIED#4273-4299')


@dataclass(frozen=True)
class PivotCandidate:
    kind: str
    level: Decimal
    opened_at: int
    confirmed_at: int


class LastLegObserver:
    """Read closed M15 bars in time order; reset on any missing time-grid slot."""
    def __init__(self, interval_seconds=900):
        if type(interval_seconds) is not int or interval_seconds <= 0:
            raise ValueError('INVALID_INTERVAL')
        self.interval = interval_seconds
        self.recent = deque(maxlen=3)
        self.pivots = []
        self.last_time = None
        self.pivots_detected = 0
        self.gaps = 0
        self.ambiguous_centers = 0

    def step(self, bar):
        t = getattr(bar, 't', None)
        if type(t) is not int or t < 0:
            raise ValueError('INVALID_NATIVE_CANDLE_TIME')
        try:
            o,h,l,c = (Decimal(str(getattr(bar,key))) for key in ('open','high','low','close'))
        except (InvalidOperation,ValueError,TypeError,AttributeError):
            raise ValueError('INVALID_CANDLE_PRICE') from None
        if any(not p.is_finite() or p<=0 for p in (o,h,l,c)) or l>min(o,c) or h<max(o,c):
            raise ValueError('INVALID_CANDLE_OHLC')
        if self.last_time is not None and t<=self.last_time:
            raise ValueError('NON_MONOTONIC_NATIVE_CANDLES')
        gap = self.last_time is not None and t != self.last_time+self.interval
        if gap:
            self.recent.clear()
            self.pivots.clear()
            self.gaps+=1
        self.last_time=t
        self.recent.append({'t':t,'o':o,'h':h,'l':l,'c':c})
        known_at=t+self.interval
        if len(self.recent)==3:
            a,b,d=self.recent
            hi=(b['h']>a['h'] and b['h']>d['h'])
            lo=(b['l']<a['l'] and b['l']<d['l'])
            if hi and lo:
                # Wide engulfing bar can be a high AND a low; selecting either
                # silently would make the last-leg direction arbitrary.
                self.ambiguous_centers+=1
            elif hi or lo:
                pivot=PivotCandidate('HIGH' if hi else 'LOW',b['h'] if hi else b['l'],b['t'],known_at)
                self.pivots.append(pivot)
                self.pivots_detected+=1
        result={'schema':'artin_teacher_candidate_last_leg_v1',
                'known_at_native':known_at,'latest_closed_bar_open_native':t,
                'gap_reset':gap,'sources':SOURCES,
                'price_geometry_only':True,
                'teacher_last_leg_selected':False,
                'teacher_half_leg_verified':False,
                'trade_authorized':False,
                'pivots_detected':self.pivots_detected,
                'ambiguous_pivot_centers':self.ambiguous_centers,
                'gaps_reset':self.gaps,
                'status':'NO_COMPLETED_ALTERNATING_PIVOT_PAIR',
                'candidate_leg':None,'third_candle_half_comparison':None}
        if len(self.pivots)<2:
            return result
        a,b=self.pivots[-2:]
        if a.kind==b.kind:
            result['status']='TWO_LAST_PIVOTS_SAME_KIND_NOT_A_SELECTED_LEG'
            return result
        lo=min(a.level,b.level);hi=max(a.level,b.level)
        if lo==hi:
            result['status']='ZERO_RANGE_PIVOT_PAIR'
            return result
        midpoint=(hi+lo)/Decimal(2)
        direction=('UP' if a.kind=='LOW' and b.kind=='HIGH' else
                   'DOWN' if a.kind=='HIGH' and b.kind=='LOW' else None)
        if direction is None: raise RuntimeError('UNEXPECTED_PIVOT_KIND')
        leg={'begin_pivot_kind':a.kind,'begin_pivot_open_native':a.opened_at,
             'begin_pivot_confirmed_native':a.confirmed_at,'begin_price':str(a.level),
             'end_pivot_kind':b.kind,'end_pivot_open_native':b.opened_at,
             'end_pivot_confirmed_native':b.confirmed_at,'end_price':str(b.level),
             'direction_candidate':direction,'low':str(lo),'high':str(hi),
             'midpoint':str(midpoint), 'teacher_selection_verified':False}
        result.update(status='LAST_OPPOSITE_PIVOT_PAIR_CANDIDATE_ONLY',candidate_leg=leg)
        if (len(self.recent)==3 and self.recent[0]['t']>=b.confirmed_at
            and all(y['t']-x['t']==self.interval for x,y in zip(self.recent,list(self.recent)[1:]))):
            closes=[q['c'] for q in self.recent]
            compared={'open_times_native':[q['t'] for q in self.recent],
                      'three_closes_all_below_candidate_half':all(x<midpoint for x in closes),
                      'three_closes_all_above_candidate_half':all(x>midpoint for x in closes),
                      'three_closes_all_inside_candidate_range':all(lo<=x<=hi for x in closes),
                      'third_close':str(closes[-1]),
                      'exact_half':str(midpoint),
                      'teacher_sentiment_verified':False,
                      'teacher_leg_choice_verified':False,
                      'teacher_three_sequence_approved':False}
            result['third_candle_half_comparison']=compared
            result['status']='THREE_CLOSES_COMPARED_TO_CANDIDATE_HALF_NOT_TEACHER_APPROVED'
        witness=json.dumps({'leg':leg,'comparison':result['third_candle_half_comparison']},
                            ensure_ascii=True,sort_keys=True,separators=(',',':'))
        result['observation_sha256']=hashlib.sha256(witness.encode()).hexdigest()
        return result


def observe_last_leg(bars, *, interval_seconds=900):
    if not isinstance(bars,(list,tuple)) or not bars:
        raise ValueError('CLOSED_BARS_REQUIRED')
    machine=LastLegObserver(interval_seconds)
    report=None
    for bar in bars:
        report=machine.step(bar)
    return report