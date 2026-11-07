"""Reproducible synthetic diagnostics, persisted in the existing ResearchLedger."""
import copy,hashlib,io,json,unittest
from pathlib import Path
from registry import Registry,digest
from test_selector import bars,controlled_run,CONTEXTS,PROTOCOL
from engine_bridge import evaluate_strategies
from test_real_stage import fixture

ROOT=Path(__file__).resolve().parent
def dump(name,data):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def compact(report):
    result=copy.deepcopy(report)
    def trim(x):
        if isinstance(x,dict):
            for k,v in list(x.items()):
                if k=='rows' and v and isinstance(v,list) and isinstance(v[0],dict) and 'trace' in v[0]:
                    x['all_rows_sha256']=digest(v);x['retained_trace_examples']=min(2,len(v));x[k]=v[:2]
                else:trim(v)
        elif isinstance(x,list):
            for v in x:trim(v)
    trim(result);return result
def main():
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(x) for x in ('test_selector','test_stage3','test_real_stage.EngineBridgeTests'))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (ROOT/'stage4-test-results.txt').write_text(stream.getvalue(),encoding='utf8')
    if not result.wasSuccessful():raise SystemExit(stream.getvalue())
    bank=Registry(ROOT/'local-research.sqlite');data=bars()
    # Immutable fixture ID in a dedicated local ledger avoids colliding with prior fixture IDs.
    bank=Registry(ROOT/'selector-research.sqlite');bank.artifact('fixture',digest(data),{'synthetic':True,'purpose':'controlled-selector'},True)
    first=controlled_run(bank,data);again=controlled_run(bank,data)
    unknown=copy.deepcopy(CONTEXTS)
    for c in unknown.values():c.update(swap=None,assumed_swap=0)
    unknown_result=controlled_run(bank,data,unknown)
    missing=copy.deepcopy(CONTEXTS);missing['base']['assumed_spread']=None
    try:controlled_run(bank,data,missing)
    except ValueError:pass
    failed=controlled_run(bank,data,missing)
    actual=[dict(b,available=b['observed_at'],time_basis='synthetic-UTC') for b in fixture()]
    bank.artifact('synthetic-320-actual-strategies',digest(actual),{'synthetic':True},True)
    contexts=copy.deepcopy(CONTEXTS)
    for c in contexts.values():c['exit_policy']='adaptive_existing'
    actual_run=evaluate_strategies(bank,actual,'synthetic-320-actual-strategies',contexts,PROTOCOL)
    dump('selector-controlled-trace.json',compact(first['result']))
    dump('selector-existing-strategies.json',compact(actual_run['result']))
    summary=dict(tests=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),failed=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        controlled_run_id=first['id'],controlled_action=first['action'],repeated_action=again['action'],ranking=first['result']['ranking'],
        unknown_swap_nominee=unknown_result['result']['scenario_nominee'],unknown_swap_run_id=unknown_result['id'],missing_spread_state=failed['action'],
        actual_strategy_run_id=actual_run['id'],actual_candidate_count=len(actual_run['result']['candidates']),
        actual_training_trade_rows=sum(len(s['rows']) for c in actual_run['result']['candidates'] for s in c['train'].values()),
        official_historical_evidence_added=0,gaps_unknown=260,year_validation='BLOCKED',real_market_strategy_runs=0,
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'engine_bridge.py',ROOT/'execution_scenarios.py',ROOT/'scenario_segment.py',ROOT/'research_engine/experiments.py',ROOT/'test_selector.py',ROOT/'stage4_qa.py']})
    dump('stage4-results.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
