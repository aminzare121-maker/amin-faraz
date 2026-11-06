"""S22 SELL source-case hypotheses: selected run -> doubt pause -> next close.

The selected teacher variant and a prior break/run remain explicit sourced
inputs. We do not infer variant choice from colour or zone overlap. S21's
same-colour own-close example is retained separately. This is not a universal
pivot/strong-run classifier. Exact unambiguous doubt geometry is a subset;
other pause shapes or later confirmations are unresolved, not teacher vetoes.
The operand is NOT established as a universal teacher formula. A predeclared
body/wick hypothesis is required; missing selection produces no reference.
"""
from entry_engine import Fact
from teacher_features import candle_predicates

ROLE_KEYS=('break_before_pause','pause_doubt_confirmed','pause_in_run_direction',
    'confirmation_in_run_direction','following_confirmation_closed','confirmation_timely',
    'confirmation_close','teacher_confirmation_reference','pause_opened_at','pause_closed_at',
    'confirmation_opened_at','confirmation_closed_at','pause_body_close','pause_wick_low')

def derive(side,window,facts,raw_source=None):
    if side!='SELL' or len(window)<2:return {}
    pause,current=window[-2:]
    if pause.closed_at!=current.opened_at:return {}
    variant=facts.get('teacher_model_variant');anchor=facts.get('run_break_closed_at')
    run=facts.get('strong_run_in_sentiment_direction')
    if variant is None or variant.value!='S22_AFTER_BREAK_CONFIRMED_PAUSE':return {}
    if anchor is None or run is None or run.value is not True:return {}
    if type(anchor.value) is not int or anchor.value<0:raise ValueError('exact break completion time required')
    if anchor.known_at<anchor.value:return {}
    if not max(anchor.known_at,run.known_at,variant.known_at)<=pause.opened_at:return {}
    if anchor.value>pause.opened_at:return {}
    if candle_predicates(pause)['doubt_shape'].value is not True:return {}
    source='S22_SOURCE_CASE_RAW_PAUSE:'+str(pause.opened_at)+':CONFIRMATION:'+str(current.opened_at)
    source+='|RAW_SOURCE:'+('UNDECLARED' if raw_source is None else raw_source)
    source+='|'+anchor.source+'|'+run.source+'|'+variant.source
    out={k:Fact(v,known,source) for k,v,known in (
        ('pause_opened_at',pause.opened_at,pause.closed_at),('pause_closed_at',pause.closed_at,pause.closed_at),
        ('confirmation_opened_at',current.opened_at,current.closed_at),('confirmation_closed_at',current.closed_at,current.closed_at),
        ('pause_body_close',pause.close,pause.closed_at),('pause_wick_low',pause.low,pause.closed_at),
        ('break_before_pause',True,pause.closed_at),('pause_doubt_confirmed',True,pause.closed_at),
        ('pause_in_run_direction',pause.close<pause.open,pause.closed_at),
        ('confirmation_in_run_direction',current.close<current.open,current.closed_at),
        ('following_confirmation_closed',True,current.closed_at),
        ('confirmation_timely',True,current.closed_at),
        ('confirmation_close',current.close,current.closed_at))}
    operand=facts.get('confirmation_reference_kind')
    if operand is not None and operand.known_at<=pause.opened_at:
        if operand.value=='PAUSE_BODY_CLOSE_HYPOTHESIS':value=pause.close
        elif operand.value=='PAUSE_WICK_LOW_HYPOTHESIS':value=pause.low
        else:return out
        out['teacher_confirmation_reference']=Fact(value,pause.closed_at,source+':EXPLICIT_UNVERIFIED_OPERAND:'+operand.value)
    return out
