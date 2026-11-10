"""Artin measurable-PDF-subset autonomous DEMO bot for Windows MetaTrader5.

Reads actual ePlanet DEMO XAUUSD.st 15m CLOSED bars; discovers candidate
setups itself, derives risk from live broker contract, optionally places DEMO
orders and moves stops by FXM page-4 ladder. Never connects/logs into an
account. Requires explicit documented winrate, broker-day offset, and an
explicit --enable-demo-orders switch for any order API call.

IMPORTANT: these are only TWO strict/measurable PDF candidate subsets;
NOT all 13 video semantics, NOT a certified implementation of the instructor.
On unknown market state the bot refuses to send orders. No REAL accounts.
Live execution has NOT been tested in this environment.
"""
from __future__ import annotations
import argparse,datetime as dt,json,os,time,sys,hashlib
from decimal import Decimal as D, ROUND_FLOOR
from pathlib import Path
from artin_automatic_teacher_recognizer import Bar,AutoRecognizer
from fxm_teacher_policy import AccountRisk,winrate_target_policy,day_trade_permission

MAGIC=26011113
SERVER='ePlanet-MT5';SYMBOL='XAUUSD.st'

class BotBlocked(RuntimeError):pass

SOURCE_PDF_HASHES={
    'FXM.pdf':'504930d6b148b008f134a92e7445e870b7e3fc54478db0956f82f695c23a7af1',
    'Technical(1).pdf':'f50f66139fa96c8083e936f368160c3b77667302174e3e1c6084c8bbd6a1a909'}

def verify_teacher_pdf_sources(directory):
    """Never authorize demo orders from changed or absent teacher handouts."""
    for filename,expected in SOURCE_PDF_HASHES.items():
        p=Path(directory)/filename
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise BotBlocked('TEACHER_ORIGINAL_PDF_MISSING_OR_MODIFIED:'+filename)
    return True

def atomic_state(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('x',encoding='utf-8') as out:
        json.dump(data,out,ensure_ascii=False,sort_keys=True,indent=2);out.flush();os.fsync(out.fileno())
    os.replace(temp,path)

def guard_account(mt,expected_data_path):
    account=mt.account_info();terminal=mt.terminal_info()
    if account is None or terminal is None:raise BotBlocked('ACCOUNT_OR_TERMINAL_UNAVAILABLE')
    if (account.trade_mode!=mt.ACCOUNT_TRADE_MODE_DEMO or account.server!=SERVER
        or 'eplanet' not in account.company.lower()):raise BotBlocked('STRICT_EPLANET_DEMO_REQUIRED')
    if str(Path(terminal.data_path).resolve()).lower()!=str(Path(expected_data_path).resolve()).lower():
        raise BotBlocked('MT5_TERMINAL_DATA_PATH_MISMATCH')
    if not terminal.connected:raise BotBlocked('TERMINAL_DISCONNECTED')
    return account

def validated_winrate(path):
    d=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (d.get('schema')!='fxm_winrate_evidence_v1' or d.get('audited') is not True
        or not isinstance(d.get('source'),str) or not d['source'].strip()
        or type(d.get('wins')) is not int or type(d.get('losses')) is not int
        or d['wins']<0 or d['losses']<0 or d['wins']+d['losses']==0):
        raise BotBlocked('AUDITED_FXM_WINRATE_RECORD_REQUIRED')
    return D(d['wins'])*100/D(d['wins']+d['losses']),d['source']

def fxm_targets(mode,winrate,source):
    if mode=='THREE_TP':
        if not D(45)<winrate<D(66):raise BotBlocked('THREE_TP_NOT_ALLOWED_FOR_RECORDED_WINRATE')
        return (D('0.8'),D('1.3'),D('1.8'))
    if mode!='SINGLE_RR':raise BotBlocked('UNKNOWN_TARGET_MODE')
    rule=winrate_target_policy(str(winrate),evidence_source=source)
    if rule['status']!='RR_CANDIDATE_FROM_HANDOUT':raise BotBlocked(rule['status'])
    return (D(rule['rr']),)

def broker_volume(mt,order_type,symbol,entry,stop,risk_budget,info):
    loss=mt.order_calc_profit(order_type,symbol,1.0,float(entry),float(stop))
    if loss is None or loss>=0:raise BotBlocked('BROKER_RISK_PER_LOT_UNAVAILABLE')
    step,minvol,maxvol=(D(str(getattr(info,k))) for k in ('volume_step','volume_min','volume_max'))
    if not(step>0 and minvol>0 and maxvol>=minvol):raise BotBlocked('BAD_BROKER_LOT_GRID')
    max_by_risk=D(risk_budget)/(-D(str(loss)))
    lots=min(max_by_risk,maxvol)
    lots=(lots/step).to_integral_value(rounding=ROUND_FLOOR)*step
    if lots<minvol:raise BotBlocked('FXM_MIN_LOT_EXCEEDS_RISK_BUDGET')
    return lots

def exact_broker_price(v,info):
    v=D(v);tick=D(str(info.trade_tick_size))
    if tick<=0:raise BotBlocked('BROKER_TICK_SIZE_UNKNOWN')
    if v/tick!=(v/tick).to_integral_value():raise BotBlocked('TEACHER_STRUCTURE_NOT_ON_BROKER_TICK')
    return v

def source_rates(mt,count):
    now=mt.copy_rates_from_pos(SYMBOL,mt.TIMEFRAME_M15,0,1)
    if now is None or len(now)!=1:raise BotBlocked('CURRENT_BAR_UNAVAILABLE')
    fence=int(now[0]['time'])
    raw=mt.copy_rates_from_pos(SYMBOL,mt.TIMEFRAME_M15,1,count)
    if raw is None or len(raw)<3:raise BotBlocked('CLOSED_BAR_HISTORY_MISSING')
    check=mt.copy_rates_from_pos(SYMBOL,mt.TIMEFRAME_M15,0,1)
    if check is None or len(check)!=1 or int(check[0]['time'])!=fence:
        raise BotBlocked('MOVING_BAR_BOUNDARY_RETRY')
    bars=sorted((Bar(int(x['time']),D(str(x['open'])),D(str(x['high'])),
                     D(str(x['low'])),D(str(x['close']))) for x in raw),key=lambda x:x.t)
    if bars[-1].t+900!=fence:raise BotBlocked('LAST_CLOSED_BAR_NOT_FRESH')
    if len({x.t for x in bars})!=len(bars):raise BotBlocked('HISTORY_DUPLICATES')
    return bars,fence

def broker_day_outcomes(mt,broker_day_offset_minutes,at,positions):
    """FXM p5 from broker-confirmed TP/SL exits, not modelled PnL.

    An ambiguous exit reason, incomplete position, or unavailable history
    blocks entry. The broker-day offset is owner-provided, never assumed.
    """
    day=(int(at)+broker_day_offset_minutes*60)//86400
    start=day*86400-broker_day_offset_minutes*60
    end=(day+1)*86400-broker_day_offset_minutes*60
    start_dt=dt.datetime.fromtimestamp(start,dt.timezone.utc)
    end_dt=dt.datetime.fromtimestamp(end,dt.timezone.utc)
    deals=mt.history_deals_get(start_dt,end_dt)
    if deals is None:raise BotBlocked('BROKER_DAY_HISTORY_UNAVAILABLE')
    active_ids={int(p.identifier) for p in positions if int(p.magic)==MAGIC}
    out_types={mt.DEAL_ENTRY_OUT,mt.DEAL_ENTRY_OUT_BY}
    closed={}
    for deal in deals:
        if (int(deal.magic)!=MAGIC or deal.symbol!=SYMBOL or deal.entry not in out_types):
            continue
        pid=int(deal.position_id)
        if pid in active_ids:raise BotBlocked('PARTIAL_EXIT_IN_DAY_REVIEW_REQUIRED')
        reason='TP' if deal.reason==mt.DEAL_REASON_TP else 'SL' if deal.reason==mt.DEAL_REASON_SL else None
        if reason is None:raise BotBlocked('UNCLASSIFIED_BROKER_CLOSED_TRADE')
        if pid in closed and closed[pid][0]!=reason:raise BotBlocked('MULTIPLE_CONFLICTING_EXIT_REASONS')
        closed[pid]=(reason,int(deal.time))
    outcomes=[x[0] for x in sorted(closed.values(),key=lambda p:p[1])]
    result=day_trade_permission(outcomes)
    if result['status']!='PAPER_DAY_SEQUENCE_CONTINUE':
        raise BotBlocked('FXM_DAY_STOP:'+str(result.get('reason')))
    return outcomes


def reconcile_closed_plan(mt,plan,positions):
    """Only clear a persisted plan after an actual broker closing deal.

    The opening deal is identified by its ticket or order (rather than
    assuming a magic number survives an automatic SL/TP close). A missing
    history leaves the bot safely blocked from a replacement entry.
    """
    if not plan:return None,'NO_PREVIOUS_PLAN'
    if any(int(p.magic)==MAGIC for p in positions):return plan,'PREVIOUS_PLAN_STILL_OPEN'
    from_ts=int(plan['signal_id'].split(':',1)[0])-3600
    history=mt.history_deals_get(dt.datetime.fromtimestamp(max(0,from_ts),dt.timezone.utc),
                                 dt.datetime.now(dt.timezone.utc))
    if history is None:return plan,'DEAL_RECONCILIATION_HISTORY_UNAVAILABLE'
    openings=[d for d in history if int(d.ticket)==int(plan['broker_deal']) or
        int(d.order)==int(plan['ticket'])]
    ids={int(d.position_id) for d in openings if d.entry==mt.DEAL_ENTRY_IN}
    if not ids:return plan,'OPENING_DEAL_NOT_FOUND'
    outs=[d for d in history if int(d.position_id) in ids and
          d.entry in (mt.DEAL_ENTRY_OUT,mt.DEAL_ENTRY_OUT_BY)]
    if not outs:return plan,'CLOSING_DEAL_NOT_FOUND'
    return None,'CLOSED_POSITION_RECONCILED_FROM_BROKER_HISTORY'


def make_plan(mt,account,info,signal,mode,targets,risk_pct,reference_balance,broker_day_offset):
    tick=mt.symbol_info_tick(SYMBOL)
    if tick is None or tick.bid<=0 or tick.ask<tick.bid:raise BotBlocked('LIVE_QUOTE_INVALID')
    if int(tick.time)<signal.at or int(tick.time)>signal.at+900:raise BotBlocked('STALE_SIGNAL_OR_TICK')
    risk=AccountRisk(D(str(account.balance)),D(reference_balance),D(risk_pct)).assess()
    if risk['status']!='RISK_BUDGET_AVAILABLE':raise BotBlocked(risk['status'])
    side=signal.side;price=D(str(tick.ask if side=='BUY' else tick.bid))
    stop=D(signal.operational_stop)
    if not (stop<price if side=='BUY' else stop>price):raise BotBlocked('INVALID_STRUCTURE_STOP')
    stop=exact_broker_price(stop,info)
    order_type=mt.ORDER_TYPE_BUY if side=='BUY' else mt.ORDER_TYPE_SELL
    lots=broker_volume(mt,order_type,SYMBOL,price,stop,D(risk['per_trade_risk_budget']),info)
    sign=D(1) if side=='BUY' else D(-1)
    d=sign*(price-stop)
    tp=exact_broker_price(price+sign*d*targets[-1],info)
    level=D(str(info.trade_stops_level))*D(str(info.point))
    if abs(price-stop)<level or abs(tp-price)<level:raise BotBlocked('BROKER_MIN_STOP_DISTANCE')
    return {'signal_id':f'{signal.at}:{signal.zone_id}:{signal.side}:{signal.route}',
        'symbol':SYMBOL,'magic':MAGIC,'side':side,'entry_quote':str(price),
        'stop':str(stop),'initial_stop':str(stop),'tp':str(tp),'lots':str(lots),
        'tp_levels':[str(price+sign*d*r) for r in targets],
        'stage':0,'source':list(signal.sources),'teacher_semantics_fully_verified':False,
        'day_at':int((signal.at+broker_day_offset*60)//86400),
        'broker_fill_verified':False}

def trade_request(mt,plan,info,deviation):
    # Honor broker-advertised FOK/IOC, never retry a failed/ambiguous send.
    fill=int(info.filling_mode)
    if fill & 1:filling=mt.ORDER_FILLING_FOK
    elif fill & 2:filling=mt.ORDER_FILLING_IOC
    else:raise BotBlocked('NO_SUPPORTED_BROKER_FILLING_POLICY')
    return {'action':mt.TRADE_ACTION_DEAL,'symbol':SYMBOL,'magic':MAGIC,
        'type':mt.ORDER_TYPE_BUY if plan['side']=='BUY' else mt.ORDER_TYPE_SELL,
        'volume':float(D(plan['lots'])),'price':float(D(plan['entry_quote'])),
        'sl':float(D(plan['stop'])),'tp':float(D(plan['tp'])),
        'deviation':deviation,'type_time':mt.ORDER_TIME_GTC,
        'type_filling':filling,'comment':'ARTIN_PDF_SUBSET_DEMO'}

def manage_stop(mt,plan,positions):
    if not plan or not positions:return 'NO_OWN_POSITION'
    own=[x for x in positions if int(x.magic)==MAGIC]
    if len(own)!=1:return 'OWN_POSITION_UNKNOWN_OR_AMBIGUOUS'
    pos=own[0];tick=mt.symbol_info_tick(SYMBOL)
    if tick is None:return 'TICK_UNAVAILABLE'
    quote=D(str(tick.bid if plan['side']=='BUY' else tick.ask))
    levels=[D(x) for x in plan['tp_levels']]
    if len(levels)!=3:return 'SINGLE_TARGET_BROKER_MANAGED'
    sign=D(1) if plan['side']=='BUY' else D(-1)
    stage=2 if sign*(quote-levels[1])>=0 else 1 if sign*(quote-levels[0])>=0 else 0
    if stage<=plan['stage']:return 'NO_NEW_STAGE'
    stop=D(plan['entry_quote']) if stage==1 else levels[0]
    old=D(str(pos.sl));entry=D(plan['entry_quote'])
    if sign*(stop-old)<=0:return 'STOP_ALREADY_TIGHTER'
    info=mt.symbol_info(SYMBOL)
    try:stop=exact_broker_price(stop,info)
    except BotBlocked:return 'TARGET_STOP_NOT_ON_TICK'
    if sign*(quote-stop)<=D(str(info.trade_stops_level))*D(str(info.point)):
        return 'STOP_TOO_CLOSE_TO_LIVE_PRICE'
    # Never widen or remove SL; explicit ticket prevents modifying other EAs.
    req={'action':mt.TRADE_ACTION_SLTP,'position':int(pos.ticket),'symbol':SYMBOL,
         'sl':float(stop),'tp':float(D(str(pos.tp))),'magic':MAGIC}
    result=mt.order_send(req)
    if result is None or result.retcode!=mt.TRADE_RETCODE_DONE:
        return 'STOP_MOVE_FAILED_NO_CLAIM'
    plan['stage']=stage;plan['stop']=str(stop)
    return 'FXM_STOP_MOVED_TO_ENTRY' if stage==1 else 'FXM_STOP_MOVED_TO_TP1'

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terminal',required=True);p.add_argument('--expected-data',required=True)
    p.add_argument('--state',required=True);p.add_argument('--report',required=True)
    p.add_argument('--history-bars',type=int,default=4000)
    p.add_argument('--mode',choices=['SINGLE_RR','THREE_TP'],default='THREE_TP')
    p.add_argument('--risk-pct',default='1');p.add_argument('--reference-balance')
    p.add_argument('--winrate-evidence-file');p.add_argument('--broker-day-offset-minutes',type=int)
    p.add_argument('--deviation-points',type=int,default=0)
    p.add_argument('--enable-demo-orders',action='store_true')
    p.add_argument('--once',action='store_true');p.add_argument('--poll-seconds',type=int,default=2)
    a=p.parse_args(argv)
    if not 3<=a.history_bars<=50000:raise BotBlocked('BOUNDED_HISTORY_REQUIRED')
    if not 1<=D(a.risk_pct)<=2:raise BotBlocked('FXM_RISK_PERCENT_OUT_OF_RANGE')
    if a.deviation_points<0 or a.poll_seconds<1:raise BotBlocked('INVALID_RUNTIME_PARAMETER')
    # Fail closed if prerequisites for demo-order mode are missing.
    if a.enable_demo_orders and (not a.reference_balance or not a.winrate_evidence_file
                                 or a.broker_day_offset_minutes is None):
        raise BotBlocked('DEMO_ORDERS_REQUIRE_BALANCE_WINRATE_AND_BROKER_DAY_SOURCE')
    if a.enable_demo_orders:
        verify_teacher_pdf_sources(Path(__file__).parent)
    if a.broker_day_offset_minutes is not None and not -840<=a.broker_day_offset_minutes<=840:
        raise BotBlocked('INVALID_BROKER_TIME_OFFSET')
    state_path=Path(a.state)
    state=json.loads(state_path.read_text(encoding='utf8')) if state_path.exists() else {}
    if state and state.get('schema')!='artin_demo_pdf_automatic_state_v1':
        raise BotBlocked('STATE_SCHEMA_MISMATCH')
    if state and a.reference_balance and state.get('reference_balance')!=a.reference_balance:
        raise BotBlocked('REFERENCE_BALANCE_IMMUTABLE')
    if not state:
        state={'schema':'artin_demo_pdf_automatic_state_v1','last_bar':None,
               'reference_balance':a.reference_balance,'plan':None,
               'account_login_private':None,'symbol':SYMBOL,'server':SERVER}
    import MetaTrader5 as mt
    # The python package must be installed on the owner's Windows; this runtime
    # lacks Windows and never claims to have sent any order.
    if not mt.initialize(str(Path(a.terminal)),timeout=15000):
        raise BotBlocked('ATTACH_EXISTING_TERMINAL_FAILED')
    try:
        def cycle():
            account=guard_account(mt,a.expected_data)
            if state['account_login_private'] is not None and state['account_login_private']!=int(account.login):
                raise BotBlocked('DEMO_ACCOUNT_CHANGED')
            state['account_login_private']=int(account.login) # local state only; never print/publish
            positions=mt.positions_get(symbol=SYMBOL)
            if positions is None:raise BotBlocked('POSITION_LOOKUP_FAILED')
            reconcile_status='NO_PREVIOUS_PLAN'
            if state.get('plan'):
                state['plan'],reconcile_status=reconcile_closed_plan(mt,state['plan'],positions)
            move='NO_OWN_POSITION'
            if a.enable_demo_orders:
                move=manage_stop(mt,state.get('plan'),positions)
            bars,fence=source_rates(mt,a.history_bars)
            detector=AutoRecognizer();signals=[]
            for b in bars:signals+=detector.step(b)
            closed=bars[-1].t
            if state.get('last_bar') is not None and closed<=state['last_bar']:
                atomic_state(state_path,state) if not state_path.exists() else _replace_state(state_path,state)
                return {'status':'NO_NEW_CLOSED_M15','closed':closed,'stop_management':move}
            new=[s for s in signals if s.at==fence]
            state['last_bar']=closed
            info=mt.symbol_info(SYMBOL)
            if info is None:raise BotBlocked('BROKER_SYMBOL_UNAVAILABLE')
            if len(new)!=1:
                action='NO_SIGNAL_OR_AMBIGUOUS'
            elif positions:
                action='POSITIONS_EXIST_NO_OVERLAPPING_ORDERS'
            elif state.get('plan') is not None:
                action='PREVIOUS_DEMO_PLAN_NEEDS_BROKER_POSITION_RECONCILIATION'
            elif not a.enable_demo_orders:
                action='OBSERVED_PDF_CANDIDATE_ORDERS_DISABLED'
            else:
                rate,rate_source=validated_winrate(a.winrate_evidence_file)
                targets=fxm_targets(a.mode,rate,rate_source)
                broker_day_outcomes(mt,a.broker_day_offset_minutes,fence,positions)
                plan=make_plan(mt,account,info,new[0],a.mode,targets,a.risk_pct,
                               a.reference_balance,a.broker_day_offset_minutes)
                request=trade_request(mt,plan,info,a.deviation_points)
                checked=mt.order_check(request)
                if checked is None or checked.retcode!=0:
                    raise BotBlocked('BROKER_ORDER_CHECK_FAILED_NO_ORDER_SENT')
                # Persist the closed-bar watermark BEFORE the one and only
                # send attempt. This favors missed trades over duplicates.
                _replace_state(state_path,state)
                guard_account(mt,a.expected_data)
                if mt.positions_get(symbol=SYMBOL):
                    raise BotBlocked('POSITION_APPEARED_BEFORE_SEND')
                result=mt.order_send(request)
                if result is None:
                    action='ORDER_RESULT_UNKNOWN_NO_AUTOMATIC_RETRY'
                elif result.retcode!=mt.TRADE_RETCODE_DONE:
                    action='ORDER_REJECTED_OR_UNCERTAIN_NO_AUTOMATIC_RETRY:'+str(result.retcode)
                else:
                    plan['ticket']=int(result.order)
                    plan['broker_deal']=int(result.deal)
                    plan['broker_price']=str(result.price)
                    plan['broker_fill_verified']=True
                    state['plan']=plan
                    action='EPLANET_DEMO_ORDER_ACCEPTED_BROKER_RESULT'
                    _replace_state(state_path,state)
                return {'status':action,'closed':closed,'signals_at_latest_closed_bar':1,
                    'route':new[0].route,'stop_management':move,
                    'previous_position_reconciliation':reconcile_status,
                    'orders_submitted_by_this_cycle':1,
                    'broker_result_only':True,'teacher_semantics_fully_verified':False}
            _replace_state(state_path,state)
            return {'status':action,'closed':closed,'signals_at_latest_closed_bar':len(new),
                'route':new[0].route if len(new)==1 else None,
                'recognition_counts':detector.counts,'stop_management':move,
                'previous_position_reconciliation':reconcile_status,
                'orders_submitted_by_this_cycle':0}
        while True:
            status=cycle()
            report=Path(a.report);report.parent.mkdir(parents=True,exist_ok=True)
            with report.open('a',encoding='utf8') as out:
                out.write(json.dumps(status,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno())
            print(json.dumps(status,ensure_ascii=False))
            if a.once:break
            time.sleep(a.poll_seconds)
    finally:mt.shutdown()

def _replace_state(path,state):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    if temp.exists():raise BotBlocked('UNRESOLVED_STATE_WRITE_TEMP')
    atomic_state(path,state)

if __name__=='__main__':main()