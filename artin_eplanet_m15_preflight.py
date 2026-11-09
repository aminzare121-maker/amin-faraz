#!/usr/bin/env python3
"""Read-only Eplanet XAUUSD M15 CSV preflight for Artin V13.

Does not import Faraz strategies, infer teacher decisions, or issue orders.
This is quality assurance for an actual CSV supplied by the owner, not
proof that an alleged file originated from the broker. Naive times retain
an UNVERIFIED broker-clock label; never silently relabel them UTC.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {
    'open': {'open', 'o'}, 'high': {'high', 'h'},
    'low': {'low', 'l'}, 'close': {'close', 'c'},
    'time': {'time_raw_epoch', 'time', 'timestamp', 'datetime', 'date_time', 'date'},
    'date': {'date'}, 'clock': {'clock', 'time'},
}
PRICE_COLS = ('open','high','low','close')


def col_normal(s):
    return re.sub(r'[^a-z0-9_]+','',str(s).lower().strip().strip('<>'))


def parse_time(row, columns):
    # Do not interpret broker-local wall-clock as UTC. This value is used only
    # for interval calculations; the clock's origin is recorded as unknown.
    if 'date' in columns and 'clock' in columns:
        text=row[columns['date']].strip()+' '+row[columns['clock']].strip()
    else:
        text=row[columns['time']].strip()
    if re.fullmatch(r'\d{1,13}(?:\.\d+)?',text):
        epoch=float(text)
        if len(text.split('.')[0])==13: epoch/=1000
        if not math.isfinite(epoch) or not 0<=epoch<4102444800:
            raise ValueError('invalid_epoch')
        return epoch, 'RAW_EPOCH_CLOCK_NOT_INDEPENDENTLY_CERTIFIED'
    text=text.replace('T',' ').strip()
    value=None
    for fmt in ('%Y.%m.%d %H:%M:%S','%Y.%m.%d %H:%M',
                '%Y-%m-%d %H:%M:%S','%Y-%m-%d %H:%M',
                '%Y/%m/%d %H:%M:%S','%Y/%m/%d %H:%M'):
        try:
            value=datetime.strptime(text,fmt)
            break
        except ValueError: pass
    if value is None:
        try:value=datetime.fromisoformat(text)
        except ValueError:raise ValueError('invalid_datetime') from None
    if value.tzinfo is not None:
        return value.timestamp(), 'OFFSET_EXPLICIT_IN_FILE_NOT_BROKER_CERTIFIED'
    # epoch-like ordinal from naive wall time without asserting timezone
    return (value-datetime(1970,1,1)).total_seconds(), 'NAIVE_BROKER_WALL_CLOCK_TIMEZONE_UNVERIFIED'


def read_source(path):
    """Return UTF-8 text, source raw hash, and a single data-file label."""
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(str(path))
    raw=path.read_bytes()
    if not raw:raise ValueError('empty_source')
    digest=hashlib.sha256(raw).hexdigest()
    if zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=[x.filename for x in z.infolist() if not x.is_dir() and x.filename.lower().endswith(('.csv','.txt'))]
            if len(names)!=1:raise ValueError('zip_must_contain_exactly_one_csv_or_txt')
            inf=z.getinfo(names[0])
            if inf.file_size>150_000_000:raise ValueError('uncompressed_file_too_large')
            return z.read(inf).decode('utf-8-sig'), digest, names[0]
    if len(raw)>150_000_000:raise ValueError('file_too_large')
    return raw.decode('utf-8-sig'),digest,path.name


def choose_columns(fields):
    f={col_normal(c):c for c in fields if c}
    columns={}
    for key in PRICE_COLS:
        found=next((f[alias] for alias in ALIASES[key] if alias in f),None)
        if found is None:raise ValueError('missing_column_'+key)
        columns[key]=found
    # MT5 export date / time are separate. Avoid confusion with one `time` col.
    if 'date' in f and 'time' in f:
        columns['date']=f['date'];columns['clock']=f['time']
    else:
        columns['time']=next((f[a] for a in ('time_raw_epoch','timestamp','datetime','date_time','time','date') if a in f),None)
        if columns['time'] is None:raise ValueError('missing_time_column')
    return columns


def inspect_csv_text(text, original_sha256, origin_name, broker_claim='Eplanet (owner supplied; unverified export)'):
    # Support both conventional CSV and tab-separated native MetaTrader exports.
    head=text[:32768]
    try: dialect=csv.Sniffer().sniff(head, delimiters=',;\t')
    except csv.Error:raise ValueError('unsupported_separator') from None
    table=csv.DictReader(io.StringIO(text),dialect=dialect)
    if not table.fieldnames:raise ValueError('no_header')
    cols=choose_columns(table.fieldnames)
    row_count=0;invalid=[];gap_slots=0;gap_events=0;dupes=0;out_of_order=0
    first=last=None; clock_format=None
    # SHA256 of original is source identity; derived results do not replace it.
    for line_no, row in enumerate(table,2):
        if not row or not any((v or '').strip() for v in row.values() if isinstance(v,str)):continue
        row_count+=1
        if row_count>200000:raise ValueError('rows_over_limit')
        try:
            t, kind=parse_time(row,cols)
            if clock_format is None: clock_format=kind
            elif clock_format!=kind: raise ValueError('mixed_clock_formats')
            o,h,l,c=(float(str(row[cols[k]]).strip()) for k in PRICE_COLS)
            if not all(math.isfinite(x) and x>0 for x in (o,h,l,c)) or h<max(o,c,l) or l>min(o,c,h):
                raise ValueError('invalid_ohlc')
            if abs(t%900)>0.0001 and abs(t%900-900)>0.0001:
                raise ValueError('not_m15_aligned')
            if last is not None:
                diff=t-last
                if diff==0:dupes+=1
                elif diff<0:out_of_order+=1
                elif diff>900:
                    if diff%900>0.0001:raise ValueError('irregular_timing')
                    gap_events+=1;gap_slots+=round(diff/900)-1
            if first is None:first=t
            last=t
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            if len(invalid)<30:invalid.append({'csv_line':line_no,'reason':str(exc)[:100]})
    span_days=round((last-first)/86400,3) if first is not None and last is not None else 0
    return {
        'schema':'artin_eplanet_m15_preflight_v1',
        'status':'PASS_STRUCTURAL_WITH_LIMITATIONS' if row_count and not (invalid or dupes or out_of_order) else 'FAIL_STRUCTURAL',
        'source_file':origin_name,'source_bytes_sha256':original_sha256,
        'source_broker_claim':broker_claim,'broker_provenance_independently_verified':False,
        'time_interpretation':clock_format or 'UNKNOWN','bar_interval_seconds':900,
        'rows':row_count,'first_time_raw_seconds':first,'last_time_raw_seconds':last,
        'span_calendar_days':span_days, 'calendar_year_span_at_least_330_days':span_days>=330,
        'duplicate_bars':dupes,'out_of_order_bars':out_of_order,
        'invalid_rows_sample':invalid,'invalid_rows_shown':len(invalid),
        'gap_events':gap_events,'missing_calendar_slots_unclassified':gap_slots,
        'gap_disclaimer':'Unknown sessions/holidays; never infer missing live trading bars from calendar slots',
        'future_bars_excluded_confirmed':False, 'bid_ask_and_execution_costs_available':False,
        'teacher_rules_independently_verified':False,
        'teacher_motor_decisions_compared':0,'backtest_trades':0,
        'backtest_profit_usd':None,'backtest_win_rate':None,
        'mt5_orders_authorized':False,
        'reason_trading_blocked':'No authenticated teacher rule predicates, SL/TP, spread history or execution model supplied',
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path,help='local, owner-supplied Eplanet XAUUSD M15 CSV or single-CSV ZIP')
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args(argv)
    try:
        text,sha,name=read_source(a.csv)
        result=inspect_csv_text(text,sha,name)
    except (ValueError, UnicodeDecodeError, OSError, zipfile.BadZipFile) as exc:
        result={'schema':'artin_eplanet_m15_preflight_v1','status':'FAIL_INPUT',
                'source_file':a.csv.name,'error':str(exc), 'mt5_orders_authorized':False,
                'backtest_trades':0,'backtest_profit_usd':None,'teacher_rules_independently_verified':False}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('status','rows','span_calendar_days','invalid_rows_shown','duplicate_bars','out_of_order_bars','gap_events','error','mt5_orders_authorized')},ensure_ascii=False))
    return 0 if result['status']=='PASS_STRUCTURAL_WITH_LIMITATIONS' else 2

if __name__=='__main__':sys.exit(main())