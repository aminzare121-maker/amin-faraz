"""Inspect existing raw files once, without terminal/network/strategy execution."""
import csv,hashlib,io,json
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from registry import digest
from offline_evidence import load_existing,PRIVATE
from limited_window_gate import evaluate

ROOT=Path(__file__).resolve().parent
DUKA=ROOT.parent/'PRIVATE_DUKASCOPY_SAMPLE'
POLICY=dict(schema=1,selection='Existing comparison dates, split only at observed missing slots; no strategy results',
            windows=['NOV04_00_22','NOV04_23_24','NOV05_00_09','NOV05_TICK_0830_0900'],
            timezone='CONDITIONAL_EXISTING_MINUS7200_NOT_NEW_CERTIFICATE',cost_unknown_is_zero=False)

def main():
    # Fixed policy is persisted before raw inspection. No profitability inputs.
    policy_path=ROOT/'limited-window-policy.json'
    if policy_path.exists() and json.loads(policy_path.read_text())!=POLICY:raise ValueError('FIXED_WINDOW_POLICY_CHANGED')
    if not policy_path.exists():policy_path.write_text(json.dumps(POLICY,indent=2),encoding='utf-8')
    inv=json.loads((ROOT/'data-validity-inventory.json').read_text())
    hashes=[]
    sources=[PRIVATE/'manifest.json',PRIVATE/'boundary-repair/receipt.json']
    sources += [DUKA/(x['contract']['raw_sha256']+'.csv') for x in inv if x['contract']['source']=='Dukascopy']
    for entry,path in zip(inv,sources):
        got=hashlib.sha256(path.read_bytes()).hexdigest()
        if got!=entry['contract']['raw_sha256']:raise ValueError('EXISTING_SOURCE_HASH_MISMATCH')
        hashes.append(dict(source=entry['contract']['source'],kind=entry['contract']['kind'],sha256=got))
    bars,ticks=load_existing(include_repairs=True)  # validates child CSV hashes
    segments=[];segment=[]
    for bar in bars:
        if segment and int(bar['time'])-int(segment[-1]['time'])!=900:
            segments.append(segment);segment=[]
        segment.append(bar)
    if segment:segments.append(segment)
    utc=lambda x:int(datetime.fromisoformat(x.replace('Z','+00:00')).timestamp())
    intervals=[('NOV04_00_22','2026-11-04T00:00:00Z','2026-11-04T22:00:00Z'),
               ('NOV04_23_24','2026-11-04T23:00:00Z','2026-11-05T00:00:00Z'),
               ('NOV05_00_09','2026-11-05T00:00:00Z','2026-11-05T09:00:00Z'),
               ('NOV05_TICK_0830_0900','2026-11-05T08:30:00Z','2026-11-05T09:00:00Z')]
    evidence_files=['terminal-clock-sanitized.json','tick-side-after-repair.json','real-comparison-sanitized.json',
                    'comparison-nov05-sanitized.json','data-validity-inventory.json','limited-window-rights-receipt.json']
    receipts={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in evidence_files}
    results=[]
    for name,a,b in intervals:
        start,end=utc(a),utc(b)
        selected=[r for r in bars if start<=int(r['time'])-7200<end]
        selected_ticks=[r for r in ticks if start*1000<=int(r['time_msc'])-7200000<end*1000]
        times=[int(r['time'])-7200 for r in selected]
        missing=sorted(set(range(start,end,900))-set(times))
        valid_ohlc=all(all(D(r[k]).is_finite() and D(r[k])>0 for k in ('open','high','low','close')) and
                       D(r['low'])<=min(D(r['open']),D(r['close']))<=max(D(r['open']),D(r['close']))<=D(r['high']) for r in selected)
        observed=dict(status='VERIFIED',receipt_sha256=digest(selected),start=start,end=end)
        evidence={
            'rights':dict(status='VERIFIED',start=start,end=end,receipt_sha256=receipts['limited-window-rights-receipt.json'],reason='Eplanet ticket207852 and owner authorization: existing private research only; no raw redistribution'),
            'clock':dict(status='CONDITIONAL',reason='Existing same-day live offset and winter support statement; not exact window attestation',receipt_sha256=receipts['terminal-clock-sanitized.json']),
            'session':dict(status='UNKNOWN',reason='No dated broker symbol session receipt; observed continuous quotes are not a full session calendar'),
            'ohlc':observed if valid_ohlc and len(times)==len(set(times)) and selected else dict(status='UNKNOWN'),
            'price_side':dict(status='CONDITIONAL',reason='BID chart mode and two repaired tick bars corroborate Bid; only sampled period'),
            'contract':dict(status='CONDITIONAL',reason='Support:100oz,.01tick,1USD per lot tick; no dated full-window execution receipt'),
            'costs':dict(status='UNKNOWN',reason='Commission zero stated; Bid/Ask only30min; historical slippage bounds and rollover history absent'),
            'execution':dict(status='UNKNOWN',reason='Tick path only30min; M15 assumptions do not prove fills')}
        window=dict(id=name,start=start,end=end,start_label=a,end_label=b,
                    labels='CONDITIONAL_UTC_FROM_EXISTING_SAMPLE_MAPPING',m15=len(selected),ticks=len(selected_ticks),
                    sample_hash=digest(selected),tick_sample_hash=digest(selected_ticks),missing_slots=len(missing),
                    duplicate_times=len(times)-len(set(times)),evidence=evidence,exposure='PREVIOUSLY_OBSERVED_DIAGNOSTIC',
                    rollback='ROLLBACK_PROTECTION_UNVERIFIED',engine_ready=False,
                    engine_blockers=['Current selector accepts synthetic scope only','Current split runner needs >=240 bars; historical-session gaps adapter absent'])
        results.append(dict(window=window,diagnostic_gate=evaluate(window),sealed_gate=evaluate(window,mode='SEALED_HOLDOUT')))
    report=dict(schema=1,policy_sha=digest(POLICY),raw_rows=dict(m15=len(bars),ticks=len(ticks)),source_hashes=hashes,
                evidence_hashes=receipts,windows=results,counts=dict(eligible=sum(r['diagnostic_gate']['status']=='LOCAL_WINDOW_ELIGIBLE' for r in results),
                exploratory=len(results),blocked_backtests=len(results)),historical_backtests_executed=0,
                financial_metrics=None,annual_gaps_unknown=260,downloaded_rows=0,raw_modified=False,
                year_inventory=dict(continuous_observed_segments=len(segments),
                    largest_segment_bars=max(map(len,segments)),segments_at_least_240_bars=sum(len(s)>=240 for s in segments),
                    all_segment_timestamp_interpretations='RAW_SERVER_UNATTESTED',
                    source_rows_covered=sum(map(len,segments)),classification='NO_ADDITIONAL_DATED_CLOCK_SESSION_EVIDENCE_AVAILABLE'),
                note='Four overlapping evidence windows, not four independent experiments. Other annual segments have no independent dated clock/session certificate; no PnL used for selection.')
    (ROOT/'limited-window-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'rows':report['raw_rows'],'counts':report['counts'],'windows':[(r['window']['id'],r['window']['m15'],r['window']['ticks'],r['window']['missing_slots']) for r in results]}))

if __name__=='__main__':main()
