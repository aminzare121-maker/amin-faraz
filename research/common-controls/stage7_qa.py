"""Persist new controlled-fixture execution in the existing research bank."""
import copy,json
from pathlib import Path
from registry import Registry,digest
from test_selector import bars,controlled_run,CONTEXTS,PROTOCOL
from matched_controls import SPEC

bank=Registry(Path(__file__).with_name('selector-research.sqlite'))
data=bars();bank.artifact('fixture',digest(data),{'synthetic':True},True)
protocol=dict(PROTOCOL,matched_controls=SPEC)
result=controlled_run(bank,data,CONTEXTS,protocol)
report=result['result']
rows=[r for c in report['candidates'] for s in c['validation'].values() for r in s['rows']]
controls=[c for r in rows for c in r['matched_controls']]
bad=copy.deepcopy(CONTEXTS);bad['base']['assumed_spread']=None
try:failed=controlled_run(bank,data,bad,protocol)
except ValueError as exc:failed={'action':'FAILED_RECORDED','reason':str(exc)}
summary=dict(synthetic=True,run_id=result['id'],action=result['action'],candidates=len(report['candidates']),
             validation_scenario_rows=len(rows),control_scenario_rows=len(controls),
             comparable=sum(c['status']=='PAIRED_SCENARIO_ONLY' for c in controls),
             incomparable=sum(c['status']=='INCOMPARABLE' for c in controls),
             ranking=report['ranking'],failed_fixture=failed,
             market_profitability_verified=False,trade_allowed=False,
             note='Counts include repeated scenario/policy evaluations, not independent trades; no post-hoc filtering')
Path(__file__).with_name('stage7-controls-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
