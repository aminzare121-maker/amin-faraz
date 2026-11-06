"""Paired target ablation using the existing unmodified offline engine.
No broker, terminal, order or network imports. Private traces never published.
"""
import argparse,collections,csv,hashlib,importlib,json,sys
from decimal import Decimal as D, ROUND_FLOOR
from datetime import datetime,timezone
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def floorstep(x,step):return (x/step).to_integral_value(rounding=ROUND_FLOOR)*step
def dd(vals,capital=D('10000')):
    equity=peak=capital;absolute=relative=D(0)
    for x in vals:
        equity+=x;peak=max(peak,equity)
        absolute=max(absolute,peak-equity);relative=max(relative,(peak-equity)/peak)
    return dict(usd=str(absolute),fraction=str(relative))
def stats(rows):
    ns=[D(r['net_scenario_usd']) for r in rows if r['net_scenario_usd'] is not None]
    wins=[x for x in ns if x>0];losses=[x for x in ns if x<0]
    return dict(entries=len(rows),closed=len(ns),unresolved=len(rows)-len(ns),
        known_partial_net=str(sum(ns,D(0))),full_net=None if len(ns)!=len(rows) else str(sum(ns,D(0))),
        wins=len(wins),losses=len(losses),breakeven=len(ns)-len(wins)-len(losses),
        win_rate=str(D(len(wins))/len(ns)) if ns else None,
        average_win=str(sum(wins,D(0))/len(wins)) if wins else None,
        average_loss=str(-sum(losses,D(0))/len(losses)) if losses else None,
        PF=str(sum(wins,D(0))/-sum(losses,D(0))) if losses else None,
        expectancy_known_closed=str(sum(ns,D(0))/len(ns)) if ns else None,
        exit_reasons=dict(collections.Counter(r['reason'] for r in rows)),
        commission_closed=str(sum((D(r['gross_scenario_usd'])-D(r['net_scenario_usd']) for r in rows if r['net_scenario_usd'] is not None),D(0))),
        spread_slippage_cash_separate='UNMEASURABLE_ALREADY_IN_FILL')

def size(entry,stop,quote,equities,management):
    p=management['policy'];spec=management['spec'];equity=min(equities)
    if equity<=0:return None,'NONPOSITIVE_KNOWN_EQUITY'
    rate=min(D('.0025'),D(p['max_order_risk_fraction']))
    budget=equity*rate
    perlot=(max(abs(entry-stop),abs(quote-stop))+D(p['max_slippage']))*D(spec['contract_size'])+D(p['commission_per_lot'])
    vol=floorstep(min(budget/perlot,D(spec['volume_max']),
        equity*D(p['max_notional_multiple'])/(entry*D(spec['contract_size']))),D(spec['volume_step']))
    if vol<D(spec['volume_min']):return None,'MIN_LOT_EXCEEDS_BUDGET_OR_NOTIONAL'
    if vol*perlot>budget:raise ValueError('RISK_BUDGET')
    return dict(lots=vol,budget=budget,risk=vol*perlot,perlot=perlot,reference_equity=equity),None

def one(engine,part,i,setup,cost,lots,target):
    used=False
    def once(history):
        nonlocal used
        if used:return None
        used=True;return setup
    window=part[i-1:min(len(part),i+12)]
    r=engine.simulate(window,once,lots=str(lots),target_distance=str(target),
        max_holding_bars=12,policy='unknown',**cost)
    if r['positions']!=1:raise ValueError('EXISTING_ENGINE_SINGLE_ENTRY_FAILED')
    return r['rows'][0]

def liquidation(close,row,cost):
    side=D(1) if row['side']=='buy' else D(-1)
    quote=close+(D(cost['spread']) if row['side']=='sell' else D(0))-side*D(cost['slippage'])
    return side*(quote-D(row['entry']))*100*D(row['lots'])-D(cost['commission_roundtrip_per_lot'])*D(row['lots'])

def sampled_mtm(part,rows,cost,capital=D('10000')):
    cash=capital;points=[cash];truncated=False
    bytime={b['time']:b for b in part}
    for r in rows:
        start=r['entry_time'];end=r['exit_time']
        points.append(cash+liquidation(bytime[start]['open'],r,cost))
        for t in range(start,end,900):
            if t+900==end:
                if r['net_scenario_usd'] is None:truncated=True;break
                cash+=D(r['net_scenario_usd']);points.append(cash)
            else:points.append(cash+liquidation(bytime[t]['close'],r,cost))
        if truncated:break
    peak=capital;absolute=relative=D(0)
    for x in points:
        peak=max(peak,x);absolute=max(absolute,peak-x);relative=max(relative,(peak-x)/peak)
    return dict(sampled_prefix_dd_usd=str(absolute),sampled_prefix_dd_fraction=str(relative),
                points=len(points),truncated_before_uncertain_bar=truncated,
                exact_intrabar_mtm_dd='UNMEASURABLE')

def pair_part(engine,plan,candidate,part,cost,management,equities):
    cash=list(equities);pending=[None,None];rows=[[],[]]
    counters=collections.Counter();unknown=False
    for i in range(1,len(part)):
        t=part[i]['time']
        for arm in range(2):
            p=pending[arm]
            if p is not None and p['exit_time']<=t:
                if p['net_scenario_usd'] is None:unknown=True
                else:cash[arm]+=D(p['net_scenario_usd'])
                pending[arm]=None
        if unknown:
            counters['bars_blocked_after_unknown']+=len(part)-i;break
        if any(p is not None for p in pending):
            counters['joint_busy_bars']+=1;continue
        history=part[max(0,i-120):i]
        closed=[dict(b,final=True,observed_at=b['time']+900,time_basis='RAW_LABEL_UNVERIFIED') for b in history]
        setup=plan(closed,t,candidate)
        counters['signal_callbacks']+=1
        if setup is None:continue
        counters['signals_flat']+=1
        if setup['signal_time']+900>t:raise ValueError('LOOKAHEAD')
        side=D(1) if setup['side']=='buy' else D(-1)
        quote=part[i]['open']+(D(cost['spread']) if side==1 else D(0))
        entry=quote+side*D(cost['slippage']);stop=D(setup['stop_loss'])
        if side*(entry-stop)<=0:
            counters['STOP_CROSSED_AT_ENTRY']+=1;continue
        sizing,reason=size(entry,stop,quote,cash,management)
        if reason:
            counters[reason]+=1;continue
        targets=[D(10),D('1.5')*abs(entry-stop)]
        result=[one(engine,part,i,setup,cost,sizing['lots'],target) for target in targets]
        if result[0]['entry_time']!=result[1]['entry_time'] or result[0]['lots']!=result[1]['lots'] or result[0]['initial_stop']!=result[1]['initial_stop']:
            raise ValueError('PAIR_ENTRY_STOP_SIZE_MISMATCH')
        for arm,row in enumerate(result):
            row.update(sizing={k:str(v) for k,v in sizing.items()})
            rows[arm].append(row);pending[arm]=row
        counters['accepted_pairs']+=1
        if D(result[1]['target'])%D(management['spec']['tick_size']):
            counters['H1_TARGET_OFF_DECLARED_TICK']+=1
    # Settle only at the observed final close, never earlier than the event.
    boundary=part[-1]['time']+900
    for arm,p in enumerate(pending):
        if p is not None:
            if p['exit_time']>boundary:raise ValueError('EVENT_OUTSIDE_PART')
            if p['net_scenario_usd'] is None:unknown=True
            else:cash[arm]+=D(p['net_scenario_usd'])
    return dict(rows=rows,counters=dict(counters),equity=[str(x) for x in cash],unknown=unknown,
                starting_equity=[str(x) for x in equities],
                mtm=[sampled_mtm(part,rows[a],cost,equities[a]) for a in range(2)])

def parity(engine,parts,runs,costs):
    selected={}
    for run in runs:
        if run['result'] is None or not run['result']['rows']:continue
        key=(run['candidate'],run['cost'])
        if key not in selected:selected[key]=[]
        for tr in run['result']['rows']:
            if tr['reason'] not in {x[1]['reason'] for x in selected[key]}:
                selected[key].append((run['segment'],tr))
    checks=0
    for (candidate,cost),items in selected.items():
        for segment,tr in items:
            p=parts[segment-1];lookup={b['time']:i for i,b in enumerate(p)};i=lookup[tr['entry_time']]
            if tr['signal_time']!=tr['entry_time']:raise ValueError('TRACE_DECISION_CLOCK')
            setup=dict(side=tr['side'],stop_loss=tr['initial_stop'],signal_time=tr['entry_time']-900,candidate=tr['signal_candidate'])
            r=one(engine,p,i,setup,costs[cost],D('.01'),D(10))
            for field in ('entry_time','exit_time','entry','exit','reason','price_exit_reason','net_scenario_usd'):
                if r[field]!=tr[field]:raise ValueError('PARITY_'+field)
            checks+=1
    return checks

def run(a):
    locked=json.loads(a.policy.read_text());frozen=json.loads((a.protocol_dir/'hypotheses-and-future-test-protocol.json').read_text())
    summary=json.loads((a.source/'ff-session-replay-summary.json').read_text())
    enginepath=a.source/'historical_engine.py'
    if sha(enginepath)!=summary['code_hashes']['historical_engine.py']:raise ValueError('ENGINE_HASH_CHANGED')
    for name in ('model.py','strategy.py','analysis.py','risk.py','auto_sizing.py','adaptive_exit.py'):
        if sha(a.strategy_source/'amin_mt5'/name)!=summary['code_hashes']['amin_mt5/'+name]:raise ValueError('STRATEGY_HASH_CHANGED_'+name)
    sys.path[:0]=[str(a.source),str(a.strategy_source)]
    engine=importlib.import_module('historical_engine')
    strategy=importlib.import_module('amin_mt5.strategy')
    management=json.loads((a.source/'management-policy.json').read_text())
    if D(management['policy']['max_order_risk_fraction'])!=D('.005'):raise ValueError('EXISTING_LAB_CAP_CHANGED')
    manifest=json.loads((a.raw_dir/'manifest.json').read_text());raw=[]
    if sha(a.raw_dir/'manifest.json')!=summary['source_manifest_sha256']:raise ValueError('MANIFEST_HASH')
    for c in manifest['chunks'].values():
        if c['kind']!='M15':continue
        for field in ('csv','raw'):
            if sha(a.raw_dir/c[field])!=c[field+'_sha256']:raise ValueError('DATA_HASH')
        raw.extend(csv.DictReader((a.raw_dir/c['csv']).open(encoding='utf-8-sig')))
    bars=engine.canonical_bars(raw,offset_seconds=0,offset_evidence='CONDITIONAL')
    parts=list(engine.segments(bars));selection=json.loads((a.source/'ff-session-replay-selection.json').read_text())
    if len(bars)!=23643 or len(parts)!=261:raise ValueError('DATA_INVENTORY')
    for part,s in zip(parts,selection):
        if engine.sha_bars(part)!=s['sha256']:raise ValueError('SEGMENT_HASH')
    trace_path=a.trace_dir/(summary['identity']+'.json');old=json.loads(trace_path.read_text())
    if digest(old['result'])!=old['result_sha256']:raise ValueError('TRACE_HASH')
    costs=locked['costs']
    parity_count=parity(engine,parts,old['result'],costs)
    full=[];aggregates=[];periods=[]
    for candidate in strategy.candidates():
        for cost,settings in costs.items():
            for cohort in ('independent_segments','continuous_known_prefix'):
                cells=[];equities=[D(10000),D(10000)];blocked=False;blocked_parts=0
                for sid,part in enumerate(parts,1):
                    if len(part)<=max(24,candidate.lookback+2):continue
                    if blocked:blocked_parts+=1;continue
                    starts=[D(10000),D(10000)] if cohort=='independent_segments' else equities
                    cell=pair_part(engine,strategy.plan,candidate,part,settings,management,starts)
                    cell.update(candidate=candidate.id,cost=cost,cohort=cohort,segment=sid,
                                raw_month=datetime.fromtimestamp(part[0]['raw_time'],timezone.utc).strftime('%Y-%m'))
                    cells.append(cell);full.append(cell);equities=list(map(D,cell['equity']))
                    if cohort=='continuous_known_prefix' and cell['unknown']:blocked=True
                arms=[]
                for arm,name in enumerate(('baseline_overlay','H1_1p5R')):
                    rows=[r for c in cells for r in c['rows'][arm]]
                    m=dict(arm=name,**stats(rows))
                    joint_ok=[c for c in cells if not c['unknown']]
                    m.update(joint_fully_resolved_segment_net=str(sum((D(r['net_scenario_usd']) for c in joint_ok for r in c['rows'][arm]),D(0))),
                        closed_dd_worst_segment_usd=str(max((D(dd([D(r['net_scenario_usd']) for r in c['rows'][arm] if r['net_scenario_usd'] is not None],D(c['starting_equity'][arm]))['usd']) for c in cells),default=D(0))),
                        closed_dd_worst_segment_fraction=str(max((D(dd([D(r['net_scenario_usd']) for r in c['rows'][arm] if r['net_scenario_usd'] is not None],D(c['starting_equity'][arm]))['fraction']) for c in cells),default=D(0))),
                        sampled_mtm_dd_worst_segment_fraction=str(max((D(c['mtm'][arm]['sampled_prefix_dd_fraction']) for c in cells),default=D(0))),
                        full_year_net='UNKNOWN' if cohort=='independent_segments' or blocked else m['full_net'],
                        exact_intrabar_mtm_dd='UNMEASURABLE')
                    arms.append(m)
                pairs=[(x,y) for c in cells for x,y in zip(*c['rows'])]
                known=[(x,y) for x,y in pairs if x['net_scenario_usd'] is not None and y['net_scenario_usd'] is not None]
                counters=collections.Counter()
                for c in cells:counters.update(c['counters'])
                aggregates.append(dict(candidate=candidate.id,cost=cost,cohort=cohort,
                    processed_segments=len(cells),blocked_later_segments=blocked_parts,uncertain_segments=sum(c['unknown'] for c in cells),
                    joint_fully_resolved_segments=sum(not c['unknown'] for c in cells),counters=dict(counters),
                    arms=arms,known_matched_pairs=len(known),pair_unknown_count=len(pairs)-len(known),
                    matched_delta_H1_minus_baseline=str(sum((D(y['net_scenario_usd'])-D(x['net_scenario_usd']) for x,y in known),D(0))),
                    paired_delta_distribution=dict(positive=sum(D(y['net_scenario_usd'])>D(x['net_scenario_usd']) for x,y in known),
                        negative=sum(D(y['net_scenario_usd'])<D(x['net_scenario_usd']) for x,y in known),
                        equal=sum(D(y['net_scenario_usd'])==D(x['net_scenario_usd']) for x,y in known)),
                    full_paired_delta=None if any(c['unknown'] for c in cells) else str(sum((D(y['net_scenario_usd'])-D(x['net_scenario_usd']) for x,y in known),D(0)))))
                for month in sorted({c['raw_month'] for c in cells}):
                    subset=[c for c in cells if c['raw_month']==month]
                    periods.append(dict(candidate=candidate.id,cost=cost,cohort=cohort,raw_month=month,
                        uncertain_segments=sum(c['unknown'] for c in subset),
                        arms=[dict(arm=name,**stats([r for c in subset for r in c['rows'][arm]])) for arm,name in enumerate(('baseline_overlay','H1_1p5R'))]))
    a.out.mkdir(parents=True,exist_ok=True);a.private_out.mkdir(parents=True,exist_ok=True)
    tracefile=a.private_out/'h1-paired-trace-PRIVATE.json'
    tracefile.write_text(json.dumps(full,separators=(',',':')),encoding='utf-8')
    result=dict(schema=1,scope=locked['scope'],H2='BLOCKED_SCHEDULE',six_original_FF='STOP',
        fresh_holdout='NO_FRESH_HOLDOUT',market_approval=False,old_baseline_parity_checks=parity_count,
        results=aggregates,monthly=periods,
        limitations=['Common-flat paired eligibility differs from original fixed-lot FF and independently scheduled H1.',
            'Independent segments reset explicitly; their sum is not annual net or account compounding.',
            'Continuous prefix stops at first unresolved; blocked future results are not zeros.',
            'MTM is sampled open/close liquidation under assumed costs, not exact intrabar or broker-real DD.',
            'Exact1.5R may be off declared tick; counted, never silently rounded.'])
    for name,data in [('h1-results.json',result),('h1-summary.json',{k:v for k,v in result.items() if k!='monthly'}),('h1-monthly.json',periods)]:
        (a.out/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    receipt=dict(code_sha256=sha(Path(__file__)),locked_policy_sha256=sha(a.policy),
        prior_hypothesis_protocol_sha256=sha(a.protocol_dir/'hypotheses-and-future-test-protocol.json'),
        frozen_engine_sha256=sha(enginepath),strategy_sha256=sha(a.strategy_source/'amin_mt5/strategy.py'),
        management_policy_sha256=sha(a.source/'management-policy.json'),manifest_sha256=sha(a.raw_dir/'manifest.json'),
        source_trace_sha256=sha(trace_path),private_trace_sha256=sha(tracefile),
        outputs={n:sha(a.out/n) for n in ('h1-results.json','h1-summary.json','h1-monthly.json')},
        original_engine_changed=False,original_strategy_changed=False,new_data_connection=False,orders=0)
    (a.out/'h1-execution-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(dict(parity_checks=parity_count,results=aggregates),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('source','strategy-source','raw-dir','trace-dir','protocol-dir','policy','out','private-out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
