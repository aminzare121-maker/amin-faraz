import csv,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from collections import Counter

ROOT=Path(__file__).resolve().parent
PRIVATE=Path('C:/Users/Pixel/Documents/PRIVATE_EPLANET_HISTORY_20261105_DEMO')
def utc(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def load_existing(include_repairs=False):
    manifest=json.loads((PRIVATE/'manifest.json').read_text());bars=[];ticks=[]
    for e in manifest['chunks'].values():
        raw=(PRIVATE/e['csv']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==e['csv_sha256']
        with (PRIVATE/e['csv']).open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        (bars if e['kind']=='M15' else ticks).extend(rows)
    if include_repairs:
        repair=PRIVATE/'boundary-repair'
        receipt=json.loads((repair/'receipt.json').read_text())
        for e in receipt['entries']:
            data=(repair/e['csv']).read_bytes()
            assert hashlib.sha256(data).hexdigest()==e['csv_sha256']
            with (repair/e['csv']).open(newline='',encoding='utf-8') as f:extra=list(csv.DictReader(f))
            if any(int(x['time_msc'])>=e['start_raw_epoch']*1000 and int(x['time_msc'])<e['end_raw_epoch']*1000 for x in ticks):raise ValueError('REPAIR_OVERLAP')
            ticks.extend(extra)
    return sorted(bars,key=lambda x:int(x['time'])),sorted(ticks,key=lambda x:int(x['time_msc']))

def audit(include_repairs=False):
    bars,ticks=load_existing(include_repairs);indexed={int(b['time']):b for b in bars};samples=[]
    for t in sorted({int(x['time_msc'])//900000*900 for x in ticks}):
        chunk=[x for x in ticks if t*1000<=int(x['time_msc'])<(t+900)*1000]
        b=indexed[t];metrics={}
        for side in ('bid','ask'):
            values=[D(x[side]) for x in chunk]
            p=dict(open=values[0],high=max(values),low=min(values),close=values[-1])
            metrics[side]={k:str(p[k]-D(b[k])) for k in p}
        samples.append({'bar_raw_epoch':t,'bar_server_label':utc(t).replace('+00:00',''),
            'sample_utc_with_supported_winter_mapping':utc(t-7200),'time_basis':'BROKER_SERVER_LABEL_UTC_PLUS_2_FOR_THIS_SAMPLE_ONLY',
            'last_field_all_zero':all(D(x['last'])==0 for x in chunk),'ticks':len(chunk),'ohlc_delta_tick_minus_bar':metrics})
    gaps=[]
    for a,b in zip(bars,bars[1:]):
        first=int(a['time'])+900;end=int(b['time'])
        if end<=first:continue
        count=(end-first)//900;dt=datetime.fromtimestamp(first,timezone.utc)
        pattern='OTHER'
        if count==4:pattern='ONE_HOUR_RECURRENT_CANDIDATE'
        elif count==196:pattern='49_HOUR_WEEKEND_CANDIDATE'
        gaps.append({'id':len(gaps)+1,'start_raw_epoch':first,'end_raw_epoch_exclusive':end,
            'start_label_no_shift':utc(first),'end_label_no_shift':utc(end),'absent_m15_slots':count,
            'pattern':pattern,'classification':'UNKNOWN','evidence':'NO_BROKER_HISTORICAL_SESSION_CALENDAR',
            'natural_closure_proven':False,'data_defect_proven':False})
    report={'m15':len(bars),'ticks':len(ticks),'tick_reconstruction':samples,'gap_count':len(gaps),
        'patterns':dict(Counter(x['pattern'] for x in gaps)),'natural_proven':0,'defects_proven':0,'unknown':len(gaps)}
    (ROOT/'gap-classifications.json').write_text(json.dumps(gaps,indent=2),encoding='utf-8')
    (ROOT/('tick-side-after-repair.json' if include_repairs else 'tick-side-evidence.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':audit()
