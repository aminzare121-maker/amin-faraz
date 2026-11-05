"""Read existing private bars only; keep raw prices and source paths private."""
import csv,json
from bisect import bisect_left
from collections import Counter
from datetime import datetime,timezone
from calendar_gap_audit import ROOT,PRIVATE,load_existing,sha,valid,HOLIDAYS
def label(t):return datetime.fromtimestamp(t,timezone.utc).isoformat().replace('+00:00','')
def candidate(g):
    if g['pattern']!='OTHER':return 'SESSION_CLOSURE_CANDIDATE'
    if g['absent_m15_slots']==1:return 'FEED_ABSENCE_CANDIDATE'
    if g['id'] in HOLIDAYS:return 'HOLIDAY_EARLY_CLOSE_CANDIDATE'
    return 'UNRESOLVED'
def main():
    bars,ticks=load_existing(include_repairs=True);times=[int(b['time']) for b in bars]
    assert len(times)==len(set(times))==23643
    gaps=json.loads((ROOT/'gap-classifications-v3.json').read_text())
    with (ROOT/'gap-neighbor-time-context-260.csv').open(encoding='utf-8',newline='') as f: reference={int(x['gap_id']):x for x in csv.DictReader(f)}
    assert len(reference)==len(gaps)==260
    manifest=json.loads((PRIVATE/'manifest.json').read_text());sources={}
    for chunk in manifest['chunks'].values():
        if chunk['kind']!='M15':continue
        with (PRIVATE/chunk['csv']).open(encoding='utf-8',newline='') as f:
            for b in csv.DictReader(f):sources[int(b['time'])]=dict(file=chunk['csv'],sha256=chunk['csv_sha256'])
    full=[];public=[];counts=Counter();slots=Counter();unique=set()
    for g in gaps:
        start,end=g['start_raw_epoch'],g['end_raw_epoch_exclusive'];i=bisect_left(times,start);j=bisect_left(times,end)
        before=bars[i-2:i];after=bars[j:j+2];neighbors=before+after
        assert len(before)==len(after)==2 and i==j
        assert all(valid(b) for b in neighbors)
        ref=reference[g['id']]
        assert label(int(before[-1]['time']))==ref['previous_observed_candle_open_raw_label']
        assert label(int(after[0]['time']))==ref['next_observed_candle_open_raw_label']
        assert int(ref['missing_m15_count'])==g['absent_m15_slots']
        rows=[dict(b,source_receipt=sources[int(b['time'])],symbol='XAUUSD.st',feed='Eplanet Demo') for b in neighbors]
        full.append(dict(gap_id=g['id'],before=rows[:2],after=rows[2:]))
        unique.update(int(b['time']) for b in neighbors)
        cat=candidate(g);counts[cat]+=1;slots[cat]+=g['absent_m15_slots']
        public.append(dict(gap_id=g['id'],neighbor_raw_epochs=[int(b['time']) for b in neighbors],neighbor_count=4,ohlc_valid=True,spread_nonnegative=True,tick_volume_positive=True,source_receipts_present=True,reference_boundaries_match=True,absent_slots=g['absent_m15_slots'],slot_parent_candidate=cat,historical_status='UNKNOWN',evidence_status='CALENDAR_CANDIDATE' if g['id'] in HOLIDAYS and g['absent_m15_slots']>1 else 'UNKNOWN',source_url=['https://www.metatrader5.com/en/terminal/help/trading/market_watch']+(['https://www.cmegroup.com/trading-hours.html'] if g['id'] in HOLIDAYS else []),minute_match='UNKNOWN',cross_gap_execution=False))
    private=ROOT.parent/'PRIVATE_HISTORICAL_DIAGNOSTIC'/'all-gap-neighbors-private.json'
    private.write_text(json.dumps(full,indent=2),encoding='utf-8')
    report=dict(schema=1,gaps=260,neighbor_occurrences=1040,unique_neighbor_bars=len(unique),absent_slots=sum(slots.values()),candidate_gaps=dict(counts),candidate_slots=dict(slots),status_gaps=dict(VERIFIED_CLOSED=0,VERIFIED_MISSING_WHILE_OPEN=0,CALENDAR_CANDIDATE=11,UNKNOWN=249),status_slots=dict(VERIFIED_CLOSED=0,VERIFIED_MISSING_WHILE_OPEN=0,CALENDAR_CANDIDATE=sum(g['absent_m15_slots'] for g in gaps if g['id'] in HOLIDAYS and g['absent_m15_slots']>1),UNKNOWN=sum(g['absent_m15_slots'] for g in gaps if not(g['id'] in HOLIDAYS and g['absent_m15_slots']>1))),historical_cause_unknown=260,private_evidence_sha256=sha(private),code_sha256=sha(ROOT/'all_gap_neighbor_audit.py'),manifest_sha256=sha(PRIVATE/'manifest.json'),reference_csv_sha256=sha(ROOT/'gap-neighbor-time-context-260.csv'),boundary_checks_pass=260,raw_price_published=False,eligibility_change=0,financial_approval=False,rows=public)
    assert report['absent_slots']==11397
    (ROOT/'all-gap-neighbor-evidence-v1.json').write_text(json.dumps(report,separators=(',',':')),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
if __name__=='__main__':main()
