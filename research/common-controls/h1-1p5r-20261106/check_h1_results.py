"""Independent accounting checks of the saved private paired trace."""
import argparse,json,hashlib
from decimal import Decimal as D
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--private-trace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();cells=json.loads(a.private_trace.read_text());pairs=closed=unknown=0
for c in cells:
    assert len(c['rows'][0])==len(c['rows'][1])==c['counters'].get('accepted_pairs',0)
    for x,y in zip(*c['rows']):
        pairs+=1
        for f in ('side','entry_time','entry','initial_stop','lots'):assert x[f]==y[f]
        assert abs(D(y['target'])-D(y['entry']))==D('1.5')*abs(D(y['entry'])-D(y['initial_stop']))
        for r in (x,y):
            assert D(r['sizing']['risk'])<=D(r['sizing']['budget'])
            assert D(r['lots'])%D('.01')==0 and D(r['lots'])>=D('.01')
            if r['net_scenario_usd'] is None:
                unknown+=1;assert r['exit'] is None and r['gross_scenario_usd'] is None
            else:
                closed+=1;direction=1 if r['side']=='buy' else -1
                gross=D(direction)*(D(r['exit'])-D(r['entry']))*100*D(r['lots'])
                fee=(D(0) if c['cost']=='base' else D(10))*D(r['lots'])
                assert gross==D(r['gross_scenario_usd']) and gross-fee==D(r['net_scenario_usd'])
    for arm in (0,1):
        rows=c['rows'][arm]
        for prev,nxt in zip(rows,rows[1:]):
            assert prev['net_scenario_usd'] is not None and nxt['entry_time']>=prev['exit_time']
for candidate in {c['candidate'] for c in cells}:
    for cost in ('base','envelope'):
        series=[c for c in cells if c['candidate']==candidate and c['cost']==cost and c['cohort']=='continuous_known_prefix']
        assert series[-1]['unknown'] and not any(c['unknown'] for c in series[:-1])
result=dict(passed=True,checked_pairs_including_prefix_subcohort=pairs,closed_cash_identities=closed,
    unknown_no_invented_exit=unknown,shared_entry_stop_volume=True,exact_1p5R=True,risk_budget_respected=True,
    no_overlapping_entries=True,continuous_stops_at_first_unknown=True,
    private_trace_sha256=hashlib.sha256(a.private_trace.read_bytes()).hexdigest())
a.out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
