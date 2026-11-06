"""Frozen 2x2 observed-window diagnostic; private traces, public aggregates only."""
import json,hashlib,time
from decimal import Decimal as D
from collections import Counter
from historical_windows_run import ROOT,PRIVATE_OUTPUT,PRIVATE,epoch_utc,load_existing
from historical_candidates import SOURCE,methods
from historical_engine import canonical_bars,sha_bars,simulate,sma_cross_signal
from factorial_controls import control,matched,validate_windows
from registry import digest,Registry

POLICY=dict(schema=1,modes=['FF','VF','FA','VA'],policies=['stop_first','target_first','unknown'],
    costs=dict(spread='0.3',slippage='0.1',commission_roundtrip_per_lot='0'),
    initial_capital='10000',fixed_lots='0.01',fixed_target_distance='10',fixed_horizon=12,
    risk_envelope='ORIGINAL_DEFAULT_POLICY_COMMISSION_10_SLIPPAGE_0.2',
    windows=[dict(id='observed-Nov04',start=1793750400,end=1793829600),
             dict(id='observed-Nov05',start=1793836800,end=1793869200)],
    clock='CONDITIONAL_MINUS7200_ONLY_THESE_TWO_WINDOWS_NOT_YEAR',
    selection='Previously documented Nov04 00-22 and Nov05 00-09; fixed before new PnL; no overlap',
    warmup='Original plan per segment; no fabricated history',
    capital_scope='Each window isolated flat-start ASSUMPTION, NOT continuous portfolio or proven overnight liquidation',
    unseen_holdout=False,training=False,sensitivity='NONE; keep prior costs unchanged')

def frozen(path,value):
    if path.exists():
        if json.loads(path.read_text())!=value:raise ValueError('FROZEN_POLICY_OR_DATA_CHANGED')
    else:path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def cached(identity):
    e=json.loads((PRIVATE_OUTPUT/(identity+'.json')).read_text())
    if e['identity']!=identity or digest(e['result'])!=e['result_sha256']:raise ValueError('CACHE_TAMPER')
    return e['result']

def summarize(r):
    values=[D(x['net_scenario_usd']) for x in r['rows'] if x['net_scenario_usd'] is not None]
    eq=D('10000');trades=[]
    for x in r['rows']:
        # Legacy trace lacks sizing risk; derive envelope, NOT a broker estimate.
        risk=x.get('initial_risk_usd')
        if risk is None:risk=str((abs(D(x['entry'])-D(x['stop']))+D('.2'))*100*D(x['lots'])+10*D(x['lots']))
        trades.append({**{k:x[k] for k in ('lots','gross_scenario_usd','net_scenario_usd','reason')},
            'capital_before':x.get('equity_before') or str(eq),'initial_risk_envelope':risk})
        if x['net_scenario_usd'] is not None:eq+=D(x['net_scenario_usd'])
    return dict(**{k:r[k] for k in ('positions','resolved','unresolved','scenario_net_usd','scenario_max_drawdown_usd','known_partial_net_usd')},
        wins=sum(x>0 for x in values),losses=sum(x<0 for x in values),flat=sum(x==0 for x in values),
        return_fraction=None if r['scenario_net_usd'] is None else str(D(r['scenario_net_usd'])/10000),
        no_signal=r['positions']==0,no_trade_baseline='0',trades=trades,
        stop_updates=sum(len(x.get('stop_adjustments',[])) for x in r['rows']),
        vetoes=dict(Counter(x for f in r.get('failures',[]) for x in f['reasons'])),
        mtm_drawdown='UNKNOWN',trace_sha256=digest(r))

def main():
    validate_windows(POLICY['windows']);frozen(ROOT/'factorial-policy.json',POLICY)
    old=json.loads((ROOT/'historical-windows-summary.json').read_text())
    managed=json.loads((ROOT/'management-summary.json').read_text())
    for name,expected in managed['code_hashes'].items():
        if name.startswith('amin_mt5/') and hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('ORIGINAL_SOURCE_CHANGED')
    if hashlib.sha256((PRIVATE/'manifest.json').read_bytes()).hexdigest()!=old['source_manifest_sha256']:raise ValueError('RAW_MANIFEST_CHANGED')
    records,_=load_existing(include_repairs=True)
    # Inventory uses RAW labels only. No inferred UTC offset for other dates.
    times=sorted(int(b['time']) for b in records)
    gaps=sum(b-a!=900 for a,b in zip(times,times[1:]))
    windows={}
    for w in POLICY['windows']:
        raw=[b for b in records if w['start']+7200<=int(b['time'])<w['end']+7200]
        data=canonical_bars(raw,offset_seconds=-7200,offset_evidence='CONDITIONAL')
        if len(data)!=(w['end']-w['start'])//900 or any(b['time']-a['time']!=900 for a,b in zip(data,data[1:])):
            raise ValueError('FROZEN_WINDOW_GAP_OR_COUNT')
        windows[w['id']]=data
    if sha_bars(windows['observed-Nov04'])!=old['data_sha256']:raise ValueError('NOV04_CHANGED')
    selection=dict(policy_sha256=digest(POLICY),raw_rows=len(records),raw_gaps=gaps,
        windows=[dict(w,bars=len(windows[w['id']]),data_sha256=sha_bars(windows[w['id']]),missing=0,
            clock='CONDITIONAL',session='UNKNOWN',costs='ASSUMPTION',holdout='OBSERVED_NOT_FRESH') for w in POLICY['windows']],
        annual_result='NO_RESULT_HISTORICAL_OFFSET_AND_SESSION_UNPROVEN')
    frozen(ROOT/'factorial-selection.json',selection)  # BEFORE any new replay
    files=['historical_engine.py','historical_management.py','historical_candidates.py','factorial_controls.py','factorial_run.py',
        'historical_windows_run.py','offline_evidence.py','registry.py','vendor/research_ledger.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    hashes.update({k:v for k,v in managed['code_hashes'].items() if k.startswith('amin_mt5/')})
    key=digest(dict(policy=POLICY,selection=selection,code=hashes,old=old['identity'],managed=managed['identity']))
    output_path=PRIVATE_OUTPUT/(key+'.json')
    if output_path.exists():full=cached(key);action='REUSE'
    else:
        legacy=cached(old['identity'])
        before_factorial=cached('81a11e869cb5c6a842baa13729263d963bf41f55295dc96d84f7bedea838dbb1')
        full={}
        for wid,data in windows.items():
            full[wid]={}
            for name,signal in methods().items():
                full[wid][name]={}
                for mode in POLICY['modes']:
                    full[wid][name][mode]={}
                    for intrabar in POLICY['policies']:
                        if mode=='FF':r=before_factorial[wid][name][mode][intrabar]
                        else:
                            m=control(mode)
                            r=simulate(data,signal,management=m,policy=intrabar,**POLICY['costs'])
                            r['failures']=m.failures if m else []
                        full[wid][name][mode][intrabar]=r
            full[wid]['baseline_SMA']=before_factorial[wid]['baseline_SMA']
        output_path.write_text(json.dumps(dict(identity=key,result_sha256=digest(full),result=full),indent=2),encoding='utf-8')
        action='REEXECUTED_MANAGEMENT_DEPENDENCIES_ONLY_FIXED_AND_BASELINE_REUSED'
    summaries={};matches={}
    for wid,results in full.items():
        summaries[wid]={};matches[wid]={}
        for name,grid in results.items():
            if name=='baseline_SMA':summaries[wid][name]={p:summarize(r) for p,r in grid.items()};continue
            summaries[wid][name]={mode:{p:summarize(r) for p,r in vals.items()} for mode,vals in grid.items()}
            matches[wid][name]={}
            for a,b in [('FF','VF'),('FF','FA'),('VF','VA'),('FA','VA')]:
                matches[wid][name][a+'-'+b]={p:matched(grid[a][p],grid[b][p]) for p in POLICY['policies']}
    report=dict(identity=key,action=action,status='EXPLORATORY_ONLY',policy=POLICY,selection=selection,
        hashes=hashes,results=summaries,matched_entries=matches,financial_approval=False,orders=0,
        learning='NO_TRAIN',continuous_portfolio='BLOCKED_UNRESOLVED_OVERNIGHT_EXPOSURE',
        annual='NO_RESULT',operational_guards='MARGIN_NEWS_SESSION_RECONCILIATION_UNASSESSED')
    (ROOT/'factorial-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    Registry(ROOT/'local-research.sqlite').discover([dict(id='factorial:'+key,received_ms=int(time.time()*1000),source='PR32',
        report_sha256=digest(report),scope='EXPLORATORY_ONLY',financial_approval=False)])
    print(json.dumps(dict(identity=key,action=action,windows=selection['windows'],
        nets={w:{n:{m:v['unknown']['scenario_net_usd'] for m,v in g.items()} for n,g in r.items() if n!='baseline_SMA'} for w,r in summaries.items()})))

if __name__=='__main__':main()
