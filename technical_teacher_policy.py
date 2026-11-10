"""Strict Technical(1).pdf pp.13--17 handout adapter for the existing Artin paper motor.

The handout describes entry families (reverse/break), structural stops and
TP = SL distance * RR. It DOES NOT define an automatable strength threshold,
PRZ selection algorithm, pivot window, numeric stop offset or exact spread
model. None are invented here. All chart facts must come from a separate,
source-linked chart observation verified by the caller; this module cannot
certify the teacher's video semantics by itself. No orders or broker APIs.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Mapping

TECH_PDF = 'Technical(1).pdf'
STOP_ANCHORS = frozenset({'PIVOT', 'ORDER_BLOCK', 'VOLUME_PROFILE', 'FVG',
                           'GOLDEN_ZONE', 'TREND', 'CANDLE_WICK'})
PRZ_CONTEXTS = frozenset({'TREND', 'ORDER_BLOCK', 'FVG'})


def _dec(value, label):
    if type(value) not in (str, int, Decimal):
        raise ValueError('EXACT_DECIMAL_REQUIRED:' + label)
    try: v = Decimal(str(value))
    except (InvalidOperation, ValueError): raise ValueError('INVALID_NUMBER:' + label) from None
    if not v.is_finite() or v <= 0:
        raise ValueError('POSITIVE_NUMBER_REQUIRED:' + label)
    return v


def _fact(evidence, name, decision_at, expected_type):
    """A strict, prior-known observation; a document page isn't a market feed."""
    x = evidence.get(name)
    if not isinstance(x, Mapping): return None, 'MISSING_SOURCED_CHART_FACT:'+name
    if (type(x.get('known_at')) is not int or x['known_at'] < 0 or
        x['known_at'] > decision_at):
        return None, 'FUTURE_OR_UNTIMED_CHART_FACT:'+name
    if (not isinstance(x.get('source'),str) or not x['source'].strip() or
        x['source'].startswith(('Technical(1).pdf', 'FXM.pdf', 'SYNTHETIC_'))):
        return None, 'CHART_SOURCE_REQUIRED:'+name
    value=x.get('value')
    if expected_type == 'bool' and type(value) is not bool:
        return None, 'BOOLEAN_CHART_FACT_REQUIRED:'+name
    if expected_type == 'str' and (not isinstance(value,str) or not value.strip()):
        return None, 'LABEL_CHART_FACT_REQUIRED:'+name
    if expected_type == 'number':
        try: value=_dec(value,name)
        except ValueError: return None, 'PRICE_CHART_FACT_REQUIRED:'+name
    return value, None


def apply_technical_handout(*, route, side, at, evidence, fxm_sizing, rr):
    """Return a *paper-only* decision (never order authorization).

    The prerequisite entry engine and FXM risk gates must both independently
    accept; therefore this function cannot turn a rejected source scene into
    an entry. Every price/structure fact must carry a source and known_at.
    """
    def reject(reason, **extra):
        return {'status':reason,'sources':['Technical(1).pdf#page=13',
                'Technical(1).pdf#page=17'], 'orders_enabled':False,**extra}
    if side not in ('BUY','SELL') or type(at) is not int or at<0:
        return reject('INVALID_SIDE_OR_TIME')
    if not isinstance(fxm_sizing, Mapping) or fxm_sizing.get('status')!='PAPER_SIZED_ONLY':
        return reject('WAIT_PREVIOUS_ENGINE_OR_FXM_RISK_GATES')
    if route.startswith('REVERSAL_'):
        family='REVERSAL'
    elif route.startswith('BREAK_'):
        family='BREAK'
    else:
        # Technical p13 names only two entry families. Pullback/StopPunch
        # variants must be justified separately by original lesson audio/video.
        return reject('WAIT_SOURCE_MAPPING_FOR_THIS_ENTRY_FAMILY')
    if not isinstance(evidence, Mapping):
        return reject('WAIT_TEACHER_CHART_EVIDENCE')
    kind,error=_fact(evidence,'entry_family',at,'str')
    if error:return reject(error)
    if kind!=family:return reject('ENTRY_FAMILY_MISMATCH')
    identified,error=_fact(evidence,'teacher_scene_meaning_confirmed',at,'bool')
    if error:return reject(error)
    if not identified:return reject('WAIT_TEACHER_SCENE_CONFIRMATION')
    if family=='REVERSAL':
        prz,error=_fact(evidence,'prz_context',at,'str')
        if error:return reject(error)
        if prz not in PRZ_CONTEXTS:return reject('UNLISTED_PRZ_CONTEXT')
        prz_valid,error=_fact(evidence,'prz_teacher_confirmed',at,'bool')
        if error:return reject(error)
        if not prz_valid:return reject('WAIT_TEACHER_PRZ_CONFIRMATION')
    else:
        line,error=_fact(evidence,'break_line_price',at,'number')
        if error:return reject(error)
        confirmed,error=_fact(evidence,'break_teacher_confirmed',at,'bool')
        if error:return reject(error)
        if not confirmed:return reject('WAIT_TEACHER_BREAK_CONFIRMATION')
        # A bullish/bearish close relative to a sourced line is an observable
        # sanity check, not an invented definition of candle strength.
        close,error=_fact(evidence,'decision_close',at,'number')
        if error:return reject(error)
        if not(close > line if side=='BUY' else close < line):
            return reject('CLOSE_NOT_BEYOND_TEACHER_BREAK_LINE')
    anchor,error=_fact(evidence,'stop_anchor_kind',at,'str')
    if error:return reject(error)
    if anchor not in STOP_ANCHORS:return reject('STOP_ANCHOR_NOT_FROM_TECHNICAL_PAGE17')
    stop_price,error=_fact(evidence,'structural_stop_price',at,'number')
    if error:return reject(error)
    entry_price,error=_fact(evidence,'entry_price',at,'number')
    if error:return reject(error)
    sign=Decimal(1) if side=='BUY' else Decimal(-1)
    distance=sign*(entry_price-stop_price)
    if distance<=0:return reject('STOP_NOT_ON_LOSS_SIDE')
    # The FXM risk-gate must be sized for EXACTLY the same prices; a conflicting
    # caller may not substitute a new SL after sizing.
    try:
        if (_dec(fxm_sizing['entry'],'fxm_entry')!=entry_price or
            _dec(fxm_sizing['structural_stop_unchanged'],'fxm_stop')!=stop_price):
            return reject('STOP_ENTRY_NOT_IDENTICAL_TO_FXM_RISK_PLAN')
    except (KeyError,ValueError):
        return reject('INVALID_FXM_RISK_PLAN')
    if not isinstance(rr,Mapping) or rr.get('status')!='RR_CANDIDATE_FROM_HANDOUT':
        return reject('WAIT_SOURCED_FXM_RR')
    try: risk_reward=_dec(rr['rr'],'rr')
    except (KeyError,ValueError):return reject('INVALID_FXM_RR')
    target=entry_price+sign*distance*risk_reward
    return {'status':'PAPER_TECHNICAL_FXM_CONDITIONS_SATISFIED',
            'side':side,'entry_family':family,'route':route,
            'entry':str(entry_price),'stop':str(stop_price),
            'stop_anchor_kind':anchor,'risk_price_distance':str(distance),
            'rr':str(risk_reward),'target':str(target),
            'lots':fxm_sizing['lots'],
            'sources':['Technical(1).pdf#page=13',
                       'Technical(1).pdf#page=14' if family=='BREAK' else 'Technical(1).pdf#page=13',
                       'Technical(1).pdf#page=17','FXM.pdf#page=2','FXM.pdf#page=4'],
            'chart_source_fields':{k: x['source'] for k,x in evidence.items()
                                   if isinstance(x,Mapping) and 'source' in x},
            'teacher_video_independently_certified_by_this_module':False,
            'real_broker_fill_confirmed':False,'orders_enabled':False}