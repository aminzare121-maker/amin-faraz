"""Research-only execution extension: variable quote spreads, explicit path/cost assumptions."""
from decimal import Decimal as D
from comparison import net_cost

def number(v):
    if v is None or type(v) is bool:raise ValueError('NUMBER_REQUIRED')
    x=D(str(v))
    if not x.is_finite():raise ValueError('FINITE_REQUIRED')
    return x

def spread_at(t,quotes,assumed_spread,receipt_ids):
    q=quotes.get(t)
    if q and q.get('time')==t and q.get('receipt_id') in receipt_ids and q.get('status')=='VERIFIED':
        bid,ask=number(q['bid']),number(q['ask'])
        if bid<=0 or ask<bid:raise ValueError('BAD_QUOTE')
        return ask-bid,'VERIFIED_QUOTE_AT_BAR_OPEN'
    if assumed_spread is None:raise ValueError('SPREAD_UNKNOWN')
    value=number(assumed_spread)
    if value<0:raise ValueError('NEGATIVE_SPREAD')
    return value,'ASSUMPTION'

def replay(bars,order,*,quotes=None,receipt_ids=(),assumed_spread=None,slippage=None,swap=None,assumed_swap=None,commission=None,intrabar_policy='stop_first'):
    """Replay an externally frozen order, not choose a strategy. No order API exists.

    Quotes are synchronous bar-open observations, not full intrabar paths.
    Ask OHLC shift within each bar remains an ASSUMPTION even with real open spreads.
    """
    quotes=quotes or {}
    if intrabar_policy not in ('stop_first','target_first','unknown'):raise ValueError('INTRABAR_POLICY')
    if not bars or order['signal_available']>bars[0]['time']:raise ValueError('LOOKAHEAD')
    if order['side'] not in ('buy','sell'):raise ValueError('SIDE')
    previous=None
    for b in bars:
        if previous is not None and b['time']-previous!=900:raise ValueError('SESSION_GAP_UNRESOLVED')
        o,h,l,c=(number(b[k]) for k in ('open','high','low','close'))
        if min(o,h,l,c)<=0 or not l<=min(o,c)<=max(o,c)<=h:raise ValueError('OHLC')
        if not b.get('final') or b.get('available',0)<b['time']+900:raise ValueError('UNCLOSED')
        previous=b['time']
    slip=number(slippage);fee=number(commission);lot=number(order['lots'])
    if min(slip,fee)<0 or lot<=0 or lot%D('.01') or order.get('contract')!=100:raise ValueError('COST_OR_LOT')
    side=1 if order['side']=='buy' else -1
    entry_spread,entry_basis=spread_at(bars[0]['time'],quotes,assumed_spread,receipt_ids)
    entry=number(bars[0]['open'])+(entry_spread if side==1 else 0)+side*slip
    stop,target=number(order['stop']),number(order['target'])
    if not (stop<entry<target if side==1 else target<entry<stop):raise ValueError('LEVELS')
    ambiguity=False;trace=[];reason='DATA_END_MARK'
    for b in bars:
        s,basis=spread_at(b['time'],quotes,assumed_spread,receipt_ids);shift=s if side==-1 else D(0)
        o,h,l,c=(number(b[k])+shift for k in ('open','high','low','close'))
        sl=l<=stop if side==1 else h>=stop;tp=h>=target if side==1 else l<=target
        trace.append({'time':b['time'],'spread':str(s),'basis':basis})
        if sl:
            exit=(min(o,stop) if side==1 else max(o,stop))-side*slip
            reason='STOP_FIRST_AMBIGUOUS' if tp else 'STOP';ambiguity=tp
            if tp and intrabar_policy=='target_first':exit=target-side*slip;reason='TARGET_FIRST_AMBIGUOUS'
            break
        if tp:exit=target-side*slip;reason='TARGET_CONSERVATIVE_NO_GAP_BONUS';break
        exit=c-side*slip
    gross=side*(exit-entry)*100*lot
    # Spread/slippage are already in entry/exit; never subtract them twice.
    known=net_cost(gross,0,fee*lot,swap,0)
    scenario=net_cost(gross,0,fee*lot,assumed_swap,0) if swap is None and assumed_swap is not None else known
    unresolved=ambiguity and intrabar_policy=='unknown'
    return {'entry':str(entry),'exit':None if unresolved else str(exit),'gross_usd':None if unresolved else str(gross),'net_with_known_costs':None if unresolved else known['net'],
        'scenario_net_usd':None if unresolved else scenario['net'],'swap_status':'UNKNOWN' if swap is None else 'CALLER_INPUT_NOT_HISTORICALLY_ATTESTED',
        'cost_basis':'ASSUMPTION','slippage_basis':'ASSUMPTION','intrabar_path':'UNKNOWN','intrabar_policy':intrabar_policy,
        'ambiguous_sl_tp':ambiguity,'exit_reason':reason,'spread_trace':trace,'entry_spread_basis':entry_basis,
        'profitability_verified':False,'trade_allowed':False,'no_trade_baseline_usd':'0'}
