"""Offline audit of an official browser export. Private raw, sanitized report."""
import csv,hashlib,io,json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from vendor.independent_adapter import ohlc

root=Path(__file__).resolve().parent
source=Path('C:/Users/Pixel/Downloads/XAU-USD_1Minute_BID_2026-11-05_23_59-23_59_Etc_UTC.csv')
raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
private=root.parent/'PRIVATE_DUKASCOPY_SAMPLE';private.mkdir(exist_ok=True)
target=private/(sha+'.csv')
if target.exists():assert target.read_bytes()==raw
else:
    with target.open('xb') as f:f.write(raw)
reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
assert reader.fieldnames==['Etc/UTC','Open','High','Low','Close','Volume']
rows=list(reader);times=[];invalid=0;non_utc=0
for row in rows:
    dt=datetime.fromisoformat(row['Etc/UTC'])
    if dt.utcoffset() is None or dt.utcoffset().total_seconds()!=0:non_utc+=1
    times.append(int(dt.timestamp()))
    try:ohlc({key:row[key.title()] for key in ('open','high','low','close')})
    except (ValueError,TypeError):invalid+=1
duplicates=len(times)-len(set(times));unordered=sum(b<=a for a,b in zip(times,times[1:]))
gaps=[{'from':a,'to':b,'missing_minutes':(b-a)//60-1,'classification':'UNKNOWN_SESSION'} for a,b in zip(times,times[1:]) if b-a>60]
counts=Counter(t//900*900 for t in times)
out={'source':'OFFICIAL_DUKASCOPY_WEB_EXPORT','url':'https://widgets.dukascopy.com/en/historical-data-export',
     'symbol':'XAU/USD','timeframe':'M1','price_side':'BID','timezone':'Etc/UTC','raw_sha256':sha,
     'bytes':len(raw),'rows':len(rows),'first_utc':rows[0]['Etc/UTC'] if rows else None,'last_utc':rows[-1]['Etc/UTC'] if rows else None,
     'invalid_ohlc':invalid,'duplicate_timestamps':duplicates,'nonincreasing_times':unordered,'non_utc':non_utc,
     'unaligned_minutes':sum(t%60!=0 for t in times),'gaps':gaps,'complete_15_record_groups':sum(n==15 for n in counts.values()),
     'raw_modified':False,'paid_service_activated':False,'aws_requests':0,
     'aggregation_approved':False,'comparison':'NOT_RUN_SESSION_AND_EPLANET_PRICE_SIDE_REQUIRE_CONFIRMATION',
     'spread':'UNKNOWN_BID_ONLY','year_downloaded':False,'financial_backtest':'NOT_RUN'}
(root/'dukascopy-sample-qa.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
