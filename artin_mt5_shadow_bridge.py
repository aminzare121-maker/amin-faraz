#!/usr/bin/env python3
"""Read-only Artin V13 MT5 DEMO M15 bar ingestion, no strategy or trading.

A native MQL5 probe can append CLOSED original broker bars; this importer checks
source syntax/price geometry/monotonicity and generates a 13-route blocked ledger.
Its successful output is NOT proof that the CSV actually came from Eplanet,
not broker clock verification, teacher certification or a trading/backtest run.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROUTES = (
 'BREAK_STRONG', 'BREAK_VERY_STRONG_RETEST', 'BREAK_WEAK_FULLBODY_EXCEPTION',
 'BREAK_WEAK_PIVOT', 'PULLBACK_STANDARD', 'REVERSAL_CLASSIC', 'REVERSAL_STAR',
 'REVERSAL_THREE', 'STOPPUNCH_DOJI_AHEAD', 'STOPPUNCH_DOJI_TIED',
 'STOPPUNCH_OPPOSITE_CONFIRMATION', 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE',
 'STOPPUNCH_SAME_COLOUR',
)
HEADER = ('source_label','broker_epoch','broker_walltime','symbol','timeframe',
          'open','high','low','close','tick_volume','spread','real_volume',
          'teacher_semantics_verified','trade_authorized')
LABEL = 'MT5_TERMINAL_DEMO_CLOSED_BAR_RAW_BROKER_CLOCK'
MAX_BYTES = 30_000_000
MAX_BARS = 500_000

class SourceRejected(ValueError):
    pass

def _reject(reason:str):raise SourceRejected(reason)

def parse_csv_bytes(raw:bytes)->dict:
    if not isinstance(raw,bytes) or not raw or len(raw)>MAX_BYTES:
        _reject('EMPTY_OR_OVERSIZED_CSV')
    if b'\x00' in raw:_reject('BINARY_DATA')
    try:txt=raw.decode('utf-8-sig')
    except UnicodeError:_reject('INVALID_UTF8')
    if '\r' in txt.replace('\r\n',''):_reject('INVALID_NEWLINE')
    stream=csv.reader(io.StringIO(txt,newline=''),delimiter=',',strict=True)
    try:header=next(stream)
    except (StopIteration,csv.Error):_reject('MISSING_HEADER')
    if tuple(header)!=HEADER:_reject('HEADER_SCHEMA_MISMATCH')
    n=0;first_epoch=None;last_epoch=None;gaps=0;symbols=Counter();tfs=Counter()
    last_wall=None
    try:
        for physical,row in enumerate(stream,start=2):
            if n >= MAX_BARS:_reject('BAR_LIMIT_EXCEEDED')
            if len(row)!=len(HEADER):_reject(f'COLUMN_COUNT_{physical}')
            r=dict(zip(HEADER,row))
            if r['source_label'] != LABEL:_reject(f'UNKNOWN_SOURCE_LABEL_{physical}')
            # Demo/live provenance cannot be authenticated by CSV text alone.
            sym=r['symbol']
            if not re.fullmatch(r'XAUUSD[A-Za-z0-9._-]{0,24}',sym):
                _reject(f'UNEXPECTED_SYMBOL_{physical}')
            if r['timeframe']!='M15':_reject(f'UNEXPECTED_TIMEFRAME_{physical}')
            if r['teacher_semantics_verified']!='0' or r['trade_authorized']!='0':
                _reject(f'FALSE_SEMANTIC_OR_ORDER_AUTHORIZATION_{physical}')
            try:epoch=int(r['broker_epoch'])
            except ValueError:_reject(f'INVALID_EPOCH_{physical}')
            if epoch<=0 or epoch%900!=0:_reject(f'UNALIGNED_M15_BAR_{physical}')
            if last_epoch is not None:
                if epoch<=last_epoch:_reject(f'DUPLICATE_OR_NONMONOTONIC_BAR_{physical}')
                if epoch-last_epoch!=900:gaps+=1
            if first_epoch is None:first_epoch=epoch
            # Broker wall clock is not assumed to have a UTC offset; don't
            # recompute timestamps from it or label the epoch as independently UTC.
            try:wall=datetime.strptime(r['broker_walltime'],'%Y.%m.%d %H:%M:%S')
            except ValueError:_reject(f'INVALID_WALL_CLOCK_{physical}')
            if last_wall is not None and wall<last_wall:
                _reject(f'REVERSED_BROKER_WALL_CLOCK_{physical}')
            last_wall=wall
            prices=[]
            for col in ('open','high','low','close'):
                try: val=float(r[col])
                except ValueError:_reject(f'NONNUMERIC_{col}_{physical}')
                if not math.isfinite(val) or val<=0:_reject(f'INVALID_{col}_{physical}')
                prices.append(val)
            op,hi,lo,cl=prices
            if not lo<=min(op,cl)<=max(op,cl)<=hi:
                _reject(f'BAD_OHLC_GEOMETRY_{physical}')
            for col in ('tick_volume','spread','real_volume'):
                try:val=int(r[col])
                except ValueError:_reject(f'INVALID_{col}_{physical}')
                if val<0:_reject(f'NEGATIVE_{col}_{physical}')
            n+=1;last_epoch=epoch;symbols[sym]+=1;tfs[r['timeframe']]+=1
    except csv.Error:_reject('MALFORMED_CSV')
    if not n:_reject('NO_CLOSED_BARS')
    if len(symbols)!=1:_reject('MIXED_SYMBOL_STREAM')
    return {'source_rows':n,'first_broker_epoch':first_epoch,'last_broker_epoch':last_epoch,
      'raw_broker_wall_clock_not_independently_UTC_verified':True,
      'gaps_unclassified':gaps,'symbol':next(iter(symbols)),'timeframe':'M15'}

def build_blocked_report(raw:bytes)->dict:
    metrics=parse_csv_bytes(raw)
    return {'schema':'artin_v13_demo_m15_readonly_ingest_v1',
       'csv_sha256':hashlib.sha256(raw).hexdigest(),**metrics,
       'source_claim_not_independently_authenticated':True,
       'teacher_original_speech_independently_verified':False,
       'chart_semantics_verified':False,
       'economic_calendar_applied':False,
       'risk_entry_exit_teacher_rules_verified':False,
       'market_entry_signals':0,'broker_orders_sent':0,'demo_orders_sent':0,
       'simulation_results':None,'teacher_meaning_verified':False,
       'route_count':len(ROUTES),
       'route_statuses':[{'route_id':rule,'state':'BLOCKED_UNVERIFIED_TEACHER_RULE',
          'buy_eligible':False,'sell_eligible':False,'order_authorized':False,
          'missing_evidence':['teacher_verified_voice_and_speaker','teacher_chart_referent',
                              'teacher_entry_exit_exceptions','cross_session_resolution',
                              'real_teacher_example_replay_pass']}
          for rule in ROUTES],
       'next_stage':'Independent original teacher A/V interpretation, then replay in paper mode; do not enable MT5 trade calls.'}

def main():
    p=argparse.ArgumentParser(description='Artin V13 read-only MT5 DEMO M15 intake')
    p.add_argument('csv',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.csv.resolve()==a.output.resolve():raise SourceRejected('CANNOT_OVERWRITE_SOURCE')
    raw=a.csv.read_bytes()
    report=build_blocked_report(raw)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'bars':report['source_rows'],'routes':report['route_count'],
      'eligible_signals':0,'orders':0,'report':str(a.output)},ensure_ascii=False))
if __name__=='__main__':main()