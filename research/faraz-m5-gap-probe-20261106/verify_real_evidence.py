"""Offline verification of private Eplanet exports; publishes counts, never OHLC.
Reuses PR34 parsing/aggregation. No terminal imports or network operations.
"""
import argparse,collections,csv,hashlib,json
from pathlib import Path
from datetime import timedelta
import faraz_m5_audit as audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(old_dir,export_dir,gaps_path,out):
    receipt=json.loads((export_dir/'receipt.json').read_text())
    if not receipt['expansion_gate'] or not receipt['same_existing_process'] or receipt['account_mode']!='DEMO':
        raise ValueError('REAL_PROVENANCE_GATE_FAILED')
    old={}
    for item in receipt['old_sources']:
        p=old_dir/item['name']
        if sha(p)!=item['sha256']:raise ValueError('OLD_SOURCE_HASH_CHANGED')
        for t,b in audit.load_bars(p,'XAUUSD.st',15).items():
            if t in old and old[t]!=b:raise ValueError('OLD_DUPLICATE_CONFLICT')
            old[t]=b
    for item in receipt['chunks']:
        if item['rows'] is not None and sha(export_dir/(item['key']+'.bin'))!=item['sha256']:
            raise ValueError('NEW_SOURCE_HASH_CHANGED')
    new=audit.load_bars(export_dir/'M15.csv','XAUUSD.st',15)
    m5=audit.load_bars(export_dir/'M5.csv','XAUUSD.st',5)
    months=collections.defaultdict(collections.Counter)
    for t,b in old.items():
        counts=months[t.strftime('%Y-%m')]
        counts['old_bars']+=1
        same=t in new and audit.matched(b,new[t],audit.Decimal('0'))
        counts['new_m15_exact_match']+=int(same)
        agg=audit.aggregate(t,m5)
        counts['m5_complete']+=int(agg is not None)
        counts['m5_exact_match']+=int(agg is not None and audit.matched(b,agg,audit.Decimal('0')))
    old_missing=sum(t not in new for t in old)
    old_mismatch=sum(t in new and not audit.matched(b,new[t],audit.Decimal('0')) for t,b in old.items())
    agg_mismatch=sum(v['m5_complete']-v['m5_exact_match'] for v in months.values())
    if old_missing or old_mismatch or agg_mismatch:raise ValueError('FULL_YEAR_ALIGNMENT_FAILED')
    gaps=audit.gaps_from_csv(gaps_path)
    if len(gaps)!=11397 or len({g for g,t in gaps})!=260 or len({t for g,t in gaps})!=11397:
        raise ValueError('ORIGINAL_GAP_INVENTORY_MISMATCH')
    if set(t for _,t in gaps)&old.keys():raise ValueError('GAP_OVERLAPS_OLD_DATA')
    derived=audit.gaps_from_m15(old)
    if set(gaps)!=set(derived):raise ValueError('ORIGINAL_GAPS_DIFFER_FROM_OLD_M15')
    per_gap=collections.defaultdict(collections.Counter)
    totals=collections.Counter()
    slotrows=[];recovered=[]
    for gid,t in gaps:
        n=sum(t+timedelta(minutes=i) in m5 for i in (0,5,10))
        cat='THREE_VALID_M5' if n==3 else ('PARTIAL_M5' if n else 'M5_NOT_RETURNED_MARKET_STATUS_UNKNOWN')
        per_gap[gid][cat]+=1;totals[cat]+=1
        slotrows.append({'gap_id':gid,'raw_label':t.isoformat(),'m5_count':n,'category':cat})
        if n==3:
            recovered.append({'gap_id':gid,'raw_label':t.isoformat(),**{k:str(v) for k,v in audit.aggregate(t,m5).items()},
                              'origin':'SAME_EPLANET_M5_RESEARCH_ONLY'})
    internal_complete=internal_matches=0
    for t,b in new.items():
        agg=audit.aggregate(t,m5)
        if agg is not None:
            internal_complete+=1;internal_matches+=audit.matched(b,agg,audit.Decimal('0'))
    summary={'schema':1,'status':'ACTUAL_DEMO_HISTORY_AUDIT_COMPLETE_MARKET_CAUSE_UNRESOLVED',
        'symbol':'XAUUSD.st','mode':'DEMO','quote_side':'BID_CHART_MODE_0',
        'execution_route':'EXISTING_TERMINAL_PYTHON_SDK_NOT_MQL_SCRIPT_EXECUTION',
        'original_m15_count':len(old),'new_m15_count':len(new),'new_m5_count':len(m5),
        'original_gap_count':260,'original_missing_slots':len(gaps),'counts':dict(totals),
        'recoverable_m15_count':len(recovered),'partial_m5_slots':totals['PARTIAL_M5'],
        'time_or_source_mismatch_slots':0,'officially_confirmed_closed_slots':0,
        'old_m15_missing_in_new':old_missing,'old_m15_price_mismatch':old_mismatch,
        'all_old_m15_m5_complete':sum(v['m5_complete'] for v in months.values()),
        'all_old_m15_m5_exact_match':sum(v['m5_exact_match'] for v in months.values()),
        'new_internal_complete':internal_complete,'new_internal_exact_match':int(internal_matches),
        'monthly_alignment':dict(months),
        'raw_label_mapping_minutes':0,'historical_utc_dst_mapping':'UNRESOLVED_NOT_NEEDED_FOR_RAW_LABEL_JOIN',
        'full_request_raw_labels':['2025-11-05T00:00:00','2026-11-06T00:00:00_EXCLUSIVE'],
        'old_coverage':[min(old).isoformat(),max(old).isoformat()],
        'm5_coverage':[min(m5).isoformat(),max(m5).isoformat()],
        'failed_chunks':sum(c['rows'] is None for c in receipt['chunks']),
        'empty_chunks':sum(c['rows']==0 for c in receipt['chunks']),
        'history_requests':len(receipt['chunks']),
        'same_existing_process':receipt['same_existing_process'],'orders':receipt['orders'],
        'source_hashes':{'old_manifest':sha(old_dir/'manifest.json'),'full_receipt':sha(export_dir/'receipt.json'),
                         'new_m15':sha(export_dir/'M15.csv'),'new_m5':sha(export_dir/'M5.csv'),'original_gaps':sha(gaps_path)},
        'targets':[r for r in slotrows if r['gap_id'] in (18,142)],
        'per_gap':[{'gap_id':g,'slot_count':sum(c.values()),'counts':dict(c)} for g,c in sorted(per_gap.items())],
        'limits':['Zero recoverable bars means none in this actual export, not proof of permanent broker unavailability.',
                  'No official historical closure evidence was supplied for these slots; all zero-M5 slots remain cause UNKNOWN.',
                  'No broker intent inferred. No source bars replaced. DEMO BID is not executable Ask or historical real fills.']}
    out.mkdir(parents=True,exist_ok=True)
    (out/'real-evidence-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    with (export_dir/'slot-classification-PRIVATE.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(slotrows[0]));w.writeheader();w.writerows(slotrows)
    if recovered:
        with (export_dir/'reconstructed-RESEARCH-PRIVATE.csv').open('x',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(recovered[0]));w.writeheader();w.writerows(recovered)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('monthly_alignment','per_gap')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('old-dir','export-dir','gaps-path','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();verify(a.old_dir,a.export_dir,a.gaps_path,a.out)
