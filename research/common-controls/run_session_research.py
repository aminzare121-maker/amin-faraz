"""Frozen full-inventory study. Every segment retained; no annual equity claim."""
import json,hashlib,time
from decimal import Decimal as D
from collections import Counter
from historical_windows_run import ROOT,PRIVATE_OUTPUT,load_existing,PRIVATE
from historical_candidates import SOURCE
from historical_engine import canonical_bars,segments,sha_bars,simulate
from session_research import SessionManagement,raw_signal,candidates,assess_gap
from registry import digest,Registry

POLICY=dict(schema=1,time_basis='RAW_LABEL_UNVERIFIED_NO_OFFSET',
    risk_day='INDEPENDENT_SESSION_SCENARIO_DAY_2000_01_01_TEHRAN_NOT_HISTORICAL_MAPPING',
    select='ALL_MAXIMAL_CONTIGUOUS_PARTS; eligible iff len>max(24,lookback+2)',
    initial_capital='10000',initial_exposure='FLAT_ASSUMPTION_PER_SEGMENT',
    costs={'base':dict(spread='.3',slippage='.1',commission_roundtrip_per_lot='0'),
        'envelope':dict(spread='.50',slippage='.20',commission_roundtrip_per_lot='10')},
    cost_basis='ASSUMPTION',sizing_envelope='UNCHANGED_ORIGINAL_POLICY',
    intrabar='unknown',exit='ORIGINAL_ADAPTIVE_CLOSE_ONLY_NO_TARGET_NO_HORIZON',
    uncertainty='RAW_MIDNIGHT_SWAP_UNKNOWN; unresolved blocks net and further positions',
    gap_labels_never_authorize_carry=True,fit=False,fresh_holdout=False)

def frozen(p,x):
    if p.exists() and json.loads(p.read_text())!=x:raise ValueError('FROZEN_MISMATCH')
    if not p.exists():p.write_text(json.dumps(x,indent=2),encoding='utf-8')

def main(mode='VA'):
    if mode not in ('FF','VA'):raise ValueError('MODE')
    prefix='ff-session' if mode=='FF' else 'session'
    active_policy=dict(POLICY,mode=mode)
    if mode=='FF':active_policy.update(risk_day='NOT_USED_FIXED_VOLUME',exit='EXISTING_FIXED_TARGET_10_HORIZON_12_LOT_0.01')
    frozen(ROOT/(prefix+'-replay-policy.json'),active_policy)
    bars,_=load_existing(include_repairs=True)
    data=canonical_bars(bars,offset_seconds=0,offset_evidence='CONDITIONAL')
    parts=list(segments(data))
    selection=[dict(id=i+1,first_raw=p[0]['raw_time'],last_raw=p[-1]['raw_time'],bars=len(p),sha256=sha_bars(p)) for i,p in enumerate(parts)]
    frozen(ROOT/(prefix+'-replay-selection.json'),selection)
    old=json.loads((ROOT/'session-coverage-audit.json').read_text())
    if len(data)!=23643 or len(parts)!=261:raise ValueError('INVENTORY_CHANGED')
    manifest=hashlib.sha256((PRIVATE/'manifest.json').read_bytes()).hexdigest()
    if manifest!=old['source_manifest_sha256']:raise ValueError('MANIFEST_CHANGED')
    files=['historical_engine.py','historical_management.py','session_research.py','run_session_research.py','historical_candidates.py','offline_evidence.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    for f in ('model.py','strategy.py','analysis.py','risk.py','auto_sizing.py','adaptive_exit.py'):
        hashes['amin_mt5/'+f]=hashlib.sha256((SOURCE/'amin_mt5'/f).read_bytes()).hexdigest()
    key=digest(dict(policy=active_policy,selection=selection,code=hashes,manifest=manifest))
    path=PRIVATE_OUTPUT/(key+'.json')
    if path.exists():
        e=json.loads(path.read_text());full=e['result']
        if e['identity']!=key or e['result_sha256']!=digest(full):raise ValueError('CACHE_TAMPER')
        action='REUSED'
    else:
        full=[]
        for i,part in enumerate(parts):
            for c in candidates():
                for cost,settings in POLICY['costs'].items():
                    row=dict(segment=i+1,candidate=c.id,cost=cost)
                    if len(part)<=max(24,c.lookback+2):row.update(status='INSUFFICIENT_WARMUP',result=None)
                    else:
                        manager=SessionManagement(part[0]['time']) if mode=='VA' else None
                        signal=raw_signal(c);counts={'calls':0,'signals':0}
                        def observed(history):
                            counts['calls']+=1;answer=signal(history)
                            if answer is not None:counts['signals']+=1
                            return answer
                        r=simulate(part,observed,management=manager,policy='unknown',**settings)
                        r['failures']=manager.failures if manager else []
                        r['signal_counts']=counts
                        row.update(status='EXPLORATORY_ONLY',result=r)
                    full.append(row)
            if (i+1)%50==0:print(json.dumps({'completed_segments':i+1}),flush=True)
        path.write_text(json.dumps(dict(identity=key,result_sha256=digest(full),result=full),separators=(',',':')),encoding='utf-8')
        action='EXECUTED'
    public=[]
    for row in full:
        p=selection[row['segment']-1];r=row['result']
        rawlabel=old['windows'][row['segment']-1]['first_raw_label']
        out=dict(segment=row['segment'],month_raw=rawlabel[:7],first_raw_label=rawlabel,candidate=row['candidate'],cost=row['cost'],status=row['status'])
        if r is not None:
            nets=[D(x['net_scenario_usd']) for x in r['rows'] if x['net_scenario_usd'] is not None]
            out.update(positions=r['positions'],resolved=r['resolved'],unresolved=r['unresolved'],
                net_complete=r['scenario_net_usd'],known_partial=r['known_partial_net_usd'],closed_dd=r['scenario_max_drawdown_usd'],
                wins=sum(v>0 for v in nets),losses=sum(v<0 for v in nets),no_signal=r['positions']==0,signals=r['signal_counts']['signals'],
                vetoes=dict(Counter(x for f in r['failures'] for x in f['reasons'])),trace_sha256=digest(r))
        public.append(out)
    summary=[]
    for c in candidates():
        for cost in POLICY['costs']:
            for month in ['ALL']+sorted({x['month_raw'] for x in public}):
                rows=[x for x in public if x['candidate']==c.id and x['cost']==cost and (month=='ALL' or x['month_raw']==month)]
                run=[x for x in rows if x['status']=='EXPLORATORY_ONLY']
                summary.append(dict(candidate=c.id,cost=cost,month_raw=month,total_segments=len(rows),eligible=len(run),
                    skipped=len(rows)-len(run),signals=sum(x['signals'] for x in run),positions=sum(x['positions'] for x in run),resolved=sum(x['resolved'] for x in run),
                    unresolved=sum(x['unresolved'] for x in run),wins=sum(x['wins'] for x in run),losses=sum(x['losses'] for x in run),
                    no_signal_segments=sum(x['no_signal'] for x in run),
                    net_unknown_segments=sum(x['unresolved']>0 for x in run),fully_resolved_segments=sum(x['unresolved']==0 for x in run),
                    sum_net_fully_resolved_segments=str(sum((D(x['net_complete']) for x in run if x['net_complete'] is not None),D(0))),
                    sum_known_partial_net=str(sum((D(x['known_partial']) for x in run),D(0))),
                    complete_aggregate_net=None if any(x['unresolved'] for x in run) else str(sum((D(x['known_partial']) for x in run),D(0))),
                    continuous_equity='NO_RESULT',mtm_dd='UNKNOWN',no_trade_baseline='0',
                    worst_closed_dd_among_fully_resolved_segments=str(max((D(x['closed_dd']) for x in run if x['closed_dd'] is not None),default=D(0)))))
    out=dict(identity=key,mode=mode,action=action,policy_sha256=digest(active_policy),selection_sha256=digest(selection),
        source_manifest_sha256=manifest,code_hashes=hashes,rows=summary,
        eligible_candidate_cost_runs=sum(x['status']=='EXPLORATORY_ONLY' for x in public),
        skipped_candidate_cost_cells=sum(x['status']!='EXPLORATORY_ONLY' for x in public),financial_approval=False)
    (ROOT/(prefix+'-replay-summary.json')).write_text(json.dumps(out,indent=2),encoding='utf-8')
    (ROOT/(prefix+'-replay-by-segment.json')).write_text(json.dumps(public,separators=(',',':')),encoding='utf-8')
    gaps=[assess_gap(g) for g in json.loads((ROOT/'gap-classifications-v3.json').read_text())]
    (ROOT/'gap-classifications-v4.json').write_text(json.dumps(gaps,separators=(',',':')),encoding='utf-8')
    Registry(ROOT/'local-research.sqlite').discover([dict(id='sessions:'+key,source='PR32',received_ms=int(time.time()*1000),
        report_sha256=digest(out),financial_approval=False,scope='EXPLORATORY_ONLY_INDEPENDENT_SESSIONS')])
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','code_hashes')}))
    print(json.dumps([x for x in summary if x['month_raw']=='ALL']))

if __name__=='__main__':main()
