"""Owner-authorized Nov04 diagnostic. Persist raw-derived traces ONLY privately."""
import hashlib,json
from pathlib import Path
from decimal import Decimal as D
from dataclasses import asdict
from historical_engine import canonical_bars,simulate,sma_cross_signal,sha_bars
from historical_runner import one_signal,epoch_utc
from historical_candidates import methods,candidates,SOURCE
from offline_evidence import load_existing,PRIVATE
from registry import digest

ROOT=Path(__file__).resolve().parent
PRIVATE_OUTPUT=ROOT.parent/'PRIVATE_HISTORICAL_DIAGNOSTIC'
POLICY=dict(schema=1,window_start='2026-11-04T00:00:00Z',window_end='2026-11-04T22:00:00Z',
    offset_seconds=-7200,time_evidence='CONDITIONAL',spread='0.3',slippage='0.1',commission_roundtrip_per_lot='0',
    lots='0.01',contract='100',stop_distance='5',target_distance='10',max_holding_bars=12,
    rollover_exposure='UNKNOWN',policies=['stop_first','target_first','unknown'],
    candidate_definitions=[asdict(c) for c in candidates()],
    note='Original six entry rules and original stop; diagnostic fixed lot/target/horizon, NOT full production sizing/adaptive exit.')

def main():
    policy_path=ROOT/'historical-windows-policy.json'
    if policy_path.exists() and json.loads(policy_path.read_text())!=POLICY:raise ValueError('FROZEN_POLICY_MISMATCH')
    if not policy_path.exists():policy_path.write_text(json.dumps(POLICY,indent=2),encoding='utf-8')
    files=['historical_engine.py','historical_runner.py','historical_candidates.py','historical_windows_run.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    for f in ('strategy.py','analysis.py','model.py'):hashes['amin_mt5/'+f]=hashlib.sha256((SOURCE/'amin_mt5'/f).read_bytes()).hexdigest()
    manifest_sha=hashlib.sha256((PRIVATE/'manifest.json').read_bytes()).hexdigest()
    expected=json.loads((ROOT/'data-validity-inventory.json').read_text())[0]['contract']['raw_sha256']
    if manifest_sha!=expected:raise ValueError('MANIFEST_CHANGED')
    bars,_=load_existing(include_repairs=True)
    converted=canonical_bars(bars,offset_seconds=-7200,offset_evidence='CONDITIONAL')
    start,end=epoch_utc(POLICY['window_start']),epoch_utc(POLICY['window_end'])
    selected=[b for b in converted if start<=b['time']<end]
    identity=digest(dict(policy=POLICY,code=hashes,data=sha_bars(selected),manifest_sha=manifest_sha))
    PRIVATE_OUTPUT.mkdir(exist_ok=True)
    full_path=PRIVATE_OUTPUT/(identity+'.json')
    if full_path.exists():
        envelope=json.loads(full_path.read_text())
        full=envelope['result']
        if envelope['identity']!=identity or envelope['result_sha256']!=digest(full):raise ValueError('PRIVATE_RESULT_TAMPER')
        action='REUSED_PRIVATE_DIAGNOSTIC'
    else:
        full={}
        groups={'baselines':{'SMA_5_20':sma_cross_signal,'buy_after21':one_signal('buy'),'sell_after21':one_signal('sell')},'existing_six_signals':methods()}
        for group,signals in groups.items():
            full[group]={}
            for name,signal in signals.items():
                full[group][name]={}
                for policy in POLICY['policies']:
                    calls={'opportunities':0,'signals':0}
                    def observed(history):
                        calls['opportunities']+=1;r=signal(history)
                        if r is not None:calls['signals']+=1
                        return r
                    r=simulate(selected,observed,spread=POLICY['spread'],slippage=POLICY['slippage'],
                        commission_roundtrip_per_lot=POLICY['commission_roundtrip_per_lot'],
                        lots=POLICY['lots'],target_distance=POLICY['target_distance'],max_holding_bars=POLICY['max_holding_bars'],
                        rollover_exposure='UNKNOWN',policy=policy)
                    r['signal_counts']=calls;full[group][name][policy]=r
        full_path.write_text(json.dumps(dict(identity=identity,result_sha256=digest(full),result=full),indent=2),encoding='utf-8');action='EXECUTED'
    summaries={}
    for group,results in full.items():
        summaries[group]={}
        for name,policies in results.items():
            summaries[group][name]={}
            for policy,r in policies.items():
                values=[D(x['net_scenario_usd']) for x in r['rows'] if x['net_scenario_usd'] is not None]
                wins=sum(x>0 for x in values)
                summaries[group][name][policy]={**{k:r[k] for k in ('positions','resolved','unresolved','scenario_net_usd','scenario_max_drawdown_usd','known_partial_net_usd','signal_counts')},
                    'resolved_win_rate':str(D(wins)/len(values)) if values else None,
                    'trace_sha256':digest(r['rows'])}
    out=dict(schema=1,status='EXPLORATORY_ONLY',action=action,identity=identity,policy=POLICY,
        code_hashes=hashes,source_manifest_sha256=manifest_sha,data_sha256=sha_bars(selected),
        rows_loaded=len(bars),window_bars=len(selected),segments=1 if selected else 0,
        results=summaries,financial_profitability_verified=False,holdout_certified=False,orders=0,
        no_trade_baseline_usd='0',raw_or_prices_published=False)
    (ROOT/'historical-windows-summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps({'window_bars':len(selected),'identity':identity,'results':summaries}))

if __name__=='__main__':main()
