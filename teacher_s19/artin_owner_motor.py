"""Artin 13-route research motor on broker-shaped M15 OHLC observations.

This is an executable adapter to the PINNED legacy decision and paper lifecycle
engine, not a new strategy or a trade executor. Never upgrades machine ASR to
teacher proof, manufactures a sentiment, position, stop or take-profit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

CORE_COMMIT = 'b48fb06f8b2b0d134292025f5b27fc670ad2a293'
INTERVAL = 900
FIELDS = ('time_raw_epoch', 'open', 'high', 'low', 'close')

class EvidenceError(ValueError):
    pass


def read_observations(source: Path, writer):
    """Stream-validate provenance and convert raw OHLC without interpretation."""
    digest = hashlib.sha256()
    total = 0
    previous = None
    with Path(source).open('rb') as fh:
        for raw in fh:
            digest.update(raw)
            total += 1
            try:
                item = json.loads(raw)
            except (UnicodeError, ValueError) as exc:
                raise EvidenceError(f'INVALID_ORIGINAL_ROW:{total}') from exc
            if type(item.get('source_row_index')) is not int or item['source_row_index'] != total-1:
                raise EvidenceError(f'ROW_INDEX_MISMATCH:{total}')
            if item.get('teacher_trade_decision') != 'NOT_VERIFIED' or item.get('trade_or_profit_result') is not None:
                raise EvidenceError(f'UNSUPPORTED_TEACHER_CERTIFICATION:{total}')
            stamp = item.get('raw_open_epoch_no_certified_utc_offset')
            if type(stamp) is not int or stamp <= 0 or stamp % INTERVAL:
                raise EvidenceError(f'INVALID_M15_TIME:{total}')
            if previous is not None and stamp <= previous:
                raise EvidenceError(f'DUPLICATE_OR_REVERSED_TIME:{total}')
            if item.get('prior_bar_contiguous') is not (previous is not None and stamp-previous == INTERVAL):
                raise EvidenceError(f'CONTIGUITY_MISMATCH:{total}')
            try:
                from decimal import Decimal
                o, h, l, c = [Decimal(str(item[k])) for k in ('open', 'high', 'low', 'close')]
            except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
                raise EvidenceError(f'INVALID_PRICE:{total}') from exc
            if not all(v.is_finite() and v > 0 for v in (o, h, l, c)) or not l <= min(o,c) <= max(o,c) <= h:
                raise EvidenceError(f'INVALID_OHLC:{total}')
            writer.writerow((stamp, *(str(v) for v in (o,h,l,c))))
            previous = stamp
    if total == 0:
        raise EvidenceError('EMPTY_SOURCE')
    return {'original_observations_sha256':digest.hexdigest(), 'rows':total,
            'last_native_epoch':previous, 'source_teacher_verification':False}


def run_motor(observations: Path, core_dir: Path, out_dir: Path, allowed_rules=None):
    core_dir = Path(core_dir).resolve()
    # Import the existing actual decision/management engine rather than inventing one.
    for n in ('entry_engine.py','raw_pipeline.py','monthly_execution.py','trade_machine.py','run_raw.py'):
        if not (core_dir/n).is_file():
            raise EvidenceError(f'PINNED_ENGINE_MODULE_MISSING:{n}')
    manifest = core_dir/'LEGACY_SHA_MANIFEST.json'
    if not manifest.is_file():
        raise EvidenceError('PINNED_MANIFEST_REQUIRED')
    expected = json.loads(manifest.read_text(encoding='utf8'))
    if expected.get('source_commit') != CORE_COMMIT:
        raise EvidenceError('WRONG_ENGINE_REVISION')
    for name,sha in expected.get('files_sha256',{}).items():
        p = core_dir/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
            raise EvidenceError(f'ENGINE_SOURCE_TAMPERED:{name}')
    sys.path.insert(0,str(core_dir))
    try:
        entry = importlib.import_module('entry_engine')
        runner = importlib.import_module('run_raw')
        if Path(runner.__file__).resolve() != core_dir/'run_raw.py':
            raise EvidenceError('UNEXPECTED_ENGINE_IMPORT')
        ids = tuple(entry.RULE_IDS)
        if len(ids)!=13 or len(set(ids))!=13:
            raise EvidenceError('THIRTEEN_ENGINE_ROUTES_REQUIRED')
        selected = ids if allowed_rules is None else tuple(allowed_rules)
        if not selected or len(selected)!=len(set(selected)) or not set(selected).issubset(ids):
            raise EvidenceError('INVALID_RULE_SELECTION')
        destination = Path(out_dir)
        destination.mkdir(parents=True,exist_ok=True)
        if destination.resolve() == Path(observations).resolve() or destination.resolve()==core_dir:
            raise EvidenceError('UNSAFE_OUTPUT_TARGET')
        with tempfile.TemporaryDirectory(prefix='artin-owner-motor-') as td:
            csvpath = Path(td)/'private_original_ohlc.csv'
            with csvpath.open('w',newline='',encoding='utf8') as f:
                writer = csv.writer(f,lineterminator='\n')
                writer.writerow(FIELDS)
                provenance = read_observations(observations,writer)
            # No Context document => no invented teacher context; no execution
            # document => no invented SL/TP or paper fills. This is intentional.
            result=runner.run(csvpath,destination,INTERVAL,allowed_rules=selected,
                              protected_inputs=(Path(observations),),
                              plan_id='ARTIN_OWNER_ACTUAL_13_BRANCH_MOTOR')
        decision_counts = result['decisions_by_side']
        eligible = len(result['eligible_entries'])
        if result['observed_bars']!=provenance['rows']:
            raise EvidenceError('ENGINE_SOURCE_ROW_MISMATCH')
        if result['actual_entry_evaluations']!=provenance['rows']*2*len(selected):
            raise EvidenceError('ENGINE_DECISION_COUNT_MISMATCH')
        if result['orders_sent'] != 0:
            raise EvidenceError('UNAUTHORIZED_ORDER_REPORTED')
        evidence={'schema':'artin_owner_actual_engine_execution_v1',
                  'engine_commit':CORE_COMMIT,'source':provenance,
                  'actual_engine_branches':list(selected),'engine_branches_count':len(selected),
                  'bars_replayed':provenance['rows'],
                  'decision_evaluations':result['actual_entry_evaluations'],
                  'decisions_by_side':decision_counts,'candidate_eligible':eligible,
                  'paper_trades_opened':result['paper_trades_opened'],
                  'semantic_teacher_rules_approved':0,
                  'historical_teacher_context_supplied':False,
                  'execution_specs_supplied':False,
                  'teacher_fidelity_test_completed':False,
                  'strategy_profitability_test_completed':False,
                  'orders_sent':0,
                  'state':'ENGINE_EXECUTED_ON_SOURCE_BARS_TEACHER_RULES_NOT_CERTIFIED',
                  'why_not_a_finished_trading_engine':[
                      'independent teacher audio-chart semantic confirmation missing',
                      'causal historical sentiment and strategy context not source-certified',
                      'teacher stop and target rules and execution prices not certified'],
                  'output_summary':'SUMMARY.json',
                  'output_private_trace':'PRIVATE_raw_decisions.jsonl.gz'}
        target=destination/'OWNER_ENGINE_EXECUTION.json'
        if target.exists():
            raise EvidenceError('RECEIPT_ALREADY_EXISTS')
        target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        return evidence
    finally:
        sys.path.remove(str(core_dir))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations',type=Path,required=True)
    p.add_argument('--pinned-core',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--rule',action='append',help='Exact historical 13 route id; defaults to all')
    a=p.parse_args()
    result=run_motor(a.observations,a.pinned_core,a.out,a.rule)
    print(json.dumps({k:result[k] for k in ('engine_branches_count','bars_replayed','decision_evaluations','candidate_eligible','paper_trades_opened','orders_sent','state')},ensure_ascii=False))

if __name__=='__main__':main()