"""Observed complete M1 buckets only. Missing sessions remain UNKNOWN, never filled."""
import csv,io,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from statistics import median
from collections import defaultdict
from vendor.independent_adapter import ohlc
from offline_evidence import load_existing
from comparison import compare

def aggregate(rows,start,end,asof):
    if start%900 or end%900 or end<=start or end>asof:raise ValueError('WINDOW_OR_CLOSURE')
    indexed={};last=None
    for row in rows:
        dt=datetime.fromisoformat(row['Etc/UTC'])
        if dt.utcoffset() is None or dt.utcoffset().total_seconds()!=0:raise ValueError('NOT_UTC')
        t=int(dt.timestamp())
        if dt.microsecond or t%60 or not start<=t<end or (last is not None and t<=last):raise ValueError('TIME_ORDER_RANGE')
        if not D(row['Volume']).is_finite() or D(row['Volume'])<=0:raise ValueError('NO_QUOTE_VOLUME')
        indexed[t]=ohlc({k:row[k.title()] for k in ('open','high','low','close')});last=t
    bars=[];excluded=[]
    for begin in range(start,end,900):
        slots=list(range(begin,begin+900,60));missing=[t for t in slots if t not in indexed]
        if missing:
            excluded.append({'time':begin,'missing_m1':len(missing),'reason':'UNKNOWN_SESSION_NO_FILL'});continue
        p=[indexed[t] for t in slots]
        bars.append(dict(time=begin,open=str(p[0]['open']),high=str(max(x['high'] for x in p)),low=str(min(x['low'] for x in p)),close=str(p[-1]['close'])))
    return bars,excluded

def metrics(differences):
    result={}
    for key in ('open','high','low','close'):
        values=[D(r[key]) for r in differences];absvalues=[abs(x) for x in values]
        result[key]={'signed_mean':str(sum(values)/len(values)),'signed_median':str(median(values)),
            'mean_absolute':str(sum(absvalues)/len(values)),'median_absolute':str(median(absvalues)),
            'max_absolute':str(max(absvalues)),
            'count_abs_gt_1_usd_per_oz':sum(x>D('1') for x in absvalues)}
    return result

def run():
    root=Path(__file__).resolve().parent;private=root.parent/'PRIVATE_DUKASCOPY_SAMPLE';private.mkdir(exist_ok=True)
    start=int(datetime(2026,11,4,tzinfo=timezone.utc).timestamp());end=start+86400
    clock=json.loads((root/'terminal-clock-sanitized.json').read_text())
    if clock['chart_mode']!=clock['chart_mode_bid_constant'] or not 7190<clock['quote_minus_wall_seconds']<7205:raise ValueError('CLOCK_OR_SIDE_NOT_SUPPORTED')
    sides={};receipts={};exclusions={}
    for side in ('BID','ASK'):
        source=Path('C:/Users/Pixel/Downloads')/f'XAU-USD_1Minute_{side}_2026-11-04_00_00-23_59_Etc_UTC.csv'
        raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest();dest=private/(sha+'.csv')
        if dest.exists():assert dest.read_bytes()==raw
        else:
            with dest.open('xb') as f:f.write(raw)
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        sides[side],exclusions[side]=aggregate(rows,start,end,int(clock['utc_wall_before']))
        receipts[side]={'raw_sha256':sha,'rows_m1':len(rows),'bytes':len(raw),'bars_m15':len(sides[side])}
    source_bars,ticks=load_existing()
    # Fixed support-stated winter UTC+2, checked against current quote/wall clock.
    # Scope Nov 4 only, not a fitted offset and NOT a year-long DST mapping.
    left=[{**{k:r[k] for k in ('open','high','low','close')},'time':int(r['time'])-7200} for r in source_bars if start<=int(r['time'])-7200<end]
    right=sides['BID'];a={r['time']:r for r in left};b={r['time']:r for r in right};common=sorted(a.keys()&b.keys())
    meta=dict(canonical='XAUUSD',price_side='BID',timezone='UTC',bar_seconds=900,unit='USD/oz',
        session_evidence='OBSERVED_COMPLETE_SHARED_BUCKETS_ONLY_NOT_HISTORICAL_CLOSURE_CERTIFICATE',mapping_evidence='CURRENT_CHART_MODE_AND_SUPPORT_WINTER_UTC2_PLUS_LIVE_CLOCK')
    summary=compare(left,right,meta,meta)
    diffs=[dict(time=t,time_difference_seconds=0,**{k:str(D(a[t][k])-D(b[t][k])) for k in ('open','high','low','close')}) for t in common]
    (private/'nov04-per-bar-differences.json').write_text(json.dumps(diffs,indent=2),encoding='utf-8')
    output={'date':'2026-11-04','scope':'OBSERVED_COMMON_BID_BARS_ONLY_CONDITIONAL_WINTER_CLOCK_MAPPING',
        'receipts':receipts,'eplanet_m15':len(left),'dukascopy_m15':len(right),'common_bars':len(common),
        'left_only':[t for t in a if t not in b],'right_only':[t for t in b if t not in a],
        'both_absent':[t for t in range(start,end,900) if t not in a and t not in b],
        'dukascopy_excluded':exclusions,'time_mapping':{'raw_to_utc_seconds':-7200,'scope':'2026-11-04 only',
            'evidence':['Eplanet ticket207852 winter UTC+2','terminal-clock-sanitized.json'],
            'historical_year_certified':False,'raw_modified':False,'offset_selected_by_price_fit':False},
        'ohlc_metrics':metrics(diffs),'time_difference_seconds':0,'unusual_rule':'absolute OHLC delta >1 USD/oz; predeclared diagnostic threshold, not defect proof',
        'bars_with_any_abs_delta_gt_1':sum(any(abs(D(r[k]))>1 for k in ('open','high','low','close')) for r in diffs),
        'spread_comparison':'NOT_IDENTIFIABLE_FROM_SEPARATE_OHLC_EXTREMA; NO_SYNCHRONIZED_EPLANET_TICKS_FOR_NOV04',
        'financial_result':'NOT_RUN','year_fit_allowed':False,'comparator_status':summary['status']}
    (root/'real-comparison-sanitized.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in output.items() if k!='dukascopy_excluded'},indent=2))
if __name__=='__main__':run()
