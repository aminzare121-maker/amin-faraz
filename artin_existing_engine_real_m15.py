#!/usr/bin/env python3
"""Execute the existing 13-rule instructor engine on real M15 candle timestamps.

No guessed teacher facts, no synthetic orders. Research-only causal diagnostic.
"""
import csv,glob,importlib.util,json,sys
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent/'research/artin-independent-engine/entry_engine.py'
spec=importlib.util.spec_from_file_location('artin_source_engine',P)
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

def run(csvpath,out):
    engine=module.Engine('ARTIN_REAL_M15_SOURCE_ONLY',tuple(module.RULE_IDS))
    summary={r:Counter() for r in module.RULE_IDS}
    reasons={r:Counter() for r in module.RULE_IDS}
    first=None;last=None;count=0
    with open(csvpath,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            t=int(row.get('timestamp') or row.get('time'))
            if t>10**11:t//=1000
            if first is None:first=t
            if last is not None and (t<=last or t%900):raise ValueError('INVALID_BAR_TIME')
            last=t;count+=1
            for side in ('BUY','SELL'):
                observation=module.Observation(side,t,{})
                for rule in module.RULE_IDS:
                    d=engine.evaluate(rule,observation)
                    if d.order_created:raise AssertionError('NO_ORDER_ALLOWED')
                    summary[rule][d.status]+=1
                    reasons[rule][';'.join(d.reasons)]+=1
    result={'schema':'artin_existing_13_route_engine_real_m15_diagnostic_v1',
      'source':'Dukascopy public BID M15, not Eplanet',
      'actual_engine_path':str(P.relative_to(Path(__file__).resolve().parent)),
      'engine_fingerprint':engine.fingerprint,
      'candles':count,'evaluations':count*26,'first_bar':first,'last_bar':last,
      'routes':[{'id':r,'statuses':dict(summary[r]),'reasons':dict(reasons[r])} for r in module.RULE_IDS],
      'market_only_teacher_context':'NOT_AVAILABLE',
      'teacher_entry_confirmed':0,'trades':0,'pnl':None,
      'explanation':'This executes the actual existing engine, not a surrogate. Its teacher-only facts remain missing; do not bypass.'}
    with open(out,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'candles':count,'engine_evaluations':count*26,
                      'routes':len(module.RULE_IDS),'statuses':{r:dict(summary[r]) for r in module.RULE_IDS}},ensure_ascii=False))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
