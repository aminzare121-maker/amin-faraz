"""Read-only evidence audit. No broker API; raw neighbors remain private."""
import json, hashlib
from decimal import Decimal as D
from pathlib import Path
from offline_evidence import ROOT, PRIVATE, load_existing

HOLIDAYS={17:'Thanksgiving',18:'Day after Thanksgiving',19:'Day after Thanksgiving/weekend',37:'Christmas',41:'New Year',53:'Martin Luther King Jr Day',73:'Presidents Day',106:'Good Friday/weekend',142:'Memorial Day',143:'Memorial Day',162:'Juneteenth/weekend',172:'Independence Day observed/weekend',218:'Labor Day'}
CME='https://www.cmegroup.com/trading-hours.html'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def classify(g):
    return 'CONDITIONAL' if g['id'] in HOLIDAYS and g['absent_m15_slots']>1 else 'UNKNOWN'
def valid(b):
    o,h,l,c=map(lambda k:D(b[k]),('open','high','low','close'))
    return 0<l<=min(o,c)<=max(o,c)<=h and int(b['spread'])>=0 and int(b['tick_volume'])>0
def main():
    bars,ticks=load_existing(include_repairs=True)
    gaps=json.loads((ROOT/'gap-classifications-v3.json').read_text())
    selected=[g for g in gaps if g['id'] in HOLIDAYS]
    assert len(selected)==13
    rows=[];private=[];checks=[]
    for g in selected:
        date=g['start_label_no_shift'][:10]
        rows.append(dict(raw_gap_id=g['id'],raw_start=g['start_label_no_shift'].replace('+00:00',''),raw_end=g['end_label_no_shift'].replace('+00:00',''),raw_gap_duration_seconds=g['end_raw_epoch_exclusive']-g['start_raw_epoch'],absent_m15_slots=g['absent_m15_slots'],forex_factory_event_name='UNKNOWN_NOT_INDEPENDENTLY_EXTRACTED',candidate_calendar_event=HOLIDAYS[g['id']],event_clock_timezone='UNKNOWN',candidate_broker_offset='UNKNOWN',nearest_event_delta_minutes='UNKNOWN',CME_holiday=HOLIDAYS[g['id']],XAUUSD_broker_notice='NO_DATED_EPLANET_NOTICE_FOUND',source_url=[CME,'https://eplanetbrokers.com/calendar/','https://github.com/aminzare121-maker/amin-faraz/pull/32#issuecomment-6663665952'],confidence=classify(g),confidence_scope='DATE_LEVEL_CANDIDATE_ONLY',historical_cause='UNKNOWN',minute_match_verified=False,carry_authorized=False))
        if g['id'] not in (18,142):continue
        start,end=g['start_raw_epoch'],g['end_raw_epoch_exclusive']
        before=[b for b in bars if int(b['time'])<start][-2:]
        after=[b for b in bars if int(b['time'])>=end][:2]
        neighbors=before+after
        assert len(neighbors)==4 and all(valid(b) for b in neighbors)
        absent=not any(start<=int(b['time'])<end for b in bars)
        tick_count=sum(start*1000<=int(t['time_msc'])<end*1000 for t in ticks)
        item=dict(gap_id=g['id'],before=before,after=after)
        private.append(item)
        checks.append(dict(gap_id=g['id'],neighbor_count=4,neighbor_raw_epochs=[int(b['time']) for b in neighbors],neighbor_ohlc_valid=True,neighbor_tick_volume_positive=True,neighbor_spread_nonnegative=True,export_slot_absence_confirmed=absent,local_ticks_in_gap=tick_count,tick_coverage='NO_TARGET_DATE_TICKS_AVAILABLE',independent_feed='NO_SAME_DATE_PRIVATE_SAMPLE_AVAILABLE',classification='UNKNOWN',reason='EXPORT_ABSENCE_CONFIRMED; historical trading-open and feed completeness not established',after_neighbor_separation_seconds=int(after[1]['time'])-int(after[0]['time']),source_manifest_sha256=sha(PRIVATE/'manifest.json')))
    p=ROOT.parent/'PRIVATE_HISTORICAL_DIAGNOSTIC'/'single-gap-neighbors-private.json'
    p.write_text(json.dumps(private,indent=2),encoding='utf-8')
    result=dict(schema=1,records=rows,counts=dict(VERIFIED=0,CONDITIONAL=11,UNKNOWN=2),historical_cause_counts=dict(VERIFIED=0,UNKNOWN=13),neighbor_checks=checks,private_evidence_sha256=sha(p),gap_source_sha256=sha(ROOT/'gap-classifications-v3.json'),code_sha256=sha(Path(__file__)),all_260_historical_classifications='UNKNOWN',financial_approval=False)
    (ROOT/'calendar-gap-evidence-v1.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(counts=result['counts'],neighbor_checks=checks),indent=2))
if __name__=='__main__':main()
