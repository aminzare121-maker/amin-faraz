"""Offline, gap-aware XAUUSD historical price diagnostic. Never routes orders."""
import argparse
import csv
import hashlib
import json
from decimal import Decimal as D, InvalidOperation
from pathlib import Path

BAR_SECONDS = 900

def num(x):
    try: v = D(str(x))
    except (TypeError, ValueError, InvalidOperation): raise ValueError('INVALID_NUMBER') from None
    if not v.is_finite(): raise ValueError('NONFINITE')
    return v

def bars_from_rows(rows):
    """Keep raw broker clock. Do NOT silently convert to UTC."""
    output = []; last = None
    for r in rows:
        t = num(r['time'])
        if t != int(t) or int(t) % BAR_SECONDS: raise ValueError('UNSUPPORTED_TIMESTAMP')
        t = int(t)
        if last is not None and t <= last: raise ValueError('DUPLICATE_OR_NONMONOTONIC')
        o,h,l,c = (num(r[k]) for k in ('open','high','low','close'))
        if min(o,h,l,c)<=0 or not l<=min(o,c)<=max(o,c)<=h: raise ValueError('OHLC_INVALID')
        output.append(dict(time=t,open=o,high=h,low=l,close=c)); last=t
    return output

def segments(bars):
    parts=[]; current=[]
    for b in bars:
        if current and b['time']-current[-1]['time']!=BAR_SECONDS:
            parts.append(current);current=[]
        current.append(b)
    if current:parts.append(current)
    return parts

def fixed_breakout(history):
    """Causal fixed BASELINE; not one of Faraz's original six strategies."""
    if len(history)<11:return None
    prev=history[-11:-1]; c=history[-1]['close']
    side='BUY' if c>max(b['high'] for b in prev) else 'SELL' if c<min(b['low'] for b in prev) else None
    return dict(side=side,lots='.01',stop_distance='2',target_distance='4') if side else None

def replay(part,idx,intent,cost,policy='unknown'):
    """Signal is formed before bar idx; executable side and gap-safe conservative fills."""
    if policy not in ('unknown','stop_first','target_first'):raise ValueError('POLICY')
    if idx<1 or idx>=len(part) or part[idx]['time']-part[idx-1]['time']!=BAR_SECONDS:raise ValueError('LOOKAHEAD_OR_GAP')
    if intent['side'] not in ('BUY','SELL'):raise ValueError('SIDE')
    side=1 if intent['side']=='BUY' else -1
    lots=num(intent['lots']);dist=num(intent['stop_distance']);reward=num(intent['target_distance'])
    if lots<=0 or lots%D('.01') or min(dist,reward)<=0:raise ValueError('INVALID_ORDER')
    spread,slip,comm,swap=(cost.get(k) for k in ('spread','slippage','commission_roundtrip_lot','swap_roundtrip_lot'))
    if spread is None or slip is None or comm is None:raise ValueError('COST_SCENARIO_MISSING')
    spread,slip,comm=num(spread),num(slip),num(comm)
    swap=None if swap is None else num(swap)
    if min(spread,slip,comm)<0:raise ValueError('COST_NEGATIVE')
    entry=part[idx]['open']+(spread if side==1 else D(0))+side*slip
    stop=entry-side*dist;target=entry+side*reward
    final=None;end=None;reason='UNCLOSED_AT_SEGMENT_END';ambiguous=False
    for i in range(idx,len(part)):
        b=part[i]; shift=spread if side==-1 else D(0)
        o,h,l=(b[k]+shift for k in ('open','high','low'))
        # Opening gaps are explicitly resolved before intrabar hit uncertainty.
        if (o<=stop if side==1 else o>=stop):
            final=(min(o,stop) if side==1 else max(o,stop))-side*slip
            end=i;reason='GAP_AT_STOP';break
        if (o>=target if side==1 else o<=target):
            final=target-side*slip;end=i;reason='TARGET_AT_OPEN';break
        s=(l<=stop if side==1 else h>=stop)
        p=(h>=target if side==1 else l<=target)
        if s and p:
            ambiguous=True;end=i
            if policy=='unknown':reason='AMBIGUOUS_SL_TP';break
            final=(stop if policy=='stop_first' else target)-side*slip
            reason='ASSUMED_'+policy.upper();break
        if s or p:
            final=(stop if s else target)-side*slip
            reason='STOP' if s else 'TARGET';end=i;break
    # Contract is explicit, not a broker-verified historical claim.
    gross=None if final is None else side*(final-entry)*D('100')*lots
    net=None if gross is None or swap is None else gross-lots*comm+lots*swap
    def s(v):return None if v is None else str(v)
    return dict(entry_time=part[idx]['time'],exit_time=part[end]['time'] if end is not None else None,
                entry=s(entry),exit=s(final),side=intent['side'],lots=s(lots),gross_scenario_usd=s(gross),
                net_scenario_usd=s(net),exit_reason=reason,intrabar_ambiguous=ambiguous,
                price_side_assumption='BID_BARS_AND_ASSUMED_ASK_SHIFT',historical_cost_verified=False),end

def diagnose(rows,signal=fixed_breakout,*,lookback=11,cost=None,policy='unknown',raw_sha=None):
    cost=cost or dict(spread='0.3',slippage='0.1',commission_roundtrip_lot='0',swap_roundtrip_lot=None)
    items=bars_from_rows(rows);parts=segments(items);trades=[];skipped=0
    for p in parts:
        if len(p)<lookback+2:skipped+=1;continue
        i=lookback
        while i<len(p):
            intent=signal(tuple(dict(b) for b in p[:i]))  # NEVER feed current/future bar
            if intent is None:i+=1;continue
            result,end=replay(p,i,intent,cost,policy)
            trades.append(result)
            if end is None:break
            i=end+1
    nets=[num(t['net_scenario_usd']) for t in trades if t['net_scenario_usd'] is not None]
    complete=bool(trades) and len(nets)==len(trades)
    capital=peak=dd=D(0)
    for v in nets:
        capital+=v;peak=max(peak,capital);dd=max(dd,peak-capital)
    return dict(schema=1,data_class='OBSERVED_PRICES_IF_INPUT_AUTHENTIC',data_sha256=raw_sha,
        clock_basis='RAW_BROKER_LABEL_NOT_ATTESTED',n_bars=len(items),n_segments=len(parts),
        largest_segment=max(map(len,parts),default=0),short_segments_skipped=skipped,
        baseline='FIXED_CAUSAL_BREAKOUT_NOT_FARAZ_SIX',cost_assumptions={k:(str(v) if v is not None else None) for k,v in cost.items()},
        scenario_policy=policy,n_scenario_entries=len(trades),n_resolved_scenarios=len(nets),
        net_scenario_usd=str(capital) if complete else None,
        drawdown_scenario_usd=str(dd) if complete else None,
        win_rate_scenario=str(D(sum(n>0 for n in nets))/len(nets)) if complete else None,
        no_trade_baseline_usd='0',trades=trades,status='EXPLORATORY_ONLY',
        blockers=['BROKER_CLOCK_SESSION_UNVERIFIED','EXECUTION_BID_ASK_UNVERIFIED','HISTORICAL_COST_UNVERIFIED','FRESH_HOLDOUT_UNVERIFIED'],
        market_profitability_verified=False,real_backtest_eligible=False,trade_allowed=False)

def main():
    ap=argparse.ArgumentParser(description='Faraz OFFLINE scenario diagnostic; never trades')
    for flag in ('bars','output','spread','slippage','commission'):ap.add_argument('--'+flag,required=True)
    ap.add_argument('--swap',help='hypothetical signed rollover cashflow USD/lot; omit for UNKNOWN')
    ap.add_argument('--policy',default='unknown',choices=['unknown','stop_first','target_first'])
    a=ap.parse_args();raw=Path(a.bars).read_bytes()
    rows=list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    cost=dict(spread=a.spread,slippage=a.slippage,commission_roundtrip_lot=a.commission,swap_roundtrip_lot=a.swap)
    result=diagnose(rows,cost=cost,policy=a.policy,raw_sha=hashlib.sha256(raw).hexdigest())
    Path(a.output).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('n_bars','n_segments','n_scenario_entries','net_scenario_usd','status')}))

if __name__=='__main__':main()
