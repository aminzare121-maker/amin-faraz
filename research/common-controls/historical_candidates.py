"""Causal adapter to existing six candidates; no runtime/broker imports.
Uses original entry rules and stop. Fixed lots, target and horizon are explicitly
the historical diagnostic overlay, not the installed adaptive risk/exit policy.
"""
import os,sys
from pathlib import Path
if not os.environ.get('FARAZ_STRATEGY_SOURCE'):raise ValueError('LOCAL_STRATEGY_SOURCE_REQUIRED')
SOURCE=Path(os.environ['FARAZ_STRATEGY_SOURCE']).resolve()
if not (SOURCE/'amin_mt5/strategy.py').is_file():raise ValueError('LOCAL_STRATEGY_SOURCE_MISSING')
if str(SOURCE) not in sys.path:sys.path.insert(0,str(SOURCE))
from amin_mt5.strategy import candidates,plan

def closed_input(history):
    if not history:return [],None
    asof=history[-1]['time']+900
    bars=[dict(b,final=True,observed_at=b['time']+900,time_basis='conditional-UTC') for b in history]
    if any(b['observed_at']>asof for b in bars):raise ValueError('LOOKAHEAD_HISTORY')
    return bars,asof

def adapter(candidate):
    candidate.validate()
    def signal(history):
        bars,asof=closed_input(history)
        if not bars:return None
        result=plan(bars,asof,candidate)
        if result is not None and result['signal_time']+900>asof:raise ValueError('LOOKAHEAD_SIGNAL')
        return result
    return signal

def methods():return {c.id:adapter(c) for c in candidates()}
