"""Versioned evidence audit, no download and no price-based clock fitting."""
import json,hashlib,io,unittest
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from decimal import Decimal
from evidence_gates import classify_gap,final_gate

ROOT=Path(__file__).resolve().parent
def ts(s):return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
def label(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
start,end=ts('2025-11-05T00:00:00Z'),ts('2026-11-05T00:00:00Z')
ny_start,ny_end=ts('2026-03-08T07:00:00Z'),ts('2026-11-01T06:00:00Z')
eu_start,eu_end=ts('2026-03-29T01:00:00Z'),ts('2026-10-25T01:00:00Z')
bounds=sorted([start,ny_start,ny_end,eu_start,eu_end,end]);periods=[]
for a,b in zip(bounds,bounds[1:]):
    mid=(a+b)//2;ny=10800 if ny_start<=mid<ny_end else 7200;eu=10800 if eu_start<=mid<eu_end else 7200
    periods.append({'utc_start':a,'utc_end':b,'start_label':label(a),'end_label':label(b),
        'candidate_ny_offset':ny,'candidate_eu_offset':eu,'candidates_agree':ny==eu,
        'status':'UNKNOWN','unknown':True,'confidence':'CANDIDATE_AGREEMENT_ONLY' if ny==eu else 'CONFLICTING_RULES',
        'evidence_ids':['NIST_DST_2026','EU_COUNCIL_RULE','EPLANET_207852_AMBIGUOUS_STATEMENT'],
        'offset_seconds':None,'approved_for_final_backtest':False})
gaps=json.loads((ROOT/'gap-classifications.json').read_text());qa=[]
for g in gaps:
    c=classify_gap(g['start_raw_epoch'],g['end_raw_epoch_exclusive'],[],{})
    dt=datetime.fromtimestamp(g['start_raw_epoch'],timezone.utc)
    qa.append({**g,'classification':c['classification'],'classification_basis':'NO_DATED_EPLANET_SCHEDULE',
        'raw_label_weekday':dt.strftime('%A'),'raw_label_hour':dt.hour,'duration_seconds':g['end_raw_epoch_exclusive']-g['start_raw_epoch'],
        'slot_counts':dict(Counter(s['class'] for s in c['slots']))})
transition_windows=[]
for name,t in [('NY_START',ny_start),('EU_START',eu_start),('EU_END',eu_end),('NY_END',ny_end)]:
    near=[g for g in gaps if abs(g['start_raw_epoch']-t)<7*86400]
    transition_windows.append({'candidate_transition':name,'candidate_utc':label(t),
        'raw_gap_labels_near_transition':[{'start':g['start_label_no_shift'],'end':g['end_label_no_shift'],'slots':g['absent_m15_slots']} for g in near],
        'tick_evidence_available':False,'can_discriminate_broker_dst_rule':False,
        'reason':'Session labels alone cannot anchor UTC; Tick sample only Nov05; no historical broker calendar.'})
stream=io.StringIO()
# Final delta run: only changed scenario/time tests. Existing bridge regression passed 9/9 earlier.
suite=unittest.defaultTestLoader.loadTestsFromName('test_stage3')
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(ROOT/'stage3-test-results.txt').write_text(stream.getvalue(),encoding='utf-8')
report={'schema':'quality-v3','input_gap_report_sha256':hashlib.sha256((ROOT/'gap-classifications.json').read_bytes()).hexdigest(),
    'periods':periods,'transition_windows':transition_windows,'gap_counts':dict(Counter(g['classification'] for g in qa)),
    'source_inventory':{'official_historical_eplanet_calendar':False,'official_historical_eplanet_offset_table':False,
        'support_current_general_statement':True,'live_clock_observation_nov05':True,'tick_sample_nov05_repaired':True,
        'generic_ny_eu_rules_are_not_broker_proof':True},
    'final_gate':final_gate(periods,qa,False,{},start,end),
    'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
    'new_tests':32,'affected_existing_bridge_tests_previously_passed':9,'market_strategy_runs':0,'downloads':0,
    'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/x for x in ('evidence_gates.py','execution_scenarios.py','engine_bridge.py','test_stage3.py','stage3_qa.py')]}}
(ROOT/'stage3-quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'gap-classifications-v3.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
diff_path=ROOT.parent/'PRIVATE_DUKASCOPY_SAMPLE'/'nov04-per-bar-differences.json'
diffs=json.loads(diff_path.read_text());hourly=[]
for hour in range(24):
    values=[r for r in diffs if datetime.fromtimestamp(r['time'],timezone.utc).hour==hour]
    if not values:continue
    closes=[abs(Decimal(r['close'])) for r in values]
    hourly.append({'hour_utc':hour,'bars':len(values),'mean_abs_close_usd_oz':str(sum(closes)/len(closes)),
        'max_abs_high_usd_oz':str(max(abs(Decimal(r['high'])) for r in values))})
hour_report={'source_difference_sha256':hashlib.sha256(diff_path.read_bytes()).hexdigest(),'new_downloads':0,
    'scope':'SINGLE_DAY_2026_11_04_CONDITIONAL_CLOCK_MAPPING','hourly':hourly,
    'largest_high_difference_time_utc':label(max(diffs,key=lambda r:abs(Decimal(r['high'])))['time']),
    'causal_market_condition':'UNKNOWN_NO_EVENT_OR_LIQUIDITY_PROOF','arbitrage_or_signal':False}
(ROOT/'comparison-by-hour.json').write_text(json.dumps(hour_report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('periods','transition_windows','source_sha256')},indent=2))
print(json.dumps({'top_close_difference_hours':sorted(hourly,key=lambda r:Decimal(r['mean_abs_close_usd_oz']),reverse=True)[:3],
    'max_high_time':hour_report['largest_high_difference_time_utc']},indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
