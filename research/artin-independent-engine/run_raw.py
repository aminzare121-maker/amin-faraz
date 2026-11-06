"""Offline raw CSV runner; private trace stays local, no broker or network."""
import argparse
from collections import Counter
from dataclasses import asdict,is_dataclass
from decimal import Decimal
import gzip,json
from pathlib import Path
from entry_engine import RULE_IDS,Decision
from context_inputs import Context
from raw_pipeline import RawPipeline,read_csv
from monthly_execution import MonthlyExecutor

def serialize(v):
    if isinstance(v,Decimal):return str(v)
    if is_dataclass(v):return asdict(v)
    raise TypeError('unsupported JSON value')

def run(csv_path,output_dir,interval_seconds,contexts=(),plan_id='ARTIN_RAW_DIAGNOSTIC',
        execution_document=None,initial_cash='1000.00',fixed_lots='0.03'):
    contexts=tuple(contexts)
    candles,fingerprint=read_csv(csv_path,interval_seconds)
    if not candles:raise ValueError('empty monthly data')
    output_dir=Path(output_dir)
    # Never overwrite source CSV or place generated files on top of it.
    targets=[output_dir/n for n in ('SUMMARY.json','PRIVATE_raw_decisions.jsonl.gz','PRIVATE_execution.json')]
    if any(p.resolve()==Path(csv_path).resolve() or p.exists() and p.samefile(csv_path) for p in targets):
        raise ValueError('output aliases input')
    output_dir.mkdir(parents=True,exist_ok=True)
    pipeline=RawPipeline(plan_id,RULE_IDS,interval_seconds,fingerprint,contexts)
    executor=MonthlyExecutor(pipeline.engine,initial_cash,fixed_lots,execution_document)
    statuses={side:Counter() for side in ('BUY','SELL')};missing=Counter();shapes=Counter();candidates=Counter()
    derived=Counter();gaps=0;eligible=[]
    with gzip.open(targets[1],'wt',encoding='utf8') as f:
        for bar in candles:
            executor.advance(bar.closed_at)
            result=pipeline.step(bar);gaps+=int(result['gap_before_bar'])
            for k,p in result['predicates'].items():shapes[k+':'+str(p['value'])]+=1
            for c in result['new_candidates']:candidates[c['kind']+':'+c['direction']]+=1
            for d in result['decisions']:
                statuses[d['side']][d['status']]+=1
                missing.update(d['missing_dependencies']);derived.update(d['derived_required_keys'])
                if d['status']=='ELIGIBLE':eligible.append({'at':result['at'],'side':d['side'],'rule_id':d['rule_id']})
                # Route the actual immutable observation into the execution ledger.
                decision=Decision(d['rule_id'],d['status'],tuple(d['reasons']),tuple(d['sources']),d['input_fingerprint'])
                executor.accept(decision,pipeline.latest_observation(d['side']))
            executor.advance(bar.closed_at,strict=True)
            f.write(json.dumps(result,ensure_ascii=False,default=serialize,separators=(',',':'))+'\n')
    execution=executor.summary()
    targets[2].write_text(json.dumps({'summary':execution,'events':executor.records},ensure_ascii=False,
        indent=2,default=serialize)+'\n',encoding='utf8')
    summary={
        'mode':'REAL_RAW_DATA_DIAGNOSTIC_WITH_SOURCE_BOUNDED_FEATURE_EXTRACTION',
        'observed_bars':len(candles),'csv_sha256':fingerprint,'interval_seconds':interval_seconds,
        'raw_open_first':candles[0].opened_at,'raw_open_last':candles[-1].opened_at,
        'clock_basis':'RAW_BROKER_LABELS_NOT_VERIFIED_UTC','gap_boundaries':gaps,
        'actual_entry_evaluations':len(candles)*2*len(RULE_IDS),
        'decisions_by_side':{k:dict(v) for k,v in statuses.items()},
        'shape_results':dict(shapes),'new_geometric_candidates':dict(candidates),
        'missing_dependency_occurrences':dict(missing),'automatically_derived_dependency_occurrences':dict(derived),
        'eligible_entries':eligible,**execution,
        'fixed_lot_paper_execution_implemented':True,
        'bookkeeping_scope':'EXPLICIT_EXECUTION_EVENTS_ONLY_NOT_A_COMPLETE_STRATEGY_RETURN',
        'cash_and_lot_request_scope':'OWNER_MONTHLY_REQUEST_NOT_A_TEACHER_RULE',
        'strategy_pnl_usd':None,'strategy_backtest_complete':False,
        'full_raw_teacher_classifier_complete':False,'economic_context_events':len(tuple(contexts)),
        'unresolved_inputs':['HISTORICAL_SENTIMENT_CONTEXT','SOURCE_FAITHFUL_COMPLETE_STRUCTURE_AND_SETUP_CLASSIFICATION',
            'SOURCE_FAITHFUL_STOP_AND_TARGET_SELECTION','HISTORICAL_EXECUTABLE_QUOTES_AND_COSTS'],
        'candidate_means_trade_signal':False,'broker_connected':False,'orders_sent':0,
        'existing_engine_connected':False,'trace_private_local_only':True,
    }
    targets[0].write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=serialize)+'\n',encoding='utf8')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--interval-seconds',required=True,type=int)
    p.add_argument('--context',type=Path,help='Sourced causal context JSON; no synthetic default')
    p.add_argument('--execution',type=Path,help='Source-backed execution specs and event JSON; no inferred fills')
    p.add_argument('--initial-cash',default='1000.00');p.add_argument('--fixed-lots',default='0.03')
    args=p.parse_args();contexts=[]
    if args.context:
        doc=json.loads(args.context.read_text(encoding='utf8'),parse_float=Decimal)
        contexts=[Context(**x) for x in doc['contexts']]
    execution=None if args.execution is None else json.loads(args.execution.read_text(encoding='utf8'),parse_float=Decimal)
    result=run(args.csv,args.output_dir,args.interval_seconds,contexts,execution_document=execution,
        initial_cash=args.initial_cash,fixed_lots=args.fixed_lots)
    print(json.dumps({'bars':result['observed_bars'],'evaluations':result['actual_entry_evaluations'],
        'eligible':len(result['eligible_entries']),'full_backtest':False,'orders_sent':0}))

if __name__=='__main__':main()
