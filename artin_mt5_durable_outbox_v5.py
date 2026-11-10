#!/usr/bin/env python3
"""Crash-recoverable, read-only Artin MT5 M15 evidence outbox.

Persist an immutable observation receipt before advancing the V4 checkpoint.
A process crash in between is replayed by validating the committed receipt
against the unchanged SHA-256 pinned prefix of the CSV, not by dropping bars.

Source CSV is a CLAIM of broker provenance, never broker authentication;
no execution, teacher certification, price prediction or trade calls exist.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from artin_mt5_incremental_observer_v4 import (
    SCHEMA as V4_SCHEMA, ObserverBlocked, process_snapshot,
)

SCHEMA = 'artin_v13_durable_m15_evidence_outbox_v5'
RECEIPT_SCHEMA = 'artin_v13_durable_m15_observation_receipt_v5'
SHA = re.compile(r'[0-9a-f]{64}\Z')
RECEIPT_NAME = re.compile(r'batch_(\d{6})_([0-9a-f]{16})\.json\Z')


def blocked(reason: str):
    raise ObserverBlocked(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pack(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _sync_dir(path: Path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def atomic_write(path: Path, data: bytes, *, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent,
                                         prefix='.artin_v5_', suffix='.tmp', delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if immutable and path.exists():
            if path.read_bytes() != data:
                blocked('EXISTING_OUTBOX_RECEIPT_DIFFERS')
        else:
            os.replace(tmp, path)
            _sync_dir(path.parent)
    finally:
        if tmp is not None and tmp.exists(): tmp.unlink()


@contextmanager
def state_lock(path: Path):
    """Kernel-held advisory lock; automatically released if process dies."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+b') as f:
        if os.name == 'nt':
            import msvcrt
            if f.seek(0, os.SEEK_END) == 0:
                f.write(b'0'); f.flush()
            f.seek(0)
            try: msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError: blocked('CONCURRENT_OBSERVER_PROCESS')
            try: yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try: fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError: blocked('CONCURRENT_OBSERVER_PROCESS')
            try: yield
            finally: fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _source_bytes(path: Path) -> bytes:
    before = path.stat()
    if before.st_size > 30_000_000: blocked('OVERSIZED_SOURCE_CSV')
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        blocked('SOURCE_CHANGED_DURING_SNAPSHOT')
    return data


def _read_json(path: Path, *, max_bytes=25_000_000):
    if not path.is_file() or path.stat().st_size > max_bytes:
        blocked('MISSING_OR_OVERSIZED_EVIDENCE_FILE')
    try: return json.loads(path.read_bytes())
    except (UnicodeError, ValueError, OSError): blocked('MALFORMED_EVIDENCE_JSON')


def _receipt_for(path: Path, expected_seq: int) -> tuple[dict, str]:
    m = RECEIPT_NAME.fullmatch(path.name)
    if not m or int(m.group(1)) != expected_seq:
        blocked('INVALID_EVIDENCE_RECEIPT_FILENAME')
    if not path.is_file() or path.stat().st_size > 25_000_000:
        blocked('MISSING_OR_OVERSIZED_EVIDENCE_FILE')
    raw = path.read_bytes()
    h = sha(raw)
    if h[:16] != m.group(2): blocked('RECEIPT_SHA_FILENAME_MISMATCH')
    try: body = json.loads(raw)
    except (UnicodeError, ValueError): blocked('MALFORMED_RECEIPT_JSON')
    if not isinstance(body, dict) or body.get('schema') != RECEIPT_SCHEMA or body.get('sequence') != expected_seq:
        blocked('RECEIPT_SCHEMA_SEQUENCE_MISMATCH')
    if body.get('trading_authorized') is not False or body.get('teacher_semantics_certified') is not False:
        blocked('UNSUPPORTED_SEMANTIC_TRADE_CERTIFICATION')
    report = body.get('report')
    if not isinstance(report, dict) or report.get('orders_sent') != 0 or report.get('route_count') != 13:
        blocked('RECEIPT_CLAIMS_TRADING_OR_MISSING_ROUTES')
    if report.get('teacher_audio_independently_listened') is not False or report.get('teacher_engine_example_match_certified') is not False:
        blocked('RECEIPT_FALSE_TEACHER_VERIFICATION')
    states = report.get('route_states')
    if not isinstance(states, list) or len(states) != 13 or any(
        not isinstance(s, dict) or s.get('broker_order_permitted') is not False or
        s.get('buy_eligible') is not False or s.get('sell_eligible') is not False
        for s in states
    ):
        blocked('RECEIPT_ROUTES_NOT_ALL_BLOCKED')
    after = body.get('checkpoint_after')
    if not isinstance(after, dict) or after.get('schema') != V4_SCHEMA:
        blocked('INVALID_V4_CHECKPOINT_INSIDE_RECEIPT')
    if after.get('trading_authorized') is not False or after.get('teacher_semantics_certified') is not False:
        blocked('UNSUPPORTED_CHECKPOINT_TRADE_CERTIFICATION')
    before = body.get('checkpoint_before')
    if before is not None and (not isinstance(before, dict) or before.get('schema') != V4_SCHEMA):
        blocked('INVALID_PRIOR_CHECKPOINT_INSIDE_RECEIPT')
    old_rows = 0 if before is None else before.get('rows_seen', -10**9)
    if type(after.get('rows_seen')) is not int or type(old_rows) is not int or after['rows_seen'] <= old_rows:
        blocked('INVALID_RECEIPT_ROW_PROGRESS')
    if report.get('new_closed_bars_processed') != after['rows_seen'] - old_rows:
        blocked('RECEIPT_ROW_COUNT_MISMATCH')
    return body, h


def _envelope(seq: int, path: Path, digest: str, body: dict) -> dict:
    return {'schema':SCHEMA,'sequence':seq,
            'checkpoint':body['checkpoint_after'],
            'last_receipt':{'filename':path.name,'sha256':digest},
            'teacher_semantics_certified':False,'trading_authorized':False}


def _load_state(state: Path, outbox: Path):
    if not state.exists(): return None
    env = _read_json(state, max_bytes=100_000)
    if not isinstance(env, dict) or env.get('schema') != SCHEMA:
        blocked('INVALID_DURABLE_STATE_SCHEMA')
    seq = env.get('sequence')
    if type(seq) is not int or seq < 1 or seq > 999999:
        blocked('INVALID_DURABLE_SEQUENCE')
    if env.get('teacher_semantics_certified') is not False or env.get('trading_authorized') is not False:
        blocked('UNSUPPORTED_STATE_TRADE_CERTIFICATION')
    ref = env.get('last_receipt')
    if not isinstance(ref, dict) or not isinstance(ref.get('filename'), str) or not isinstance(ref.get('sha256'), str):
        blocked('MISSING_DURABLE_RECEIPT_REFERENCE')
    if not SHA.fullmatch(ref['sha256']) or not RECEIPT_NAME.fullmatch(ref['filename']):
        blocked('INVALID_DURABLE_RECEIPT_REFERENCE')
    path = outbox / ref['filename']
    body, digest = _receipt_for(path, seq)
    if digest != ref['sha256'] or body['checkpoint_after'] != env.get('checkpoint'):
        blocked('CHECKPOINT_REPORT_MISMATCH')
    return env


def _next_receipt_candidates(outbox: Path, seq: int):
    return sorted(outbox.glob(f'batch_{seq:06d}_*.json'))


def _recover_orphan(raw: bytes, env, state: Path, outbox: Path):
    seq = 1 if env is None else env['sequence'] + 1
    candidates = _next_receipt_candidates(outbox, seq)
    if not candidates: return env, 0
    if len(candidates) != 1: blocked('AMBIGUOUS_UNCOMMITTED_OUTBOX_RECEIPTS')
    path = candidates[0]
    body, digest = _receipt_for(path, seq)
    previous = None if env is None else env['checkpoint']
    if body.get('checkpoint_before') != previous:
        blocked('ORPHAN_PRIOR_CHECKPOINT_MISMATCH')
    after = body['checkpoint_after']
    n = after.get('source_bytes')
    if type(n) is not int or n < 1 or n > len(raw) or sha(raw[:n]) != after.get('source_sha256'):
        blocked('ORPHAN_CSV_PREFIX_MISMATCH')
    if type(after.get('rows_seen')) is not int or after['rows_seen'] <= (0 if previous is None else previous['rows_seen']):
        blocked('ORPHAN_CHECKPOINT_NOT_ADVANCING')
    # A self-consistent JSON with a freshly recomputed hash is not proof of
    # a valid batch. Replay its exact committed source prefix to revalidate
    # every row, report and checkpoint with V4's fail-closed data contract.
    replay_checkpoint, replay_report = process_snapshot(raw[:n], previous)
    if replay_checkpoint != after or replay_report != body['report']:
        blocked('ORPHAN_REPORT_NOT_REPRODUCIBLE_FROM_PINNED_SOURCE')
    new_env = _envelope(seq, path, digest, body)
    atomic_write(state, pack(new_env))
    return new_env, 1


def _make_receipt(seq: int, prior, checkpoint: dict, report: dict):
    body = {'schema':RECEIPT_SCHEMA,'sequence':seq,
            'checkpoint_before':prior,
            'checkpoint_after':checkpoint,
            'report':report,'trading_authorized':False,
            'teacher_semantics_certified':False}
    data = pack(body)
    digest = sha(data)
    filename = f'batch_{seq:06d}_{digest[:16]}.json'
    return filename, data, body, digest


def run(csv: Path, state: Path, outbox: Path, *, on_receipt_committed=None):
    csv, state, outbox = Path(csv), Path(state), Path(outbox)
    if csv.resolve() == state.resolve() or state.resolve() == outbox.resolve() or csv.resolve() == outbox.resolve():
        blocked('OUTPUT_PATH_ALIASES_INPUT')
    if outbox.exists() and not outbox.is_dir(): blocked('OUTBOX_PATH_NOT_DIRECTORY')
    outbox.mkdir(parents=True, exist_ok=True)
    with state_lock(state.with_suffix(state.suffix+'.lock')):
        raw = _source_bytes(csv)
        env = _load_state(state, outbox)
        env, recovered = _recover_orphan(raw, env, state, outbox)
        checkpoint_before = None if env is None else env['checkpoint']
        checkpoint, report = process_snapshot(raw, checkpoint_before)
        if report['new_closed_bars_processed'] == 0:
            return {'status':'NO_NEW_BARS', 'new_closed_bars':0,
                    'recovered_uncommitted_receipts':recovered,
                    'last_receipt':None if env is None else env['last_receipt']['filename'],
                    'orders_sent':0, 'teacher_semantics_certified':False}
        seq = 1 if env is None else env['sequence']+1
        if seq > 999999: blocked('OUTBOX_SEQUENCE_LIMIT')
        name, data, body, digest = _make_receipt(seq, checkpoint_before, checkpoint, report)
        # If another same-sequence file exists, fail closed; never silently
        # replace a batch with a different content hash.
        candidates = _next_receipt_candidates(outbox, seq)
        if candidates and [x.name for x in candidates] != [name]:
            blocked('DIFFERENT_BATCH_ALREADY_STAGED')
        receipt = outbox/name
        atomic_write(receipt, data, immutable=True)
        if on_receipt_committed is not None:
            on_receipt_committed(receipt)  # test-only deterministic crash injection
        # Only after receipt + directory fsync is the checkpoint advanced.
        atomic_write(state, pack(_envelope(seq, receipt, digest, body)))
        return {'status':'DURABLE_NEW_CLOSED_BARS',
                'new_closed_bars':report['new_closed_bars_processed'],
                'total_rows_seen':checkpoint['rows_seen'],
                'recovered_uncommitted_receipts':recovered,
                'last_receipt':receipt.name,
                'receipt_sha256':digest,
                'orders_sent':0,'teacher_semantics_certified':False,
                'source_claim_not_authenticated':True}


def main():
    p=argparse.ArgumentParser(description='Artin V13 V5 durable read-only evidence outbox (NO TRADES)')
    p.add_argument('csv',type=Path)
    p.add_argument('state',type=Path)
    p.add_argument('outbox',type=Path)
    a=p.parse_args()
    print(json.dumps(run(a.csv,a.state,a.outbox),ensure_ascii=False,indent=2))


if __name__=='__main__': main()