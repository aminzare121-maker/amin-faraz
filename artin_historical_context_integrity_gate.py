#!/usr/bin/env python3
"""Fail-closed post-replay provenance inspection for Artin's 13 entry routes.

Audits the actual legacy engine output without inferring teacher meaning, injecting
fabricated economic bias, opening a broker connection or computing any P&L.
The historical broker's raw epoch labels are NOT treated as verified UTC.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROUTES = ('PULLBACK_STANDARD', 'REVERSAL_CLASSIC', 'REVERSAL_THREE',
          'REVERSAL_STAR', 'BREAK_STRONG', 'BREAK_WEAK_PIVOT',
          'BREAK_WEAK_FULLBODY_EXCEPTION', 'BREAK_VERY_STRONG_RETEST',
          'STOPPUNCH_SAME_COLOUR', 'STOPPUNCH_DOJI_AHEAD',
          'STOPPUNCH_DOJI_TIED', 'STOPPUNCH_OPPOSITE_CONFIRMATION',
          'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE')
CLOCK='RAW_BROKER_LABELS_NOT_VERIFIED_UTC'


def hash_file(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def check_row(row, previous_at=None):
    """Validate a *real* engine trace row, not a teacher or strategy verdict."""
    at=row.get('at');opened=row.get('bar_opened_at')
    if type(at) is not int or type(opened) is not int or opened<0 or at-opened !=900:
        raise ValueError('invalid closed candle timestamp')
    if previous_at is not None and at<=previous_at:
        raise ValueError('non-ascending market time')
    if row.get('broker_connected') is not False or row.get('orders_sent')!=0:
        raise ValueError('replay must not claim broker connection or orders')
    if row.get('original_direction_evidence') is not None:
        raise ValueError('unassisted trace unexpectedly has economic direction context')
    if row.get('direction_plan') is not None or row.get('active_context_windows'):
        raise ValueError('unassisted trace unexpectedly has supplied context')
    if not isinstance(row.get('decisions'),list) or len(row['decisions'])!=26:
        raise ValueError('exactly 13 rules by BUY/SELL required')
    keys=set();derived=Counter();missing=Counter();status=Counter()
    for decision in row['decisions']:
        key=(decision.get('rule_id'),decision.get('side'))
        if key[0] not in ROUTES or key[1] not in ('BUY','SELL') or key in keys:
            raise ValueError('wrong or duplicate rule/side')
        keys.add(key)
        if decision.get('status')!='REVIEW' or decision.get('order_created') is not False:
            raise ValueError('unassisted entry must remain REVIEW and create no orders')
        if 'sentiment_permission' not in decision.get('missing_dependencies',[]):
            raise ValueError('economic direction missingness must be explicit')
        if decision.get('future_dependencies'):
            raise ValueError('future dependency used')
        if decision.get('supplied_context_keys') or decision.get('context_required_keys'):
            raise ValueError('supplied context not allowed in baseline replay')
        facts=decision.get('dependency_facts')
        if not isinstance(facts,dict):raise ValueError('missing fact provenance')
        for name, fact in facts.items():
            ts=fact.get('known_at')
            if type(ts) is not int or ts<0 or ts>at:
                raise ValueError('LOOKAHEAD:'+name)
            if fact.get('origin') not in ('DERIVED_FROM_RAW','DERIVED_MIXED'):
                raise ValueError('unexpected fact origin in unassisted replay:'+name)
            if not isinstance(fact.get('source'),str) or not fact['source']:
                raise ValueError('derived fact without provenance:'+name)
            derived[(key[0],name)]+=1
        for name in decision['missing_dependencies']:
            missing[(key[0],name)]+=1
        status[(key[0],key[1],decision['status'])]+=1
    return status,missing,derived


def analyze(summary_file, trace_file, source_csv, execution_file):
    summary_file,trace_file,source_csv,execution_file=map(Path,(summary_file,trace_file,source_csv,execution_file))
    summary=json.loads(summary_file.read_text(encoding='utf-8'))
    execution=json.loads(execution_file.read_text(encoding='utf-8'))
    if summary.get('clock_basis')!=CLOCK:
        raise ValueError('broker clock basis is not the reviewed unverified-UTC label')
    if hash_file(source_csv)!=summary.get('csv_sha256'):
        raise ValueError('source raw OHLC changed')
    if tuple(summary.get('provenance',{}).get('entry_rule_plan',{}).get('allowed_rules',()))!=ROUTES:
        raise ValueError('engine rules differ from pinned 13-rule list')
    if summary.get('economic_context_events')!=0 or summary.get('strategy_backtest_complete') is not False:
        raise ValueError('replay must be context-free and not declare strategy success')
    if summary.get('strategy_pnl_usd') is not None or summary.get('orders_sent')!=0:
        raise ValueError('fake P&L or orders claim')
    if not isinstance(execution.get('events'),list) or execution['events']:
        raise ValueError('unexpected execution events')
    counts=Counter(); missing=Counter(); derived=Counter();last=None;rows=0
    with gzip.open(trace_file,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            st,mi,de=check_row(r,last)
            counts.update(st);missing.update(mi);derived.update(de)
            last=r['at'];rows+=1
    if rows!=summary['observed_bars'] or rows*26!=summary['actual_entry_evaluations']:
        raise ValueError('trace truncated or counted incorrectly')
    if sum(missing[(r,'sentiment_permission')] for r in ROUTES)!=rows*26:
        raise ValueError('missing sentiment count mismatch')
    if sum(missing[(r,'current_setup')] for r in ROUTES)!=summary['missing_dependency_occurrences']['current_setup']:
        raise ValueError('missing current setup mismatch')
    if sum(derived[(r,'current_setup')] for r in ROUTES)!=summary['automatically_derived_dependency_occurrences']['current_setup']:
        raise ValueError('derived current_setup mismatch')
    by_route=[]
    for r in ROUTES:
        by_route.append({
            'rule_id':r,'BUY_REVIEW':counts[(r,'BUY','REVIEW')], 'SELL_REVIEW':counts[(r,'SELL','REVIEW')],
            'missing_sentiment_permission':missing[(r,'sentiment_permission')],
            'missing_current_setup':missing[(r,'current_setup')],
            'raw_derived_current_setup_not_teacher_certified':derived[(r,'current_setup')],
            'top_other_missing_predicates':[
                {'predicate':name,'occurrences':v} for (route,name),v in sorted(
                    missing.items(),key=lambda item:(-item[1],item[0][0],item[0][1]))
                if route==r and name not in ('sentiment_permission','current_setup')
            ][:20],
            'status':'NO_ENTRY_AUTHORIZED_MISSING_HISTORICAL_AND_TEACHER_CONTEXT'
        })
    return {
        'schema':'artin_13_engine_actual_context_integrity_v1',
        'original_csv_sha256':summary['csv_sha256'],
        'original_engine_run_summary_sha256':hash_file(summary_file),
        'original_engine_trace_sha256':hash_file(trace_file),
        'bars_examined':rows,'rules_examined':len(ROUTES),
        'real_engine_decision_count':rows*26,
        'status_counts':{'REVIEW':sum(counts.values()),'ELIGIBLE':0},
        'missing_sentiment_permission_count':rows*26,
        'missing_current_setup_count':summary['missing_dependency_occurrences']['current_setup'],
        'raw_derived_current_setup_not_teacher_certified':summary['automatically_derived_dependency_occurrences']['current_setup'],
        'data_clock_basis':CLOCK,
        'historical_utc_calibration_verified':False,
        'causal_market_source_checks_passed':True,
        'future_dependency_used':False,
        'historic_economic_news_merged_into_broker_epoch':False,
        'teacher_independent_semantic_verification':False,
        'broker_orders_sent':0,'strategic_pnl_calculated':False,
        'per_rule':by_route,
        'next_blockers_in_order':[
            'Verify broker historical time/DST mapping before joining UTC economic releases',
            'Collect historical economic releases with independently documented publication/availability timestamps',
            'Verify teacher interpretation of direction, setup, all 13 entries, SL/TP and exceptions against original speech and actual chart examples',
            'Only then run source-bound contexts and cost-aware PAPER backtest; no automatic live trades'
        ]
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--summary',type=Path,required=True)
    p.add_argument('--trace',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--execution',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    sources=(a.summary,a.trace,a.source,a.execution)
    if any(a.output.resolve()==x.resolve() for x in sources):
        raise SystemExit('source is immutable')
    result=analyze(*sources)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('bars_examined','rules_examined','real_engine_decision_count','status_counts','missing_current_setup_count','raw_derived_current_setup_not_teacher_certified')},ensure_ascii=False))

if __name__=='__main__':main()