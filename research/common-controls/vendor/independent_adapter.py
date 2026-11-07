"""Synthetic-only shared XAUUSD contract; no downloader, broker or price-file reader."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import InvalidOperation
from vendor.feed_contract import number, future_gate

def utc_ms(value):
    if not isinstance(value, str):
        raise ValueError('UTC_STRING_REQUIRED')
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('NAIVE_TIME')
    if value.microsecond % 1000:
        raise ValueError('SUBMILLISECOND_PRECISION_UNSUPPORTED')
    return int(value.astimezone(timezone.utc).timestamp() * 1000)

def ohlc(value):
    if not isinstance(value, dict) or set(value) != {'open', 'high', 'low', 'close'}:
        raise ValueError('OHLC_SCHEMA')
    p = {k: number(v) for k, v in value.items()}
    if not p['low'] <= min(p['open'], p['close']) <= max(p['open'], p['close']) <= p['high']:
        raise ValueError('OHLC_RANGE')
    return p

def receipt(raw):
    return {'scope': 'SYNTHETIC_ONLY', 'origin': 'IN_MEMORY_FIXTURE',
            'sha256': hashlib.sha256(raw).hexdigest(),
            'source': 'SYNTHETIC_DUKASCOPY_SHAPED', 'instrument': 'FIXTURE_XAU/USD',
            'canonical': 'XAUUSD', 'timezone': 'UTC', 'dst_policy': 'NO_DST_UTC',
            'licence_evidence': 'SYNTHETIC_GENERATOR_NOT_MARKET_DATA',
            'provenance': 'fixture:v1'}

def aggregate(raw, metadata, start_ms, end_ms, decision_ms, calendar):
    """Half-open UTC M15 windows. Calendar explicitly classifies every M1 slot.

    OPEN requires a closed, available M1; CLOSED permits no record; UNKNOWN blocks.
    No filling or partial bars. Out-of-window records rejected, not silently discarded.
    """
    result = {'status': 'BLOCKED', 'real_data_used': False, 'trade_allowed': False,
              'fit_allowed': False, 'bars': [], 'quality_flags': [], 'coverage': None,
              'gate': future_gate({})}
    try:
        if not isinstance(metadata, dict) or metadata.get('scope') != 'SYNTHETIC_ONLY' or metadata.get('origin') != 'IN_MEMORY_FIXTURE':
            raise ValueError('SYNTHETIC_ONLY')
        if type(raw) is not bytes:
            raise ValueError('IMMUTABLE_RAW_REQUIRED')
        sha = hashlib.sha256(raw).hexdigest()
        if metadata.get('sha256') != sha:
            raise ValueError('HASH_MISMATCH')
        expected = receipt(raw)
        if metadata != expected:
            raise ValueError('SOURCE_OR_PROVENANCE_SCHEMA')
        if any(type(x) is not int or x < 0 for x in (start_ms, end_ms, decision_ms)) or start_ms % 900000 or end_ms % 900000 or end_ms <= start_ms:
            raise ValueError('WINDOW_ALIGNMENT')
        if end_ms - start_ms > 86400000:
            raise ValueError('FIXTURE_WINDOW_LIMIT')
        slots = list(range(start_ms, end_ms, 60000))
        if not isinstance(calendar, dict) or set(calendar) != set(slots) or any(v not in ('OPEN', 'CLOSED', 'UNKNOWN') for v in calendar.values()):
            raise ValueError('CALENDAR_SCHEMA')
        if 'UNKNOWN' in calendar.values():
            raise ValueError('SESSION_UNKNOWN')
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError('ROWS_SCHEMA')
        parsed = {}; previous = None
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'open_ms', 'close_ms', 'available_ms', 'bid', 'ask'}:
                raise ValueError('M1_SCHEMA')
            t, close, available = (row[k] for k in ('open_ms', 'close_ms', 'available_ms'))
            if any(type(x) is not int for x in (t, close, available)) or t not in calendar or t % 60000 or close != t + 60000:
                raise ValueError('M1_TIME')
            if t in parsed:
                raise ValueError('DUPLICATE')
            if previous is not None and t < previous:
                raise ValueError('UNSORTED')
            if available < close or available > decision_ms:
                raise ValueError('LOOKAHEAD_OR_UNCLOSED')
            if calendar[t] != 'OPEN':
                raise ValueError('RECORD_IN_CLOSED_SESSION')
            bid, ask = ohlc(row['bid']), ohlc(row['ask'])
            if any(bid[k] > ask[k] for k in bid):
                raise ValueError('CROSSED_SIDE_ENVELOPE')
            parsed[t] = (bid, ask, available)
            previous = t
        expected_count = sum(v == 'OPEN' for v in calendar.values())
        missing = [t for t in slots if calendar[t] == 'OPEN' and t not in parsed]
        result['coverage'] = {'expected_open_minutes': expected_count, 'observed_minutes': len(parsed),
                              'closed_minutes': len(slots)-expected_count, 'missing_minutes': len(missing),
                              'ratio': len(parsed)/expected_count if expected_count else None,
                              'calendar': 'EXPLICIT_SYNTHETIC_ONLY'}
        if missing:
            raise ValueError('MISSING_OPEN_MINUTES_NO_FILL')
        bars = []
        for begin in range(start_ms, end_ms, 900000):
            window = list(range(begin, begin + 900000, 60000))
            if all(calendar[t] == 'CLOSED' for t in window):
                continue
            if any(calendar[t] == 'CLOSED' for t in window):
                raise ValueError('PARTIAL_SESSION_BUCKET')
            if begin + 900000 > decision_ms:
                raise ValueError('LOOKAHEAD_OR_UNCLOSED')
            bar = {'open_ms': begin, 'close_ms': begin+900000,
                   'available_ms': max(parsed[t][2] for t in window),
                   'source': metadata['source'], 'instrument': metadata['instrument'], 'canonical': 'XAUUSD',
                   'timezone': 'UTC', 'dst_policy': metadata['dst_policy'], 'session': 'SYNTHETIC_OPEN',
                   'raw_sha256': sha, 'licence_evidence': metadata['licence_evidence'], 'provenance': metadata['provenance'],
                   'spread': {'value': None, 'status': 'UNKNOWN', 'reason': 'OHLC_EXTREMA_NOT_SYNCHRONIZED_QUOTES'},
                   'quality_flags': ['SYNTHETIC_ONLY', 'NO_INTRABAR_PATH', 'SPREAD_UNKNOWN']}
            for side, index in (('bid', 0), ('ask', 1)):
                p = [parsed[t][index] for t in window]
                bar[side] = {'open': str(p[0]['open']), 'high': str(max(x['high'] for x in p)),
                             'low': str(min(x['low'] for x in p)), 'close': str(p[-1]['close'])}
            bars.append(bar)
        result.update(status='SYNTHETIC_PASS', bars=bars, raw_sha256_before=sha,
                      raw_sha256_after=hashlib.sha256(raw).hexdigest(), metadata=dict(metadata))
    except (ValueError, TypeError, KeyError, InvalidOperation, UnicodeError) as exc:
        result['quality_flags'].append(str(exc))
    return result

def quote_spread(bid, ask, bid_ms, ask_ms):
    """Only a genuinely synchronous quote can supply a numeric spread."""
    if type(bid_ms) is not int or type(ask_ms) is not int or bid_ms < 0 or ask_ms < 0 or bid_ms != ask_ms:
        raise ValueError('UNSYNCHRONIZED_QUOTE')
    b, a = number(bid), number(ask)
    if a < b:
        raise ValueError('CROSSED_QUOTE')
    return str(a-b)
