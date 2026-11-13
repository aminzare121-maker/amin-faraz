"""Source-anchored Artin classroom entry/stop-management replay.

This module is part of the classroom trading MOTOR, not an ASR pipeline.
It executes decisions for cited teacher-scene events without inventing
chart levels, market fills, broker orders, or teacher certainty from ASR.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


class TeacherActionError(ValueError):
    pass


def money(value, label):
    if type(value) not in (str, int):
        raise TeacherActionError('EXACT_DECIMAL_REQUIRED:'+label)
    try:
        number=Decimal(value)
    except (InvalidOperation, ValueError):
        raise TeacherActionError('INVALID_DECIMAL:'+label) from None
    if not number.is_finite() or number <= 0:
        raise TeacherActionError('POSITIVE_DECIMAL_REQUIRED:'+label)
    return number


def normalize(text):
    return str(text).replace('ي','ی').replace('ك','ک').replace('\u200c',' ').replace('ۀ','ه')


def source_index(folder, sessions):
    """Index immutable original machine transcript rows by exact segment id."""
    root=Path(folder)
    index={}
    digests={}
    for session in sorted(set(sessions)):
        if type(session) is not int or not 1 <= session <= 25:
            raise TeacherActionError('INVALID_CLASS_SESSION')
        path=root/f'session_{session:02d}_all_machine_speech_review.jsonl'
        raw=path.read_bytes()
        digests[str(session)]=hashlib.sha256(raw).hexdigest()
        for line in raw.splitlines():
            if not line.strip(): continue
            row=json.loads(line)
            ident=row.get('source_segment_id')
            if row.get('session') != session or not isinstance(ident,str) or not ident:
                raise TeacherActionError('SOURCE_ROW_IDENTITY_MISMATCH')
            if ident in index and index[ident] != row:
                raise TeacherActionError('SOURCE_SEGMENT_ID_CONFLICT')
            index[ident]=row
    return index,digests


def _evidence(event, index):
    ids=event.get('source_segment_ids')
    session=event.get('session')
    if type(session) is not int or not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
        raise TeacherActionError('SOURCE_IDS_REQUIRED')
    try: rows=[index[i] for i in ids]
    except (KeyError, TypeError): raise TeacherActionError('SOURCE_SEGMENT_MISSING') from None
    if any(r['session']!=session for r in rows):
        raise TeacherActionError('CROSS_SESSION_SOURCE_MISMATCH')
    ordered=sorted(rows,key=lambda x:x['start_seconds'])
    if ordered!=rows:raise TeacherActionError('CLASS_EVENT_SOURCE_OUT_OF_ORDER')
    return ordered,normalize(' '.join(x['machine_text_unverified'] for x in rows))


def _decision(event, text):
    kind=event['kind']
    if kind=='NO_ENTRY':
        if not re.search(r'ورود\s+نمی\s*کن|ورود\s+نکرد',text):
            raise TeacherActionError('NO_ENTRY_WORDS_NOT_PRESENT_IN_SOURCE')
        return {'decision':'NO_TRADE_IN_CITED_CLASS_SCENE','order_created':False}
    if kind=='ENTRY_AFTER_CONFIRMATION':
        if not ('کلوز' in text and re.search(r'تایید|تأیید|تعیید',text)
                and re.search(r'ورود\s*می\s*کن',text)):
            raise TeacherActionError('CONFIRMATION_ENTRY_WORDS_NOT_PRESENT')
        chart=event.get('chart')
        if not isinstance(chart,dict) or chart.get('closed') is not True:
            return {'decision':'WAIT_FOR_CONFIRMATION_CLOSE','order_created':False}
        if (not isinstance(chart.get('source_frame_sha256'),str)
            or not re.fullmatch(r'[0-9a-f]{64}',chart['source_frame_sha256'])
            or chart.get('source_verified') is not True):
            return {'decision':'WAIT_FOR_CHART_REFERENCE','order_created':False}
        # The utterance alone does not define which price/location/direction
        # was meant. Do not transform a matched sentence into an actual order.
        return {'decision':'CLASSROOM_CONFIRMATION_OBSERVED_ENTRY_REVIEW',
                'order_created':False,'teacher_price_level_assumed':False}
    raise TeacherActionError('NOT_AN_ENTRY_DECISION')



def _three_candle_close_entry(event, text):
    """Reversal-three class: 3 consecutive M15 closes; entry timing is bar 3.

    Instructor's pivot, half-leg location and doubt-candle recognition are
    required as prior-known chart observations, never guessed by indicators.
    This is an executable conditional decision, not an MT5 trade permission.
    """
    if not (('سه تا کندل' in text or 'ستا کندل' in text)
            and ('یک دوم' in text or 'نصف' in text)
            and 'شک' in text and 'کلوز کندل' in text
            and ('جهت سنتیمنت' in text or 'جهت سنتمینت' in text)
            and 'یکی' in text):
        raise TeacherActionError('THREE_CANDLE_TEACHER_WORDS_NOT_PRESENT')
    side=event.get('side')
    if side not in ('BUY','SELL'):raise TeacherActionError('THREE_CANDLE_SIDE_REQUIRED')
    observations=event.get('candles')
    if observations is None:
        return {'decision':'WAIT_FOR_THREE_M15_CANDLES','order_created':False}
    if not isinstance(observations,list) or len(observations)!=3:
        raise TeacherActionError('EXACTLY_THREE_M15_BARS_REQUIRED')
    times=[];direction=[]
    for candle in observations:
        if not isinstance(candle,dict) or type(candle.get('time')) is not int or candle['time']<=0:
            raise TeacherActionError('M15_NATIVE_BAR_TIME_REQUIRED')
        t=candle['time'];times.append(t)
        o=money(candle.get('open'),'bar_open');h=money(candle.get('high'),'bar_high')
        l=money(candle.get('low'),'bar_low');c=money(candle.get('close'),'bar_close')
        if not l<=min(o,c)<=max(o,c)<=h:
            raise TeacherActionError('INVALID_THREE_CANDLE_OHLC')
        if not isinstance(candle.get('source'),str) or not candle['source'].strip():
            raise TeacherActionError('UNSOURCED_M15_CANDLE')
        direction.append('BUY' if c>o else 'SELL' if c<o else 'FLAT')
    if times[1]-times[0]!=900 or times[2]-times[1]!=900:
        return {'decision':'REJECT_THREE_CANDLE_SEQUENCE_GAP','order_created':False}
    at=event.get('decision_at')
    if type(at) is not int or at<times[0]:
        raise TeacherActionError('INVALID_THREE_CANDLE_DECISION_TIME')
    if at<times[2]+900:
        return {'decision':'WAIT_FOR_THIRD_CANDLE_CLOSE','order_created':False,
                'earliest_decision_at':times[2]+900}
    if at!=times[2]+900:
        # Teacher points specifically to the third close, not a late signal.
        return {'decision':'REJECT_NOT_AT_THIRD_CANDLE_CLOSE','order_created':False}
    # Lesson 19, 3509.96-3519.68: AT LEAST ONE of the three bars that
    # points with sentiment must be the doubt bar. The older shortcut that
    # ALL THREE bars must point with sentiment contradicts this wording.
    # The doubt candle's index is supplied from the classroom chart; choosing
    # it based on hindsight or arbitrary candle geometry is prohibited.
    if side not in direction:
        return {'decision':'REJECT_NO_CANDLE_IN_SENTIMENT_DIRECTION',
                'order_created':False,'observed_directions':direction}
    chart=event.get('teacher_chart_facts')
    required=('pivot_confirmed','half_leg_location_confirmed',
              'doubt_candle_present','sentiment_permitted','doubt_candle_index')
    if not isinstance(chart,dict) or any(k not in chart for k in required):
        return {'decision':'WAIT_FOR_CLASS_CHART_CONTEXT','order_created':False,
                'missing_facts':[k for k in required if not isinstance(chart,dict) or k not in chart]}
    for name in required:
        fact=chart[name]
        if not isinstance(fact,dict) or type(fact.get('known_at')) is not int or (
                not isinstance(fact.get('source'),str) or not fact['source'].strip()
                or fact['known_at']>at):
            return {'decision':'WAIT_FOR_PRIOR_KNOWN_CLASS_FACTS',
                    'order_created':False,'invalid_fact':name}
        if name=='doubt_candle_index':
            # 0/1/2 is a source-anchored *position*, not a new indicator.
            if type(fact.get('value')) is not int or not 0<=fact['value']<=2:
                return {'decision':'WAIT_FOR_PRIOR_KNOWN_CLASS_FACTS',
                        'order_created':False,'invalid_fact':name}
            if direction[fact['value']]!=side:
                return {'decision':'REJECT_TEACHER_DOUBT_CANDLE_OPPOSES_SENTIMENT',
                        'order_created':False,'doubt_bar_index':fact['value'],
                        'observed_directions':direction}
        elif type(fact.get('value')) is not bool:
            return {'decision':'WAIT_FOR_PRIOR_KNOWN_CLASS_FACTS',
                    'order_created':False,'invalid_fact':name}
        elif not fact['value']:
            return {'decision':'REJECT_TEACHER_THREE_CANDLE_CONDITION_FALSE',
                    'order_created':False,'failed_fact':name}
    return {'decision':'CLASSROOM_THIRD_CLOSE_SETUP_CANDIDATE',
            'order_created':False,'trade_authorized':False,
            'route':'REVERSAL_THREE','side':side,'bar_3_close_time':at,
            'doubt_candle_index':chart['doubt_candle_index']['value'],
            'observed_bar_directions':direction,
            'teacher_chart_observations_externally_supplied':True,
            'teacher_chart_meaning_independently_verified':False}

def _riskfree(event, text):
    if 'استاپ' not in text or 'نقطه' not in text or not re.search(r'بیار|بذار|بردار',text):
        raise TeacherActionError('RISKFREE_STOP_WORDS_NOT_PRESENT')
    trade=event.get('position')
    if not isinstance(trade,dict):raise TeacherActionError('EXPLICIT_POSITION_REQUIRED')
    side=trade.get('side')
    if side not in ('BUY','SELL'):raise TeacherActionError('INVALID_SIDE')
    entry=money(trade.get('entry'),'entry')
    old=money(trade.get('current_stop'),'current_stop')
    lots=money(trade.get('lots'),'lots')
    sign=Decimal(1) if side=='BUY' else Decimal(-1)
    if sign*(entry-old)<=0:
        raise TeacherActionError('STOP_ALREADY_AT_OR_BEYOND_ENTRY')
    if event.get('observed_management_trigger') is not True or not event.get('trigger_source'):
        return {'decision':'WAIT_FOR_SOURCED_RISKFREE_TRIGGER', 'order_created':False,
                'current_stop_unchanged':str(old),'position_lots_unchanged':str(lots)}
    # Session 25 describes moving SL to the entry while remaining in position;
    # NOT taking partial profit or closing the position. The exact entry price
    # is break-even GROSS only; commissions, spreads and gaps remain nonzero.
    return {'decision':'MOVE_STOP_TO_ENTRY_PAPER','order_created':False,
            'position_closed':False,'lots_before':str(lots),'lots_after':str(lots),
            'old_stop':str(old),'new_stop':str(entry),'gross_profit_realized':None,
            'net_break_even_guaranteed':False}


def _structural_stop(event, text):
    if 'استاپ' not in text or 'نزدیک' not in text or 'اشتباه' not in text:
        raise TeacherActionError('DO_NOT_COMPRESS_STOP_WORDS_NOT_PRESENT')
    from capital import Instrument,Costs,size_position
    trade=event.get('proposal')
    if not isinstance(trade,dict):raise TeacherActionError('SOURCED_TRADE_PROPOSAL_REQUIRED')
    side=trade.get('side')
    if side not in ('BUY','SELL'):raise TeacherActionError('INVALID_SIDE')
    entry=money(trade.get('entry'),'entry');stop=money(trade.get('structural_stop'),'structural_stop')
    risk=money(trade.get('risk_budget'),'risk_budget')
    instrument=Instrument(money(trade.get('money_per_price_unit_per_lot'),'multiplier'),
                          money(trade.get('min_lot'),'min_lot'),money(trade.get('lot_step'),'lot_step'))
    costs=Costs(Decimal(str(trade.get('round_trip_fee_per_lot','0'))),
                Decimal(str(trade.get('adverse_price_allowance','0'))))
    sized=size_position(side,entry,stop,risk,instrument,costs)
    result={'decision':'POSITION_SIZE_ACCEPT' if sized['status']=='ACCEPT' else 'NO_TRADE_RISK_OR_MIN_LOT',
            'structural_stop_unchanged':str(stop),'order_created':False,
            'sizing_result':sized['status'],'reason':sized.get('reason')}
    if sized['status']=='ACCEPT':result['lots']=str(sized['lots'])
    return result


def _sourced_stop_move(event, text):
    """Apply classroom risk-reduction / profit-protection to the pinned motor.

    The numeric position, trigger and costs are *explicit paper inputs*; they
    are not inferred from noisy ASR or fabricated historical fills. No orders.
    """
    kind=event['kind']
    halve=kind=='HALVE_RISK_STOP'
    if halve:
        # Session 24 expressly describes halving the initial nominal stop
        # distance while keeping the position open. Never invent a trigger.
        if not ('استاپ' in text and ('نصف' in text or 'یک دوم' in text)
                and 'ریسک' in text):
            raise TeacherActionError('HALVE_RISK_CLASS_WORDS_NOT_PRESENT')
        label='reduce'
    elif kind=='REDUCE_RISK_STOP':
        if not ('ریسک' in text and ('درصد' in text or 'استاپ' in text)
                and (re.search(r'نمی\s*بنده',text) or 'استاپ' in text)):
            raise TeacherActionError('REDUCE_RISK_CLASS_WORDS_NOT_PRESENT')
        label='reduce'
    elif kind=='SAVE_PROFIT_STOP':
        if not (re.search(r'سیو(?:ه)?\s*سود',text) and 'استاپ' in text):
            raise TeacherActionError('SAVE_PROFIT_CLASS_WORDS_NOT_PRESENT')
        label='saveprofit'
    else:
        raise TeacherActionError('UNSUPPORTED_STOP_MOVE_CLASS_KIND')
    trade=event.get('position')
    if not isinstance(trade,dict):
        raise TeacherActionError('EXPLICIT_POSITION_REQUIRED')
    side=trade.get('side')
    if side not in ('BUY','SELL'):
        raise TeacherActionError('INVALID_SIDE')
    # No hidden contract defaults. Prices/fees/volume must be supplied rather
    # than taken from the classroom speech or a presumed broker specification.
    required=('entry','initial_stop','current_stop','lots',
              'money_per_price_unit_per_lot','min_lot','lot_step',
              'round_trip_fee_per_lot','adverse_price_allowance')
    if any(k not in trade for k in required) or (not halve and 'new_stop' not in trade):
        raise TeacherActionError('EXPLICIT_STOP_CONTRACT_REQUIRED')
    from capital import Instrument,Costs,move_stop
    def decimal_nonnegative(v,name):
        if type(v) not in (str,int):raise TeacherActionError('EXACT_DECIMAL_REQUIRED:'+name)
        try: out=Decimal(v)
        except (InvalidOperation,ValueError):raise TeacherActionError('INVALID_DECIMAL:'+name) from None
        if not out.is_finite() or out<0:raise TeacherActionError('NONNEGATIVE_DECIMAL_REQUIRED:'+name)
        return out
    instrument=Instrument(*(money(trade[k],k) for k in
                            ('money_per_price_unit_per_lot','min_lot','lot_step')))
    costs=Costs(*(decimal_nonnegative(trade[k],k) for k in
                 ('round_trip_fee_per_lot','adverse_price_allowance')))
    position={k:money(trade[k],k) for k in ('entry','initial_stop','current_stop','lots')}
    if halve:
        side_sign=Decimal(1) if side=='BUY' else Decimal(-1)
        initial_distance=side_sign*(position['entry']-position['initial_stop'])
        if initial_distance<=0:raise TeacherActionError('INITIAL_STOP_WRONG_SIDE')
        half_stop=(position['entry']+position['initial_stop'])/2
        if side_sign*(half_stop-position['current_stop'])<=0:
            return {'decision':'ALREADY_HALF_RISK_OR_BETTER','label':'reduce',
                    'order_created':False,'position_closed':False,
                    'current_stop_unchanged':str(position['current_stop']),
                    'lots_unchanged':str(position['lots']),
                    'nominal_initial_stop_distance':str(initial_distance)}
        position['new_stop']=half_stop
    else:
        position['new_stop']=money(trade['new_stop'],'new_stop')
    if position['lots']<instrument.min_lot or position['lots']%instrument.lot_step:
        raise TeacherActionError('LOTS_NOT_ON_CONTRACT_GRID')
    if event.get('observed_management_trigger') is not True or not event.get('trigger_source'):
        return {'decision':'WAIT_FOR_CLASSROOM_TRIGGER','label':label,'order_created':False,
                'current_stop_unchanged':str(position['current_stop']),
                'position_lots_unchanged':str(position['lots'])}
    result=move_stop(label,side,position['entry'],position['initial_stop'],
                     position['current_stop'],position['new_stop'],position['lots'],instrument,costs)
    if result['status']!='ACCEPT':
        return {'decision':'REJECT_PAPER_STOP_MOVE','label':label,'reason':result['reason'],
                'order_created':False,'position_closed':False,
                'current_stop_unchanged':str(position['current_stop']),
                'lots_unchanged':str(position['lots'])}
    return {'decision':'PAPER_STOP_MOVE_ACCEPTED','label':label,
            'teacher_half_stop_distance_rule_applied':halve,
            'nominal_initial_stop_distance_reduction_fraction':'0.5' if halve else None,
            'order_created':False,'position_closed':False,
            'old_stop':str(position['current_stop']),'new_stop':str(result['stop']),
            'lots_before':str(position['lots']),'lots_after':str(result['lots']),
            'modeled_exit_net':str(result['modeled_exit_net']),
            'realized_pnl':None,'execution_guaranteed':False,
            'source_trigger_class':'PAPER_ASSUMPTION' if str(event['trigger_source']).startswith('SYNTHETIC_')
                                   else 'EXTERNAL_RECORDED_TRIGGER_NOT_INDEPENDENTLY_VERIFIED'}


def _stop_triggered_exit(event, text):
    """Replay the teacher's stated stop-trigger exit, not a broker fill.

    Source lesson 24: if price returns and touches the stop, the position
    closes through that stop. Intrabar path, slippage and actual fills are not
    supplied by spoken classroom words. Never manufacture a realized P&L.
    """
    if not ('استاپلاس' in text and ('بزنه' in text or 'بزند' in text)
            and ('می بنده' in text or 'میبنده' in text)):
        raise TeacherActionError('STOP_EXIT_CLASS_WORDS_NOT_PRESENT')
    position=event.get('position')
    if not isinstance(position,dict) or position.get('side') not in ('BUY','SELL'):
        raise TeacherActionError('STOP_EXIT_EXPLICIT_SIDE_REQUIRED')
    stop=money(position.get('current_stop'),'current_stop')
    entry=money(position.get('entry'),'entry')
    lots=money(position.get('lots'),'lots')
    side=position['side']
    quote=event.get('quote')
    if not isinstance(quote,dict) or not quote.get('source'):
        return {'decision':'WAIT_FOR_SOURCED_QUOTE','order_created':False,
                'position_closed':False,'stop_unchanged':str(stop),
                'lots_unchanged':str(lots)}
    # If a decision clock is supplied, the market observation must have
    # been available at that instant. Never replay a future quote as a stop.
    if 'decision_at' in event:
        at=event['decision_at']
        known=quote.get('known_at')
        if type(at) is not int or type(known) is not int or known>at:
            return {'decision':'WAIT_FOR_CAUSAL_QUOTE','order_created':False,
                    'position_closed':False,'stop_unchanged':str(stop),
                    'lots_unchanged':str(lots)}
    bid=money(quote.get('bid'),'bid')
    ask=money(quote.get('ask'),'ask')
    if bid>ask:
        raise TeacherActionError('STOP_EXIT_BID_EXCEEDS_ASK')
    observed=bid if side=='BUY' else ask
    touched=observed<=stop if side=='BUY' else observed>=stop
    if not touched:
        return {'decision':'PAPER_POSITION_HELD_STOP_NOT_HIT',
                'order_created':False,'position_closed':False,
                'quote_side':'BID' if side=='BUY' else 'ASK',
                'observed_quote':str(observed),'stop':str(stop),
                'lots_unchanged':str(lots)}
    return {'decision':'STOP_EXIT_TRIGGER_PAPER_NOT_A_FILL',
            'order_created':False,'position_closed':False,
            'stop_order_triggered_in_model':True,'broker_fill_verified':False,
            'quote_side':'BID' if side=='BUY' else 'ASK',
            'observed_quote':str(observed),'entry':str(entry),
            'stop':str(stop),'lots':str(lots),
            'realized_pnl':None,'slippage_unknown':True}


def execute(events_doc, source_folder, core_folder):
    """Run source-linked classroom *decisions*, never platform orders."""
    if events_doc.get('schema')!='artin_classroom_trade_actions_v1' or not isinstance(events_doc.get('events'),list):
        raise TeacherActionError('INVALID_EVENTS_SCHEMA')
    events=events_doc['events']
    if not events:raise TeacherActionError('EVENTS_REQUIRED')
    if any(not isinstance(e,dict) for e in events):
        raise TeacherActionError('CLASS_EVENT_OBJECT_REQUIRED')
    index,digests=source_index(source_folder,[e.get('session') for e in events])
    import sys
    core=Path(core_folder).resolve()
    manifest=json.loads((core/'LEGACY_SHA_MANIFEST.json').read_text(encoding='utf8'))
    if manifest.get('source_commit') != 'b48fb06f8b2b0d134292025f5b27fc670ad2a293':
        raise TeacherActionError('PINNED_ENGINE_REVISION_MISMATCH')
    hashes=manifest.get('files_sha256')
    required={'entry_engine.py','run_engine.py','trade_machine.py','raw_pipeline.py'}
    if not isinstance(hashes,dict) or not required.issubset(hashes):
        raise TeacherActionError('PINNED_ENGINE_HASH_COVERAGE_MISSING')
    for filename,expected in hashes.items():
        if (not isinstance(filename,str) or not isinstance(expected,str)
                or not re.fullmatch(r'[0-9a-f]{64}',expected)
                or Path(filename).is_absolute() or '..' in Path(filename).parts):
            raise TeacherActionError('PINNED_ENGINE_MANIFEST_INVALID')
        path=(core/filename).resolve()
        if not path.is_relative_to(core) or not path.is_file():
            raise TeacherActionError('PINNED_ENGINE_MANIFEST_INVALID')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise TeacherActionError('PINNED_ENGINE_SOURCE_TAMPERED')
    if str(core) not in sys.path:sys.path.insert(0,str(core))
    results=[];seen=set();previous_time={}
    for event in events:
        name=event.get('event_id');kind=event.get('kind')
        if not isinstance(name,str) or not name or name in seen:
            raise TeacherActionError('EVENT_ID_DUPLICATE_OR_MISSING')
        seen.add(name)
        rows,text=_evidence(event,index)
        # Reject out-of-order classroom evidence before interpreting or executing
        # the associated action, not after producing its decision.
        first=rows[0]['start_seconds'];last=rows[-1]['end_seconds'];sess=event['session']
        if first<previous_time.get(sess,-1):raise TeacherActionError('CLASSROOM_SEQUENCE_REVERSED')
        previous_time[sess]=last
        if kind in ('NO_ENTRY','ENTRY_AFTER_CONFIRMATION'):
            action=_decision(event,text)
        elif kind=='THREE_CANDLE_CLOSE_ENTRY':action=_three_candle_close_entry(event,text)
        elif kind=='RISKFREE_TO_ENTRY':action=_riskfree(event,text)
        elif kind=='KEEP_STRUCTURAL_STOP':action=_structural_stop(event,text)
        elif kind in ('REDUCE_RISK_STOP','HALVE_RISK_STOP','SAVE_PROFIT_STOP'):
            action=_sourced_stop_move(event,text)
        elif kind=='STOP_EXIT_TRIGGER':action=_stop_triggered_exit(event,text)
        else:raise TeacherActionError('UNKNOWN_TEACHER_CLASS_EVENT')
        results.append({'event_id':name,'session':sess,'start_seconds':first,
                        'end_seconds':last,'source_segment_ids':event['source_segment_ids'],
                        'original_audio_sha256s':list(dict.fromkeys(x['source_audio_sha256'] for x in rows)),
                        'source_status':'MACHINE_ASR_NOT_INDEPENDENTLY_LISTENED',
                        'class_instruction':kind,'execution':action})
    return {'schema':'artin_classroom_trade_actions_result_v1',
            'original_25_video_source_file_hashes':digests,
            'source_linked_class_events_executed':len(results),
            'classroom_decision_actions':results,'live_strategy_certified':False,
            'realized_pnl':None,'orders_sent':0,'broker_connected':False}