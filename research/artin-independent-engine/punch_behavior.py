"""Role-specific raw Doji observations and source-bounded confirmation region.

The pause is CURRENT for AHEAD, PREVIOUS for TIED and OPPOSITE confirmation. Region
bounds are sourced geometry, not an invented ATR/distance tolerance. The module
does not infer a strong run, choose the region, or equate count with dollar PnL.
S21:3984..4086,4201..4223. Drawn examples are not market OHLC/fills.
"""
from decimal import Decimal
from entry_engine import Fact
from raw_geometry import geometry

def derive(rule,side,window,facts,raw_source=None):
    out={};current=window[-1];at=current.closed_at
    def emit(k,value,known,source):out[k]=Fact(value,known,source)
    def number(f):
        if type(f.value) not in (str,int,Decimal):raise ValueError('exact region price required')
        n=Decimal(f.value)
        if not n.is_finite() or n<=0:raise ValueError('positive finite region price required')
        return n
    c,w=facts.get('day_correct_count'),facts.get('day_incorrect_count')
    if c is not None and w is not None:
        if type(c.value) is not int or type(w.value) is not int or min(c.value,w.value)<0:
            raise ValueError('analysis counts must be explicit nonnegative integers')
        if max(c.known_at,w.known_at)<=at:
            state='START_OF_DAY' if c.value==w.value==0 else 'AHEAD_BY_COUNT' if c.value>w.value else 'BEHIND_BY_COUNT' if c.value<w.value else 'TIED_BY_COUNT'
            emit('day_analysis_state',state,max(c.known_at,w.known_at),c.source+'|'+w.source+':S21_COUNT_NOT_MONEY')
    if rule=='STOPPUNCH_OPPOSITE_CONFIRMATION':
        if side!='BUY' or len(window)<2:return out
        pause=window[-2]
        if pause.closed_at!=current.opened_at:return out
        # S21:4096..4137 draws a red pause with an upper wick, followed by a
        # close above that wick. This is not the S22 same-colour hypothesis.
        # A pause's semantic role is not equivalent to one-candle doubt_shape.
        source='RAW_S21_OPPOSITE_PAUSE:'+str(pause.opened_at)+':CONFIRMATION:'+str(current.opened_at)
        source+='|RAW_SOURCE:'+('UNDECLARED' if raw_source is None else raw_source)
        emit('opposite_colour_pause',pause.close<pause.open,pause.closed_at,source)
        emit('pause_candle_opened_at',pause.opened_at,pause.closed_at,source)
        emit('following_confirmation_closed',True,at,source)
        emit('confirmation_timely',True,at,source+':IMMEDIATE_NEXT_CANDLE_SUBSET')
        emit('confirmation_close',current.close,at,source)
        emit('teacher_confirmation_reference',pause.high,pause.closed_at,source+':S21_UPPER_WICK_REFERENCE')
        run,anchor=facts.get('strong_run_in_sentiment_direction'),facts.get('punch_run_end_opened_at')
        emit('punch_role_chain_status','MISSING_SOURCED_RUN_OR_END_ANCHOR',at,source)
        if len(window)>=3 and run is not None and anchor is not None:
            last_run_bar=window[-3]
            emit('punch_role_chain_status','RUN_ROLE_NOT_CAUSAL_OR_ALIGNED',at,source)
            if (run.value is True and type(anchor.value) is int and anchor.value==last_run_bar.opened_at
                and last_run_bar.closed_at==pause.opened_at and last_run_bar.close>last_run_bar.open
                and pause.close<pause.open
                and last_run_bar.closed_at<=run.known_at<=pause.opened_at
                and last_run_bar.closed_at<=anchor.known_at<=pause.opened_at):
                parents=source+'|'+run.source+'|'+anchor.source+':SOURCED_RUN_AND_RAW_FRESH_ROLE_CHAIN'
                emit('current_setup',True,at,parents)
                emit('complete_punch_sequence',True,at,parents)
                emit('punch_role_chain_status','FRESH_SOURCE_RUN_AND_RAW_ROLES',at,parents)
        low,high=facts.get('confirmation_region_low'),facts.get('confirmation_region_high')
        if low is not None and high is not None and max(low.known_at,high.known_at)<=current.opened_at:
            lo,hi=number(low),number(high)
            if lo>hi:raise ValueError('region bounds reversed')
            emit('confirmation_near',lo<=current.close<=hi,at,low.source+'|'+high.source+':SOURCED_REGION')
        return out
    if rule=='STOPPUNCH_DOJI_AHEAD':
        if geometry(current).body==0:emit('doji_candle_closed',True,at,'RAW_CURRENT_DOJI:'+str(current.opened_at))
        return out
    if rule!='STOPPUNCH_DOJI_TIED' or len(window)<2:return out
    pause=window[-2]
    if pause.closed_at!=current.opened_at:return out
    assessed,anchor=facts.get('pause_doji_classified'),facts.get('pause_candle_opened_at')
    sourced_pause=(assessed is not None and anchor is not None and assessed.value is True
        and type(anchor.value) is int and anchor.value==pause.opened_at
        and max(assessed.known_at,anchor.known_at)<=pause.closed_at)
    if geometry(pause).body!=0 and not sourced_pause:return out
    source='RAW_PAUSE:'+str(pause.opened_at)+':CONFIRMATION:'+str(current.opened_at)+':S21_4037_4086'
    source+='|RAW_SOURCE:'+('UNDECLARED' if raw_source is None else raw_source)
    if geometry(pause).body!=0:
        source+=':SOURCED_PAUSE_CLASSIFICATION:'+assessed.source+'|'+anchor.source
    emit('doji_confirmed',True,pause.closed_at,source)
    emit('pause_candle_opened_at',pause.opened_at,pause.closed_at,source)
    emit('doji_shadow_high',pause.high,pause.closed_at,source)
    emit('following_confirmation_closed',True,at,source)
    emit('confirmation_timely',True,at,source+':IMMEDIATE_NEXT_CANDLE_SUBSET')
    emit('confirmation_close',current.close,at,source)
    # BUY mapping has direct reviewed examples; SELL geometric comparison is not
    # silently promoted to the unestablished complete sell StopPunch branch.
    low,high=facts.get('confirmation_region_low'),facts.get('confirmation_region_high')
    if low is not None and high is not None and max(low.known_at,high.known_at)<=current.opened_at:
        lo,hi=number(low),number(high)
        if lo>hi:raise ValueError('region bounds reversed')
        emit('confirmation_near',lo<=current.close<=hi,at,low.source+'|'+high.source+':EXPLICIT_REGION_NO_NUMERIC_TOLERANCE')
    zl,zh=facts.get('zone_low'),facts.get('zone_high')
    if zl is not None and zh is not None and max(zl.known_at,zh.known_at)<=pause.opened_at:
        lo,hi=number(zl),number(zh)
        if lo>hi:raise ValueError('invalid zone geometry')
        overlap=pause.high>=lo and pause.low<=hi
        emit('pause_zone_overlap_measured',overlap,pause.closed_at,zl.source+'|'+zh.source+':RAW_OVERLAP_NOT_ZONE_VALIDATION')
        valid=facts.get('reference_zone_validated')
        if valid is not None and valid.value is True and valid.known_at<=pause.opened_at:
            emit('zone_context',overlap,pause.closed_at,valid.source+'|'+source+':SOURCED_VALID_ZONE_AND_RAW_PAUSE_OVERLAP')
    return out
