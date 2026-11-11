"""Source-bounded S19 three-candle observations from CLOSED M15 bars.

Observed geometry is not teacher-approved pivot selection, last-leg choice,
economic sentiment or trade permission. Source: S19 3440.62-3654.3;
Technical(1).pdf pp.2,13.  No order/broker API and no thresholds.
"""
from __future__ import annotations
from decimal import Decimal
from hashlib import sha256
import json

TEACHER_REFS = (
    {'type':'MACHINE_SPEECH_UNVERIFIED','session':19,'seconds':[3440.62,3473.2],
     'statement':'three candles and entry evaluated at the third close'},
    {'type':'MACHINE_SPEECH_UNVERIFIED','session':19,'seconds':[3500.82,3523.7],
     'statement':'one sentiment-aligned candle must be doubt; sequence below half last leg'},
    {'type':'MACHINE_SPEECH_UNVERIFIED','session':19,'seconds':[3646.0,3654.3],
     'statement':'three-candle sequence requires a pivot'},
    {'type':'PDF_TEACHER_NOTE','name':'Technical(1).pdf','pages':[2,13]},
)


def _shape(bar):
    o,h,l,c=(Decimal(str(getattr(bar,k))) for k in ('open','high','low','close'))
    if min(o,h,l,c)<=0 or l>min(o,c) or h<max(o,c):
        raise ValueError('INVALID_TEACHER_BAR_OHLC')
    body=abs(c-o);upper=h-max(o,c);lower=min(o,c)-l
    maximum=max(upper,lower);total=upper+lower
    # Exactly the intersection of the two unambiguous readings in the
    # original S13 candle predicate. No ATR/pip/epsilon tolerance.
    doubt=True if maximum>body else False if total<=body else None
    confidence=True if body>total else False if body<=maximum else None
    color='BUY' if c>o else 'SELL' if c<o else 'FLAT'
    return {'doubt':doubt,'confidence':confidence,'color':color,
            'body':str(body),'upper_shadow':str(upper),'lower_shadow':str(lower)}


def observe_s19_three(bars, *, interval_seconds=900):
    """Measure latest 3 closed candles; no sent/last-leg inference.

    Explicitly uses a 3-bar strict extremum as a *candidate* pivot shape;
    teacher-confirmed major/minor pivot or relevant last leg is NOT inferred.
    """
    if type(interval_seconds) is not int or interval_seconds<=0:
        raise ValueError('INVALID_DECLARED_INTERVAL')
    if not isinstance(bars,(tuple,list)) or len(bars)<3:
        return {'status':'INSUFFICIENT_CLOSED_CANDLES','trade_authorized':False}
    window=bars[-3:]
    times=[]
    for b in window:
        t=getattr(b,'t',None)
        if type(t) is not int or t<0:raise ValueError('INVALID_OPEN_TIME')
        times.append(t)
    if not(times[0]<times[1]<times[2]):raise ValueError('NON_CAUSAL_SEQUENCE')
    if any(b-a!=interval_seconds for a,b in zip(times,times[1:])):
        return {'status':'GAPPED_THREE_CANDLE_WINDOW','open_times':times,'trade_authorized':False}
    a,b,c=window
    shapes=[_shape(q) for q in window]
    lows=[Decimal(str(q.low)) for q in window]
    highs=[Decimal(str(q.high)) for q in window]
    # The strictly local extremum is a measurable price-shape candidate. Its
    # selection as the *teacher's* pivot cannot be certified from 3 OHLC bars.
    pivot_buy=lows[1]<lows[0] and lows[1]<lows[2]
    pivot_sell=highs[1]>highs[0] and highs[1]>highs[2]
    sides={}
    for side,shape_pivot in (('BUY',pivot_buy),('SELL',pivot_sell)):
        aligned=[(idx,s) for idx,s in enumerate(shapes) if s['color']==side]
        doubt_values=[s['doubt'] for _,s in aligned]
        conditional_doubt=True if True in doubt_values else (False if not doubt_values or all(v is False for v in doubt_values) else None)
        sides[side]={
            'conditional_one_doubt_in_side_candles':conditional_doubt,
            'sentiment_direction_independently_known':False,
            'sentiment_aligned_doubt_proven':False,
            'aligned_candle_open_times':[times[idx] for idx,_ in aligned],
            'strict_middle_extremum_pivot_candidate':bool(shape_pivot),
            'teacher_pivot_selected_or_confirmed':False,
            'confidence_shape_exists':any(s['confidence'] is True for s in shapes),
            'last_leg_selected_from_teacher_context':False,
            'half_last_leg_condition_verified':False,
            'third_candle_close':str(c.close),
            'entry_price_classification':'THIRD_CLOSE_GEOMETRY_ONLY_NOT_TRADE_AUTHORIZED',
            'entry_approved':False,
        }
    witness=json.dumps({'times':times,'shapes':shapes,'sides':sides},sort_keys=True,ensure_ascii=True,separators=(',',':'))
    return {'schema':'artin_s19_closed_three_candle_geometry_v1',
            'status':'MEASURABLE_SHAPE_NOT_TEACHER_TRADE',
            'third_close_known_at':times[-1]+interval_seconds,
            'open_times':times,'shapes':shapes,'by_side':sides,
            'teacher_references':TEACHER_REFS,
            'observation_sha256':sha256(witness.encode()).hexdigest(),
            'trade_authorized':False}