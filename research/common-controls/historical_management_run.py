"""Same authorized observed window, new management dependency only; no downloads."""
import json,hashlib,sys,time
from dataclasses import asdict
from collections import Counter
from decimal import Decimal as D
from historical_windows_run import ROOT,PRIVATE_OUTPUT,POLICY,epoch_utc,load_existing,PRIVATE
from historical_candidates import methods,SOURCE
from historical_engine import canonical_bars,sha_bars,simulate
from historical_management import Management,train_past,UNASSESSED
from registry import digest,Registry

def main():
    baseline=json.loads((ROOT/'historical-windows-summary.json').read_text())
    if baseline['identity']!='07a5996cd4bb0a66d621307eb1bc1739b5c084a0373b1ec23984cba59a9bf1c1':
        raise ValueError('BASELINE_IDENTITY_CHANGED')
    prior=json.loads((PRIVATE_OUTPUT/(baseline['identity']+'.json')).read_text())
    if digest(prior['result'])!=prior['result_sha256']:raise ValueError('BASELINE_TAMPER')
    m=Management()
    policy=dict(window_start=POLICY['window_start'],window_end=POLICY['window_end'],
        initial_capital='10000',initial_capital_basis='ASSUMPTION',policy=asdict(m.policy),
        spec=asdict(m.spec),spec_basis='SOURCE_DEFAULTS_NOT_HISTORICAL_ATTESTATION',
        execution_costs={k:POLICY[k] for k in ('spread','slippage','commission_roundtrip_per_lot')},
        cost_basis='ASSUMPTION',sizing_cost_basis='ORIGINAL_POLICY_CONSERVATIVE_ENVELOPE',
        stop_update='CLOSED_BAR_EFFECTIVE_NEXT_BAR',fixed_target=None,fixed_horizon=None,
        offset_seconds=-7200,time_basis='CONDITIONAL',swap='UNKNOWN',
        train_cutoff=POLICY['window_start'],training='NO_OPTIMIZATION_ON_OBSERVED_DAY')
    p=ROOT/'management-policy.json'
    if p.exists() and json.loads(p.read_text())!=policy:raise ValueError('FROZEN_POLICY_MISMATCH')
    if not p.exists():p.write_text(json.dumps(policy,indent=2),encoding='utf-8')
    files=['historical_engine.py','historical_management.py','historical_management_run.py','historical_candidates.py',
        'historical_windows_run.py','historical_runner.py','offline_evidence.py','registry.py','vendor/research_ledger.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    for f in ('strategy.py','analysis.py','model.py','auto_sizing.py','risk.py','adaptive_exit.py','learning.py'):
        hashes['amin_mt5/'+f]=hashlib.sha256((SOURCE/'amin_mt5'/f).read_bytes()).hexdigest()
    manifest=hashlib.sha256((PRIVATE/'manifest.json').read_bytes()).hexdigest()
    if manifest!=baseline['source_manifest_sha256']:raise ValueError('MANIFEST_CHANGED')
    records,_=load_existing(include_repairs=True)
    start,end=map(epoch_utc,(policy['window_start'],policy['window_end']))
    data=[b for b in canonical_bars(records,offset_seconds=-7200,offset_evidence='CONDITIONAL') if start<=b['time']<end]
    if sha_bars(data)!=baseline['data_sha256'] or len(data)!=88:raise ValueError('WINDOW_CHANGED')
    key=digest(dict(policy=policy,code=hashes,data=sha_bars(data),baseline=baseline['identity']))
    path=PRIVATE_OUTPUT/(key+'.json')
    if path.exists():
        envelope=json.loads(path.read_text());full=envelope['result']
        if envelope['identity']!=key or digest(full)!=envelope['result_sha256']:raise ValueError('RESULT_TAMPER')
        action='REUSE'
    else:
        full={}
        for name,signal in methods().items():
            full[name]={}
            for intrabar in ('stop_first','target_first','unknown'):
                manager=Management()
                result=simulate(data,signal,management=manager,policy=intrabar,**policy['execution_costs'])
                result.update(failures=manager.failures,stage_trace=manager.stage_trace,
                    sampled_equity=manager.sampled_equity,ending_realized_equity=str(manager.equity))
                full[name][intrabar]=result
        path.write_text(json.dumps(dict(identity=key,result_sha256=digest(full),result=full),indent=2),encoding='utf-8')
        action='EXECUTED'
    public={}
    for name,variants in full.items():
        public[name]={}
        for variant,result in variants.items():
            fixed=baseline['results']['existing_six_signals'][name][variant]
            public[name][variant]=dict(fixed_overlay=fixed,risk_aware={k:result[k] for k in
                ('positions','resolved','unresolved','scenario_net_usd','scenario_max_drawdown_usd','known_partial_net_usd','ending_realized_equity')},
                gross_resolved_scenario_usd=str(sum((D(r['gross_scenario_usd']) for r in result['rows'] if r['gross_scenario_usd'] is not None),D(0))),
                trades=[{k:r[k] for k in ('lots','initial_risk_usd','equity_before','gross_scenario_usd','net_scenario_usd','reason','price_exit_reason')} for r in result['rows']],
                failure_counts=dict(Counter(x for f in result['failures'] for x in f['reasons'])),
                stop_updates=sum(len(r['stop_adjustments']) for r in result['rows']),
                trace_sha256=digest(result),mtm_max_drawdown='UNKNOWN_TICK_PATH_AND_QUOTE_UNVERIFIED')
    output=dict(identity=key,action=action,status='EXPLORATORY_ONLY',policy=policy,code_hashes=hashes,
        data_sha256=sha_bars(data),manifest_sha256=manifest,window_bars=len(data),results=public,
        learning=train_past([],start),operational_guards_unassessed=sorted(UNASSESSED),
        financial_approval=False,holdout_certified=False,orders=0,
        broker_modules_loaded=any(x in sys.modules for x in ('MetaTrader5','amin_mt5.mt5')))
    (ROOT/'management-summary.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    bank=Registry(ROOT/'local-research.sqlite')
    bank.discover([dict(id='historical-management:'+key,received_ms=int(time.time()*1000),source='PR32',
        summary_sha256=digest(output),scope='EXPLORATORY_ONLY',financial_approval=False)])
    print(json.dumps(dict(identity=key,action=action,learning=output['learning'],results={n:v['unknown'] for n,v in public.items()})))

if __name__=='__main__':main()
