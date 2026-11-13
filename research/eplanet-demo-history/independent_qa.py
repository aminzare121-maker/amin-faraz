"""Offline independent QA over immutable local SDK chunks; sanitized aggregates only."""
import csv,hashlib,json,math,pathlib,statistics,collections,datetime
ROOT=pathlib.Path('C:/Users/Pixel/Documents/PRIVATE_EPLANET_HISTORY_20261105_DEMO')
manifest=json.loads((ROOT/'manifest.json').read_text());records=[];ticks=[];verified=0
for entry in manifest['chunks'].values():
    for field in ('raw','csv'):
        assert hashlib.sha256((ROOT/entry[field]).read_bytes()).hexdigest()==entry[field+'_sha256'];verified+=1
    with (ROOT/entry['csv']).open(newline='',encoding='utf-8') as f:
        rows=list(csv.DictReader(f))
    (records if entry['kind']=='M15' else ticks).extend(rows)
records.sort(key=lambda r:int(r['time']));ticks.sort(key=lambda r:int(r['time_msc']))
counts=collections.Counter(datetime.datetime.fromtimestamp(int(r['time']),datetime.timezone.utc).strftime('%Y-%m') for r in records)
ranges=[float(r['high'])-float(r['low']) for r in records];median=statistics.median(ranges)
flags=[{'time_utc':datetime.datetime.fromtimestamp(int(r['time']),datetime.timezone.utc).isoformat(),'flag':'RANGE_GT_10X_DATASET_MEDIAN_REVIEW_ONLY'} for r,x in zip(records,ranges) if x>10*median]
spread=[float(r['ask'])-float(r['bid']) for r in ticks]
q=json.loads((ROOT/'year-qa.json').read_text())
unusual=[g for g in q['qa']['gaps'] if g['missing_slots'] not in (4,196)]
out={'mode':'DEMO','raw_files_and_csv_hashes_verified':verified,'raw_rows_modified':False,'m15_rows':len(records),'tick_rows':len(ticks),
     'monthly_m15_counts':dict(sorted(counts.items())),'unusual_range_flags':flags,'range_threshold_method':'10x full-dataset median; retrospective descriptive QA only, never trading feature',
     'gap_count':len(q['qa']['gaps']),'unclassified_gap_slots':sum(g['missing_slots'] for g in q['qa']['gaps']),
     'unusual_gap_windows':unusual,'natural_closure_verified':False,
     'tick_sample_spread_usd_per_oz':{'min':min(spread),'median':statistics.median(spread),'max':max(spread)},
     'spread_sample_is_year_representative':False,'bid_ask_history_year_available':False,
     'full_year_tick_downloaded':False,'costs':{'commission':'SUPPORT_ZERO_ST','historical_swap':'UNKNOWN','slippage':'UNKNOWN'},
     'usable_for_final_backtest':False,'reasons':['SESSION_AND_HOLIDAY_GAPS_UNRESOLVED','HISTORICAL_SWAP_UNKNOWN','SLIPPAGE_UNKNOWN','ONLY_30_MINUTES_TICKS','PRICE_SIDE_METADATA_REQUIRES_CONFIRMATION'],
     'dukascopy_comparison':'NOT_RUN_NO_SECOND_DATASET'}
pathlib.Path('independent-qa-sanitized.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ('unusual_range_flags','unusual_gap_windows')},indent=2))
