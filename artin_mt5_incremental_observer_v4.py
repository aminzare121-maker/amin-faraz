#!/usr/bin/env python3
"""Artin V13 MT5 M15 incremental read-only observation, NEVER an EA or trade gate.

Consumes complete snapshots of the strictly validated append-only CSV emitted by
V2 MQL5, pins the entire previous byte-prefix across invocations, and emits
raw candle geometry + the 13 permanently blocked teacher routes. A caller-provided
CSV is NOT proof of DEMO, broker authenticity, or teacher fidelity.

No sockets, broker connection, filesystem writes except an explicitly named
local observation-state JSON. In particular no orders, fills, P/L, or signals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
from pathlib import Path

from artin_mt5_shadow_bridge import HEADER, ROUTES, SourceRejected, parse_csv_bytes, MAX_BYTES

SCHEMA = 'artin_v13_append_only_observer_v4'
SHA256_RE = re.compile(r'[0-9a-f]{64}\Z')
MAX_NEW_BARS = 10_000

class ObserverBlocked(ValueError):
    pass


def _fail(reason):
    raise ObserverBlocked(reason)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_rows(raw: bytes):
    """Read source bytes after strict broker-format validation, no coercion hacks."""
    # csv.reader strips CSV framing only; authoritative source validation is
    # already completed in parse_csv_bytes before this helper is called.
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), delimiter=',')
    if tuple(reader.fieldnames or ()) != HEADER:
        _fail('SOURCE_HEADER_DRIFT')
    return list(reader)


def _state_ok(s):
    if not isinstance(s, dict) or s.get('schema') != SCHEMA:
        _fail('INVALID_STATE_SCHEMA')
    if type(s.get('source_bytes')) is not int or not 0 < s['source_bytes'] <= 30_000_000:
        _fail('INVALID_CHECKPOINT_LENGTH')
    if not isinstance(s.get('source_sha256'), str) or not SHA256_RE.fullmatch(s['source_sha256']):
        _fail('INVALID_CHECKPOINT_DIGEST')
    if type(s.get('rows_seen')) is not int or not 1 <= s['rows_seen'] <= 500_000:
        _fail('INVALID_CHECKPOINT_ROW_COUNT')
    if type(s.get('last_broker_epoch')) is not int or s['last_broker_epoch'] <= 0 or s['last_broker_epoch'] % 900:
        _fail('INVALID_CHECKPOINT_EPOCH')
    if not isinstance(s.get('symbol'), str) or not re.fullmatch(r'XAUUSD[A-Za-z0-9._-]{0,24}', s['symbol']):
        _fail('INVALID_CHECKPOINT_SYMBOL')


def _raw_features(row, preceding):
    t = int(row['broker_epoch'])
    o, h, l, c = (float(row[k]) for k in ('open', 'high', 'low', 'close'))
    direction = 'UP' if c > o else 'DOWN' if c < o else 'FLAT'
    body = abs(c-o)
    upper = h-max(o,c)
    lower = min(o,c)-l
    raw = {
        'broker_bar_epoch': t,
        'closed_bar_known_no_earlier_than_broker_epoch': t + 900,
        'observed_OHLC': [o,h,l,c],
        'candle_direction': direction,
        'body_size': round(body, 10),
        'upper_shadow': round(upper, 10),
        'lower_shadow': round(lower, 10),
        'exact_zero_body_subset': body == 0,
        'exact_shadowless_nonflat_subset': body > 0 and upper == 0 and lower == 0,
        'three_same_direction_contiguous_raw_candidate': False,
        'source_row_raw_fields_sha256': _sha(json.dumps([row[x] for x in HEADER], ensure_ascii=True, separators=(',', ':')).encode()),
        'teacher_rule_verified': False,
        'entry_signal': False,
        'trade_allowed': False,
    }
    if len(preceding) >= 2:
        bars = preceding[-2:] + [row]
        t0, t1, t2 = (int(x['broker_epoch']) for x in bars)
        if t1-t0 == 900 and t2-t1 == 900:
            directions = [
                'UP' if float(x['close']) > float(x['open']) else
                'DOWN' if float(x['close']) < float(x['open']) else 'FLAT'
                for x in bars
            ]
            raw['three_same_direction_contiguous_raw_candidate'] = directions[0] != 'FLAT' and len(set(directions)) == 1
    return raw


def _tail_committed_rows(prefix: bytes, row_count: int) -> list[bytes]:
    """Recover only the last 2 already-hashed records, not whole CSV history.

    V2 FileWrite emits one physical CRLF/LF-terminated CSV record per bar,
    with fixed unquoted fields. Reject ambiguous framing instead of guessing.
    """
    if not prefix.endswith(b'\n'):
        _fail('CHECKPOINT_NOT_TERMINATED_COMPLETE_ROW')
    pos = len(prefix) - 1  # index just before the final LF
    result = []
    for _ in range(min(2, row_count)):
        start = prefix.rfind(b'\n', 0, pos) + 1
        line = prefix[start:pos]
        if line.endswith(b'\r'):
            line = line[:-1]
        if not line or b'"' in line or line.count(b',') != len(HEADER)-1 or b'\r' in line:
            _fail('INVALID_PRIOR_CHECKPOINT_ROW_FRAMING')
        result.append(line)
        pos = start-1
    return result[::-1]


def process_snapshot(raw: bytes, prior_state=None, *, max_new_bars: int = MAX_NEW_BARS):
    """Return (new persistent checkpoint, read-only batch report).

    After bootstrap, SHA-256-check the ENTIRE persisted byte-prefix, then
    parse only two validated prior rows and the newly appended rows. A writer
    changing any previous byte, an incomplete row, invalid OHLC, an unsourced
    market gap, or an out-of-order bar never becomes an accepted checkpoint.
    """
    if type(max_new_bars) is not int or not 1 <= max_new_bars <= MAX_NEW_BARS:
        _fail('INVALID_BATCH_LIMIT')
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        _fail('EMPTY_OR_OVERSIZED_CSV')
    if not raw.endswith(b'\n'):
        _fail('SOURCE_HAS_UNCOMMITTED_PARTIAL_ROW')

    if prior_state is None:
        try:
            metrics = parse_csv_bytes(raw)
        except SourceRejected as exc:
            _fail('REJECTED_M15_SOURCE:' + str(exc))
        parsed = _source_rows(raw)
        if len(parsed) != metrics['source_rows']:
            _fail('PARSER_ROW_COUNT_DISAGREEMENT')
        start = 0
        old_context = 0
        new_rows = parsed
        symbol = metrics['symbol']
        last_epoch = int(parsed[-1]['broker_epoch'])
        source_bytes_parsed = len(raw)
    else:
        _state_ok(prior_state)
        prefix_length = prior_state['source_bytes']
        if len(raw) < prefix_length:
            _fail('SOURCE_TRUNCATED_AFTER_CHECKPOINT')
        prefix = raw[:prefix_length]
        if _sha(prefix) != prior_state['source_sha256']:
            _fail('SOURCE_HISTORY_REWRITTEN_AFTER_CHECKPOINT')
        # One fast byte count (not CSV re-parsing) binds stored row count to the
        # immutable SHA-checked prefix; a corrupt checkpoint cannot skip rows.
        if prefix.count(b'\n') - 1 != prior_state['rows_seen']:
            _fail('CHECKPOINT_ROW_IDENTITY_MISMATCH')
        old = _tail_committed_rows(prefix, prior_state['rows_seen'])
        # Validate row identity even if no new rows were appended.
        try:
            latest_fields = next(csv.reader([old[-1].decode('ascii')], strict=True))
        except (UnicodeError, csv.Error):
            _fail('PRIOR_CHECKPOINT_ROW_NOT_ASCII_CSV')
        if latest_fields[1] != str(prior_state['last_broker_epoch']):
            _fail('CHECKPOINT_ROW_IDENTITY_MISMATCH')
        if latest_fields[3] != prior_state['symbol']:
            _fail('SOURCE_SYMBOL_CHANGED_AFTER_CHECKPOINT')
        suffix = raw[prefix_length:]
        start = prior_state['rows_seen']
        symbol = prior_state['symbol']
        last_epoch = prior_state['last_broker_epoch']
        if not suffix:
            parsed = []
            new_rows = []
            old_context = len(old)
            source_bytes_parsed = 0
        else:
            if not suffix.strip():
                _fail('SOURCE_EXTENDED_WITHOUT_CLOSED_BAR')
            if not suffix.endswith(b'\n'):
                _fail('SOURCE_HAS_UNCOMMITTED_PARTIAL_ROW')
            # The original export has no quoting/embedded multiline fields.
            # Disallow a byte-level ambiguity in appended record boundaries.
            if b'"' in suffix or b'\x00' in suffix:
                _fail('SOURCE_APPEND_FRAMING_INVALID')
            header = (','.join(HEADER)+'\r\n').encode('ascii')
            tail = b''.join(line+b'\r\n' for line in old)
            scoped = header + tail + suffix
            try:
                metrics = parse_csv_bytes(scoped)
            except SourceRejected as exc:
                _fail('REJECTED_NEW_M15_ROWS:' + str(exc))
            parsed = _source_rows(scoped)
            old_context = len(old)
            new_rows = parsed[old_context:]
            if metrics['symbol'] != symbol:
                _fail('SOURCE_SYMBOL_CHANGED_AFTER_CHECKPOINT')
            if not new_rows:
                _fail('SOURCE_EXTENDED_WITHOUT_CLOSED_BAR')
            if int(new_rows[0]['broker_epoch']) <= last_epoch:
                _fail('DUPLICATE_OR_OLD_BROKER_EPOCH')
            last_epoch = int(new_rows[-1]['broker_epoch'])
            source_bytes_parsed = len(scoped)

    count = len(new_rows)
    if count > max_new_bars:
        _fail('TOO_MANY_NEW_BARS_REQUIRES_BOUNDED_REVIEW')
    observations = []
    gap_events = []
    for i in range(len(parsed)-count, len(parsed)):
        row = parsed[i]
        prev = parsed[i-1] if i >= 1 else None
        if prev is not None:
            distance = int(row['broker_epoch'])-int(prev['broker_epoch'])
            if distance > 900:
                gap_events.append({'after_epoch':int(prev['broker_epoch']),
                                   'before_epoch':int(row['broker_epoch']),
                                   'interval_seconds':distance,
                                   'classification':'UNCLASSIFIED_BROKER_HISTORY_GAP_NO_FILL'})
        observations.append(_raw_features(row, parsed[max(0,i-2):i]))
    total_rows = start + count
    checkpoint = {
        'schema': SCHEMA,
        'source_bytes':len(raw),
        'source_sha256':_sha(raw),
        'rows_seen':total_rows,
        'last_broker_epoch':last_epoch,
        'symbol':symbol,
        'teacher_semantics_certified':False,
        'trading_authorized':False,
    }
    report = {
        'schema':SCHEMA,
        'status':'READ_ONLY_OBSERVATION_'+('NO_NEW_BARS' if count == 0 else 'NEW_CLOSED_BARS'),
        'observed_source_claim_not_authenticated':True,
        'data_source_claim':'MT5_TERMINAL_DEMO_CLOSED_BAR_RAW_BROKER_CLOCK',
        'symbol':symbol, 'timeframe':'M15',
        'previous_rows_seen':start, 'total_rows_seen':total_rows,
        'new_closed_bars_processed':count,
        'scoped_csv_bytes_parsed_after_prefix_check':source_bytes_parsed,
        'historical_rows_reparsed':old_context if prior_state is not None else 0,
        'prior_source_prefix_sha256_checked':prior_state is not None,
        'unclassified_gap_events_in_new_batch':gap_events,
        'raw_market_observations_not_teacher_signals':observations,
        'route_count':len(ROUTES),
        'route_states':[{'route_id':route, 'status':'BLOCKED_NO_INDEPENDENT_TEACHER_SEMANTICS',
                         'buy_eligible':False,'sell_eligible':False,'broker_order_permitted':False}
                        for route in ROUTES],
        'teacher_audio_independently_listened':False,
        'teacher_engine_example_match_certified':False,
        'orders_sent':0, 'trades_backtested':0,
        'mt5_runtime_verified':False,
    }
    return checkpoint, report


def run(csv_path: Path, checkpoint_path: Path):
    if csv_path.resolve() == checkpoint_path.resolve():
        _fail('CHECKPOINT_MUST_NOT_OVERWRITE_CSV')
    before = csv_path.stat()
    raw = csv_path.read_bytes()
    after = csv_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        _fail('SOURCE_CHANGED_WHILE_READING')
    prior = None
    if checkpoint_path.exists():
        prior = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    new_state, report = process_snapshot(raw, prior)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=checkpoint_path.parent,
                                         prefix=checkpoint_path.name+'.', suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            json.dump(new_state, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,checkpoint_path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return report


def main():
    p=argparse.ArgumentParser(description='Artin V13 read-only incremental M15 observer (NO ORDERS)')
    p.add_argument('csv',type=Path)
    p.add_argument('checkpoint',type=Path)
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    if args.report and args.report.resolve() in (args.csv.resolve(),args.checkpoint.resolve()):
        _fail('REPORT_MUST_NOT_OVERWRITE_SOURCE_OR_CHECKPOINT')
    result=run(args.csv,args.checkpoint)
    if args.report:
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'new_closed_bars_processed':result['new_closed_bars_processed'],
       'route_count':13,'orders_sent':0,'mt5_runtime_verified':False},ensure_ascii=False))


if __name__=='__main__':main()