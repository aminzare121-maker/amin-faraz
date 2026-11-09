#!/usr/bin/env python3
"""Read-only replay of real owner-supplied M15 bars into observational facts.

The teacher's verified original spoken decisions must be supplied in a separate
future review. No strategy thresholds, fills, profit or teacher matches asserted.
This file never imports MetaTrader5 or connects to a trading service.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

PROVENANCE='M15_PRIVATE_PROVENANCE.json'
PREFIX='ORIGINAL_M15_CSV/'
HEADERS=('time','open','high','low','close')


def _sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()


def read_verified_bars(zip_path):
    src=Path(zip_path)
    with zipfile.ZipFile(src) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):
            raise ValueError('duplicate zip member paths')
        if PROVENANCE not in names:
            raise ValueError('missing source provenance')
        m=json.loads(archive.read(PROVENANCE))
        expected=[PREFIX+x['name'] for x in m['files']]
        if set(names)!=(set(expected)|{PROVENANCE}):
            raise ValueError('archive extra/missing files')
        if m['source_chunks'] != len(expected):
            raise ValueError('source chunk count mismatch')
        rows=[]
        for meta, path in zip(m['files'], expected):
            raw=archive.read(path)
            if len(raw)!=meta['bytes'] or _sha(raw)!=meta['sha256']:
                raise ValueError('source CSV content hash or byte count mismatch: '+path)
            data=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
            if not data.fieldnames or not set(HEADERS).issubset(data.fieldnames):
                raise ValueError('invalid source columns: '+path)
            entries=list(data)
            if len(entries)!=meta['rows']:
                raise ValueError('source row count mismatch: '+path)
            for x in entries:
                t=int(x['time'])
                vals=[float(x[k]) for k in HEADERS[1:]]
                o,h,l,c=vals
                if not all(math.isfinite(p) and p>0 for p in vals) or not l<=min(o,c)<=max(o,c)<=h:
                    raise ValueError('invalid OHLC')
                if t%900:
                    raise ValueError('non-M15 opening time')
                rows.append((t,o,h,l,c))
        if len(rows)!=m['source_rows']:
            raise ValueError('total M15 count mismatch')
        times=[x[0] for x in rows]
        if any(b<=a for a,b in zip(times,times[1:])):
            raise ValueError('duplicate/out-of-order M15 times')
        if times[0]!=m['first_raw_epoch'] or times[-1]!=m['last_raw_epoch']:
            raise ValueError('source time boundary mismatch')
        return rows,m,_sha(src.read_bytes())


def scan(rows):
    tally=Counter()
    gaps=[]
    bars=[]
    previous=None
    for index, (t,o,h,l,c) in enumerate(rows):
        body=abs(c-o);rng=h-l
        upper=h-max(o,c);lower=min(o,c)-l
        if min(upper,lower)<-1e-8:
            raise AssertionError('invalid wick geometry')
        up=c>o;down=c<o
        tally['bullish' if up else 'bearish' if down else 'flat']+=1
        if rng==0:tally['zero_range']+=1
        if rng>0 and body>rng/2:tally['body_more_than_half_range']+=1
        if rng>0 and upper>lower:tally['upper_wick_longer']+=1
        if rng>0 and lower>upper:tally['lower_wick_longer']+=1
        prev_gap=None
        if previous is not None:
            dt=t-previous[0]
            if dt>900:
                gaps.append({'after_epoch':previous[0],'before_epoch':t,'missing_calendar_slots':dt//900-1,'classification':'UNKNOWN_SESSION_OR_HOLIDAY'})
                tally['bars_following_gap']+=1
            else:
                tally['consecutive_pairs']+=1
                # These are only price comparisons, not patterns or trade triggers.
                if h>previous[2]:tally['current_high_above_prev_high']+=1
                if l<previous[3]:tally['current_low_below_prev_low']+=1
                if h>previous[2] and l<previous[3]:tally['outside_previous_range']+=1
                if h<=previous[2] and l>=previous[3]:tally['inside_previous_range']+=1
        bars.append({'source_row_index':index,'raw_open_epoch_no_certified_utc_offset':t,
                     'open':o,'high':h,'low':l,'close':c,
                     'body_abs':round(body,10),'range_abs':round(rng,10),
                     'upper_wick_abs':round(max(0.0,upper),10),
                     'lower_wick_abs':round(max(0.0,lower),10),
                     'prior_bar_contiguous':bool(previous and t-previous[0]==900),
                     'teacher_trade_decision':'NOT_VERIFIED',
                     'trade_or_profit_result':None})
        previous=(t,o,h,l,c)
    return bars, tally, gaps


def build(source,output):
    source=Path(source);output=Path(output)
    rows, m, ziphash=read_verified_bars(source)
    entries, metrics, gaps=scan(rows)
    if len(gaps)!=m['gap_events_unclassified']:
        raise ValueError('unverified number of time gaps')
    output.parent.mkdir(parents=True,exist_ok=True)
    trace=output.with_suffix('.observations.jsonl')
    # Separate private per-bar facts. Never write original source data to GitHub.
    with trace.open('w',encoding='utf8') as fh:
        for x in entries:
            fh.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
    report={
       'schema':'artin_real_m15_observation_replay_v1',
       'source_archive_sha256':ziphash,
       'source_manifest_sha256_claimed_by_collector':m['source_manifest_sha256'],
       'source_broker_claim':m['source_claim'],
       'independently_authenticated_broker':False,
       'symbol_claims':m['symbol_claims'],
       'm15_rows_verified':len(rows),'m15_chunks_verified':m['source_chunks'],
       'first_raw_epoch':rows[0][0],'last_raw_epoch':rows[-1][0],
       'broker_timezone_mapping_verified':False,
       'gap_events_unclassified':len(gaps),
       'missing_calendar_slots_unclassified':sum(g['missing_calendar_slots'] for g in gaps),
       'gap_example_first':gaps[:3],
       'observations':dict(metrics),
       'private_observation_trace_sha256':_sha(trace.read_bytes()),
       'private_observation_trace_file':trace.name,
       'source_complete_bar_replay':len(entries)==len(rows),
       'semantic_teacher_rules_verified':0,
       'teacher_engine_comparisons_done':0,
       'mt5_orders_sent':0,
       'backtest_trades':None,
       'backtest_profit_usd':None,
       'backtest_win_rate':None,
       'explanation':'Every actual source candle was examined for geometry and prior-bar comparisons. None of these observations is claimed to be the teacher strategy. No PnL or trade backtest is possible without certified teacher decisions and execution parameters.',
    }
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    a=p.parse_args()
    result=build(a.source,a.report)
    print(json.dumps({'rows':result['m15_rows_verified'],'chunks':result['m15_chunks_verified'],'gaps':result['gap_events_unclassified'],'source_full_scan':result['source_complete_bar_replay'],'teacher_verified':result['semantic_teacher_rules_verified']},ensure_ascii=False))
if __name__=='__main__':main()