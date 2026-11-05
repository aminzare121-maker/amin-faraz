"""Synthetic exposure-budget QA, no price/feed/model/network entry point."""
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from statistics import mean, stdev
from vendor.legacy_statistics import paired_bootstrap

SEEDS=(1729,2718,31415,42017,65537)
@dataclass(frozen=True)
class Opportunity:
    key: str
    block: int
    risk_usd: Decimal = Decimal('10')
    holding_seconds: int = 900
    lots: Decimal = Decimal('.01')
    notional_usd: Decimal = Decimal('4000') # hypothetical, not broker quote

def choose(universe, quota, seed):
    """Ex-ante quota, identical planned exposure per item; cannot inspect outcome."""
    if type(quota) is not int or not 0<=quota<=len(universe) or type(seed) is not int:
        raise ValueError('INVALID_PREDECLARED_BUDGET')
    if not universe:
        return ()
    if any(not isinstance(x,Opportunity) for x in universe): raise ValueError('TYPED_OPPORTUNITIES_REQUIRED')
    if len({x.key for x in universe})!=len(universe): raise ValueError('DUPLICATE_OPPORTUNITY')
    for x in universe:
        if not isinstance(x.key,str) or not x.key or type(x.block) is not int or x.block<0:
            raise ValueError('INVALID_ID_OR_BLOCK')
        if type(x.holding_seconds) is not int or x.holding_seconds<=0: raise ValueError('UNKNOWN_EXPOSURE')
        for v in (x.risk_usd,x.lots,x.notional_usd):
            if not isinstance(v,Decimal) or not v.is_finite() or v<=0: raise ValueError('UNKNOWN_EXPOSURE')
    budgets={(x.risk_usd,x.holding_seconds,x.lots,x.notional_usd) for x in universe}
    if len(budgets)!=1: raise ValueError('UNEQUAL_EX_ANTE_EXPOSURE')
    return tuple(sorted(universe,key=lambda x:sha256(f'readiness-v1|{seed}|{x.key}'.encode()).digest())[:quota])

def summarize(selected,outcomes,universe_size):
    if type(universe_size) is not int or universe_size<len(selected) or universe_size<0: raise ValueError('INVALID_UNIVERSE')
    rows=sorted(selected,key=lambda x:(x.block,x.key))
    net=[]
    for x in rows:
        v=outcomes[x.key]
        if not isinstance(v,Decimal) or not v.is_finite(): raise ValueError('INVALID_SYNTHETIC_OUTCOME')
        net.append(v)
    equity=peak=Decimal('10000');dd=Decimal(0)
    for v in net:
        equity+=v;peak=max(peak,equity);dd=max(dd,peak-equity)
    n=len(rows);secs=sum(x.holding_seconds for x in rows)
    blocks=len({x.block for x in rows})
    values=[float(x) for x in net]
    return {'synthetic_only':True,'trades':n,'opportunities':universe_size,
            'activity':n/universe_size if universe_size else None,'no_trade':universe_size-n,
            'independent_blocks_assumed':blocks,'independence_empirically_verified':False,
            'exposure_seconds':secs,'lot_hours':str(sum((x.lots*x.holding_seconds/Decimal(3600) for x in rows),Decimal(0))),
            'risk_usd_hours':str(sum((x.risk_usd*x.holding_seconds/Decimal(3600) for x in rows),Decimal(0))),
            'notional_usd_hours':str(sum((x.notional_usd*x.holding_seconds/Decimal(3600) for x in rows),Decimal(0))),
            'turnover_lots_roundtrip':str(sum((x.lots*2 for x in rows),Decimal(0))),
            'turnover_usd_roundtrip':str(sum((x.notional_usd*2 for x in rows),Decimal(0))),
            'net_hypothetical_usd':str(sum(net,Decimal(0))),'maxdd_step_usd':str(dd),
            'maxdd_over_initial_percent':str(dd/100),
            'per_trade_sharpe_descriptive_not_time_sharpe':mean(values)/stdev(values) if n>1 and stdev(values)>0 else None,
            'time_sharpe':'NOT_EVALUATED_NO_REGULAR_MARK_TO_MARKET',
            'inference':'INSUFFICIENT_INDEPENDENT_BLOCKS' if blocks<30 else 'SYNTHETIC_NOT_MARKET_EVIDENCE',
            'edge_established':False}

def run_fixture():
    u=tuple(Opportunity(f'op-{i:03}',i) for i in range(100))
    # Every opportunity loses 1 after explicitly hypothetical 0.38 fee/spread cost.
    outcomes={x.key:Decimal('-1') for x in u}
    ai=(u[0],)
    controls=[{'seed':s,'keys':[x.key for x in choose(u,1,s)],'metrics':summarize(choose(u,1,s),outcomes,100)} for s in SEEDS]
    daily={str(i):float(outcomes[u[i].key]) if i==0 else 0 for i in range(100)}
    randkeys={x.key for x in choose(u,1,SEEDS[0])}
    random_daily={str(i):float(outcomes[u[i].key]) if u[i].key in randkeys else 0 for i in range(100)}
    ci=paired_bootstrap(daily,random_daily,[str(i) for i in range(100)],block=5,reps=1000,seed=1729)
    return {'fixture':'ALL_SYNTHETIC_NO_MODEL','hypothetical_cost_per_trade':'0.38','hypothetical_gross_per_trade':'-0.62',
            'ai_one':summarize(ai,outcomes,100),'unmatched_100':summarize(u,outcomes,100),
            'matched_controls':controls,'no_trade':summarize((),outcomes,100),
            'ci_reused_diagnostic_only':ci,'ci_inference':'NOT_VALIDATED_FOR_MARKET; sparse outcomes, no edge claim',
            'real_data_used':False,'model_fit':False,'order_authority':False}
