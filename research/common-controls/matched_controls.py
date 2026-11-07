"""Predeclared paired directional controls, evaluated by the same replay engine.
Conditional on causal candidate entry opportunities; never a standalone portfolio.
No cherry-picking matched trades: any mismatch suppresses the whole comparison.
"""
from decimal import Decimal as D
from registry import digest
from execution_scenarios import replay,spread_at

SPEC=dict(schema=1,seeds=[1729,2718,31415,42017,65537],budget=5,
          generation='sha256(seed,entry_time)-direction',matching='exact-all-trades-no-filter',
          selection='validation-only-beat-all-controls',inference='NO_MARKET_SIGNIFICANCE')

def side(seed,entry_time):
    return 'buy' if int(digest([seed,entry_time])[-1],16)%2 else 'sell'

def paired(bars,order,context,adaptive,policy,candidate_result,equity,control_equities):
    slip=D(str(context['slippage']))
    spread,_=spread_at(bars[0]['time'],context.get('quotes',{}),context.get('assumed_spread'),context.get('receipt_ids',()))
    original_entry=D(candidate_result['entry']);risk=abs(original_entry-D(str(order['stop'])))
    target=None if order['target'] is None else abs(D(str(order['target']))-original_entry)
    kwargs={k:context[k] for k in ('quotes','receipt_ids','assumed_spread','slippage','swap','assumed_swap','commission','swap_schedule') if k in context}
    outputs=[]
    for seed in SPEC['seeds']:
        direction=side(seed,bars[0]['time']);sign=1 if direction=='buy' else -1
        entry=D(str(bars[0]['open']))+(spread if sign==1 else 0)+sign*slip
        randomized=dict(order,side=direction,stop=str(entry-sign*risk),target=None if target is None else str(entry+sign*target))
        result=replay(bars,randomized,**kwargs,intrabar_policy=policy,adaptive=adaptive)
        reasons=[]
        prior=control_equities.setdefault(seed,D('10000'))
        if prior is None or prior!=D(str(equity)):reasons.append('CAPITAL_PATH_MISMATCH')
        if result['exit_time']!=candidate_result['exit_time']:reasons.append('DURATION_MISMATCH')
        if result['net_with_known_costs'] is None or candidate_result['net_with_known_costs'] is None:reasons.append('UNKNOWN_COST_OR_PATH')
        if result['exit_reason']=='DATA_END_MARK' or candidate_result['exit_reason']=='DATA_END_MARK':reasons.append('UNCLOSED')
        control_equities[seed]=None if prior is None or result['net_with_known_costs'] is None else prior+D(str(result['net_with_known_costs']))
        outputs.append(dict(seed=seed,order=randomized,entry_time=bars[0]['time'],
            risk_usd=str(risk*D(str(order['lots']))*100),capital_before=None if prior is None else str(prior),
            candidate_capital_before=str(equity),duration_seconds=result['exit_time']-bars[0]['time'],
            candidate_duration_seconds=candidate_result['exit_time']-bars[0]['time'],
            context_hash=digest(context),trace=result,net=result['net_with_known_costs'],
            status='INCOMPARABLE' if reasons else 'PAIRED_SCENARIO_ONLY',reasons=reasons))
    return outputs

def summarize(rows):
    trials=[]
    for seed in SPEC['seeds']:
        pairs=[c for row in rows for c in row.get('matched_controls',[]) if c['seed']==seed]
        comparable=bool(rows) and len(pairs)==len(rows) and all(c['status']=='PAIRED_SCENARIO_ONLY' for c in pairs)
        trials.append(dict(seed=seed,trades=len(pairs),status='PAIRED_SCENARIO_ONLY' if comparable else 'INCOMPARABLE',
                           net_usd=float(sum(D(str(c['net'])) for c in pairs)) if comparable else None))
    return dict(spec=SPEC,trials=trials,comparable=all(t['status']=='PAIRED_SCENARIO_ONLY' for t in trials),
                market_significance=False,posthoc_seed_selection=False)
