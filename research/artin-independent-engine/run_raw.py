"""Offline raw CSV runner; private trace stays local, no broker or network."""
import argparse
from collections import Counter
from dataclasses import asdict,is_dataclass
from decimal import Decimal,getcontext
from contextlib import contextmanager
from hashlib import sha256
import gzip,json,os,sys,tempfile
from pathlib import Path
from entry_engine import RULE_IDS,Decision
from context_inputs import Context
from raw_pipeline import RawPipeline,read_csv
from monthly_execution import MonthlyExecutor
from direction_plan import DirectionPlan

def serialize(v):
    if isinstance(v,Decimal):return str(v)
    if is_dataclass(v):return asdict(v)
    raise TypeError('unsupported JSON value')

def input_digest(value):
    def typed(v):
        if isinstance(v,dict):return ['dict',[[k,typed(x)] for k,x in sorted(v.items())]]
        if isinstance(v,(list,tuple)):return ['sequence',[typed(x) for x in v]]
        if type(v) in (str,int,bool,Decimal) or v is None:return [type(v).__name__,str(v)]
        raise ValueError('unsupported execution input type')
    return sha256(json.dumps(typed(value),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

@contextmanager
def atomic_target(target,compressed=False):
    target=Path(target)
    fd,name=tempfile.mkstemp(prefix='.artin-',suffix='.tmp',dir=target.parent);os.close(fd)
    try:
        opener=gzip.open if compressed else open
        with opener(name,'wt',encoding='utf8') as f:yield f
        os.replace(name,target)
    finally:
        if Path(name).exists():Path(name).unlink()

def assert_outputs_separate(targets,inputs):
    for target in targets:
        for source in inputs:
            if target.resolve()==source.resolve() or target.exists() and source.exists() and target.samefile(source):
                raise ValueError('output aliases declared input')

def run(csv_path,output_dir,interval_seconds,contexts=(),plan_id='ARTIN_RAW_DIAGNOSTIC',
        execution_document=None,initial_cash='1000.00',fixed_lots='0.03',protected_inputs=(),input_receipts=None,direction_plan=None):
    contexts=tuple(contexts)
    candles,fingerprint=read_csv(csv_path,interval_seconds)
    if not candles:raise ValueError('empty monthly data')
    output_dir=Path(output_dir)
    # All supplied input files, including hardlink/symlink aliases, are protected.
    targets=[output_dir/n for n in ('SUMMARY.json','PRIVATE_raw_decisions.jsonl.gz','PRIVATE_execution.json')]
    assert_outputs_separate(targets,[Path(csv_path)]+[Path(x) for x in protected_inputs])
    output_dir.mkdir(parents=True,exist_ok=True)
    pipeline=RawPipeline(plan_id,RULE_IDS,interval_seconds,fingerprint,contexts,direction_plan)
    executor=MonthlyExecutor(pipeline.engine,initial_cash,fixed_lots,execution_document)
    code_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in Path(__file__).resolve().parent.glob('*.py')
                 if not p.name.startswith('test_')}
    dc=getcontext()
    provenance={'python_version':sys.version,'decimal_context':{k:str(getattr(dc,k)) for k in ('prec','rounding','Emin','Emax','capitals','clamp')},
        'module_sha256':code_hashes,'execution_document_typed_sha256':input_digest(execution_document),
        'context_typed_fingerprint':pipeline.context_fingerprint,'declared_input_receipts':input_receipts or {}}
    provenance['direction_permission_plan']=None if direction_plan is None else direction_plan.serialize()
    statuses={side:Counter() for side in ('BUY','SELL')};missing=Counter();shapes=Counter();candidates=Counter()
    derived=Counter();gaps=0;eligible=[]
    with atomic_target(targets[1],compressed=True) as f:
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
                executor.accept(decision,pipeline.latest_observation(d['side'],d['rule_id']))
            executor.advance(bar.closed_at,strict=True)
            f.write(json.dumps(result,ensure_ascii=False,default=serialize,separators=(',',':'))+'\n')
    execution=executor.summary()
    with atomic_target(targets[2]) as f:
        f.write(json.dumps({'summary':execution,'events':executor.records,'provenance':provenance},ensure_ascii=False,
            indent=2,default=serialize)+'\n')
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
        'provenance':provenance,
    }
    with atomic_target(targets[0]) as f:f.write(json.dumps(summary,ensure_ascii=False,indent=2,default=serialize)+'\n')
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--interval-seconds',required=True,type=int)
    p.add_argument('--context',type=Path,help='Sourced causal context JSON; no synthetic default')
    p.add_argument('--execution',type=Path,help='Source-backed execution specs and event JSON; no inferred fills')
    p.add_argument('--initial-cash',default='1000.00');p.add_argument('--fixed-lots',default='0.03')
    p.add_argument('--direction-policy',choices=('SOURCE_DATA_ONLY','S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION'),default='SOURCE_DATA_ONLY')
    p.add_argument('--symbol',help='Exact fixed symbol, required for explicitly selected S09 assumption')
    args=p.parse_args();contexts=[];receipts={}
    def load_input(path,key):
        data=path.read_bytes();receipts[key]=sha256(data).hexdigest()
        return json.loads(data.decode('utf-8-sig'),parse_float=Decimal)
    if args.context:
        doc=load_input(args.context,'context_bytes_sha256')
        contexts=[Context(**x) for x in doc['contexts']]
    execution=None if args.execution is None else load_input(args.execution,'execution_bytes_sha256')
    if args.direction_policy!='SOURCE_DATA_ONLY' and not args.symbol:p.error('explicit exact --symbol is required for S09 plan')
    direction=None if args.direction_policy=='SOURCE_DATA_ONLY' else DirectionPlan('OWNER_DECLARED_FIXED_SYMBOL_RESEARCH',args.symbol,args.direction_policy,True)
    result=run(args.csv,args.output_dir,args.interval_seconds,contexts,execution_document=execution,
        initial_cash=args.initial_cash,fixed_lots=args.fixed_lots,
        protected_inputs=[x for x in (args.context,args.execution) if x],input_receipts=receipts,direction_plan=direction)
    print(json.dumps({'bars':result['observed_bars'],'evaluations':result['actual_entry_evaluations'],
        'eligible':len(result['eligible_entries']),'full_backtest':False,'orders_sent':0}))

if __name__=='__main__':main()
