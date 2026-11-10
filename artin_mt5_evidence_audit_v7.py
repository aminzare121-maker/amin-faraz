#!/usr/bin/env python3
"""Independent, file-only audit of the complete Artin V5 M15 receipt chain.

Optionally consume an existing V2 CSV with V5 exactly once before auditing.
Evidence is local files only; NEVER claim MetaEditor/MT5/Eplanet authentication,
teacher semantics, trade readiness, trading permission, or live market success.
Existing V2..V6 source code and V5 receipts are never changed by this audit.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from artin_mt5_local_observer_launcher import (
    LaunchBlocked, poll_once, select_source, state_paths, user_output_root,
)
from artin_mt5_durable_outbox_v5 import (
    ObserverBlocked, RECEIPT_NAME, _load_state, _receipt_for,
    _source_bytes, atomic_write, pack, sha, state_lock,
)
from artin_mt5_incremental_observer_v4 import process_snapshot

SCHEMA = 'artin_v13_v7_read_only_full_chain_audit'
WITNESS_SCHEMA = 'artin_v13_v7_local_file_observation_witness'
MAX_RECEIPTS = 10000


class AuditBlocked(ValueError):
    pass


def blocked(reason: str):
    raise AuditBlocked(reason)


def audit_chain(source: Path, state: Path, outbox: Path) -> dict:
    """Replay every receipt against the actual immutable historical CSV prefix.

    No report/state writes, aside from a shared advisory lock file.
    This is stronger than only checking V5's last
    checkpoint: it also detects missing/tampered *earlier* receipt files.
    """
    source, state, outbox = Path(source), Path(state), Path(outbox)
    if not source.is_file():
        blocked('V2_SOURCE_CSV_NOT_FOUND')
    if not state.is_file():
        blocked('V5_CHECKPOINT_NOT_FOUND_RUN_V5_ON_EXISTING_CSV_FIRST')
    if not outbox.is_dir():
        blocked('V5_OUTBOX_NOT_FOUND')
    # Match V5's own lock; never inspect a half-updated checkpoint/receipt pair.
    with state_lock(state.with_suffix(state.suffix + '.lock')):
        raw = _source_bytes(source)
        env = _load_state(state, outbox)
        if env is None:
            blocked('V5_CHECKPOINT_NOT_FOUND')
        seq = env['sequence']
        if seq > MAX_RECEIPTS:
            blocked('V5_CHAIN_TOO_LONG_REQUIRES_BOUNDED_REVIEW')
        files = sorted(outbox.glob('batch_*.json'))
        if len(files) != seq:
            blocked('V5_RECEIPT_CHAIN_LENGTH_MISMATCH')
        prior = None
        prev_length = 0
        total_new_rows = 0
        for n, path in enumerate(files, 1):
            if RECEIPT_NAME.fullmatch(path.name) is None or int(path.name[6:12]) != n:
                blocked('V5_RECEIPT_CHAIN_GAP_OR_INVALID_NAME')
            body, digest = _receipt_for(path, n)
            if body.get('checkpoint_before') != prior:
                blocked('V5_PRIOR_CHECKPOINT_CHAIN_MISMATCH')
            after = body['checkpoint_after']
            end = after.get('source_bytes')
            if type(end) is not int or not prev_length < end <= len(raw):
                blocked('V5_RECEIPT_SOURCE_PREFIX_LENGTH_INVALID')
            prefix = raw[:end]
            if sha(prefix) != after.get('source_sha256'):
                blocked('V5_RECEIPT_SOURCE_PREFIX_HASH_MISMATCH')
            # Critical: independently rebuild the claimed report from source.
            actual_checkpoint, actual_report = process_snapshot(prefix, prior)
            if actual_checkpoint != after or actual_report != body['report']:
                blocked('V5_RECEIPT_REPORT_NOT_REPRODUCIBLE')
            if n == seq and (env['last_receipt']['filename'] != path.name or
                             env['last_receipt']['sha256'] != digest):
                blocked('V5_LAST_RECEIPT_IDENTITY_MISMATCH')
            total_new_rows += actual_report['new_closed_bars_processed']
            prev_length = end
            prior = after
        if env['checkpoint'] != prior:
            blocked('V5_FINAL_CHECKPOINT_MISMATCH')
        if len(raw) < prev_length or sha(raw[:prev_length]) != prior['source_sha256']:
            blocked('V5_FINAL_SOURCE_PREFIX_MISMATCH')
        # New CSV bytes beyond last checkpoint might be perfectly valid but are
        # NOT claimed processed; never assert the V5 outbox has ingested them.
        unprocessed = len(raw) - prev_length
        return {
            'schema': SCHEMA,
            'status': 'FILE_BACKED_V5_CHAIN_REPLAY_VERIFIED',
            'verified_receipts': seq,
            'verified_closed_bars': total_new_rows,
            'checkpoint_rows_seen': prior['rows_seen'],
            'last_closed_bar_broker_epoch': prior['last_broker_epoch'],
            'checkpoint_csv_prefix_sha256': prior['source_sha256'],
            'unprocessed_csv_bytes_after_checkpoint': unprocessed,
            'unprocessed_bytes_require_v5_poll': unprocessed > 0,
            'all_13_trade_routes_blocked': True,
            'broker_session_authenticated': False,
            'metaeditor_compilation_authenticated': False,
            'mt5_demo_chart_attachment_verified': False,
            'teacher_semantics_certified': False,
            'orders_sent': 0,
            'proof_scope': 'LOCAL_CSV_AND_V5_RECEIPT_BYTES_ONLY_NOT_ORIGINAL_BROKER_AUTHENTICATION',
        }


def observe(source: Path, output_root: Path, *, capture_new: bool = False,
            settle_seconds: float = 0.25) -> dict:
    """Check V5; keep independent witness only after whole-chain verification."""
    source, output_root = Path(source), Path(output_root)
    state, outbox, source_id = state_paths(source, output_root)
    if capture_new:
        # V5 owns writes to its state/outbox. This optional step only uses
        # an existing V2 CSV. It cannot start the collector in MetaTrader.
        poll_once(source, output_root, settle_seconds=settle_seconds)
    result = audit_chain(source, state, outbox)
    if result['unprocessed_csv_bytes_after_checkpoint']:
        blocked('V5_CHECKPOINT_TRAILS_EXISTING_SOURCE_CSV')
    witness_path = state.parent / 'v7_file_witness.json'
    previous = None
    if witness_path.exists():
        try:
            previous = json.loads(witness_path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as exc:
            raise AuditBlocked('CORRUPT_V7_WITNESS') from exc
        if not isinstance(previous, dict) or previous.get('schema') != WITNESS_SCHEMA or previous.get('source_id') != source_id:
            blocked('INVALID_V7_WITNESS_IDENTITY')
        count, last_epoch = previous.get('rows_seen'), previous.get('last_broker_epoch')
        if type(count) is not int or type(last_epoch) is not int or count < 1 or last_epoch < 1:
            blocked('INVALID_V7_WITNESS_COUNTS')
        new_count = result['checkpoint_rows_seen']
        new_epoch = result['last_closed_bar_broker_epoch']
        if new_count < count or new_epoch < last_epoch:
            blocked('V7_LOCAL_FILE_HISTORY_REGRESSED')
        if new_count == count:
            if new_epoch != last_epoch or previous.get('sha256') != result['checkpoint_csv_prefix_sha256']:
                blocked('V7_SAME_ROW_COUNT_DIFFERENT_SOURCE')
            comparison = 'UNCHANGED_LOCAL_FILES'
            delta = 0
        else:
            if new_epoch <= last_epoch:
                blocked('V7_ROW_ADVANCE_WITHOUT_NEWER_BROKER_EPOCH')
            comparison = 'ADDITIONAL_CLOSED_BARS_IN_LOCAL_FILES'
            delta = new_count-count
    else:
        comparison = 'FIRST_LOCAL_FILE_OBSERVATION'
        delta = None
    # An independently replayed hash-chain does not authenticate broker or
    # prove the account was actually DEMO. Do not translate filename -> proof.
    witness = {
        'schema': WITNESS_SCHEMA,
        'source_id': source_id,
        'rows_seen': result['checkpoint_rows_seen'],
        'last_broker_epoch': result['last_closed_bar_broker_epoch'],
        'sha256': result['checkpoint_csv_prefix_sha256'],
        'last_checked_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(witness_path, pack(witness))
    result['source_id'] = source_id
    result['local_file_progress_since_prior_v7_check'] = comparison
    result['new_closed_bars_since_prior_v7_check'] = delta
    result['witness_written'] = True
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='ARTIN V13: audit ALL durable V5 receipts, NO orders, NO MT5 attachment')
    p.add_argument('--csv', type=Path, help='Existing V2 recovery CSV, or auto-discover unique MT5 Common Files file')
    p.add_argument('--output-root', type=Path, help='Existing V5 output folder (default LOCALAPPDATA\\ArtinV13\\read-only-live)')
    p.add_argument('--capture-new', action='store_true', help='Read CSV and ask unchanged V5 to process new bars before audit')
    p.add_argument('--settle-seconds', type=float, default=0.25)
    a = p.parse_args(argv)
    if not 0 <= a.settle_seconds <= 10:
        p.error('settle seconds must be between zero and ten')
    try:
        source = select_source(a.csv)
        root = a.output_root if a.output_root is not None else user_output_root()
        result = observe(source, root, capture_new=a.capture_new, settle_seconds=a.settle_seconds)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (AuditBlocked, LaunchBlocked, ObserverBlocked, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({'status':'BLOCKED_NO_TRADES','reason':str(exc),'orders_sent':0,
                          'broker_session_authenticated':False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())