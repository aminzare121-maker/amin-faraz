"""Run only the changed arithmetic; preserve Stage7 evidence verbatim."""
import json
from registry import Registry,digest
from test_selector import bars,controlled_run,CONTEXTS,PROTOCOL
from matched_controls import SPEC
from stage8_audit import ROOT,analyze

bank=Registry(ROOT/'selector-research.sqlite');data=bars()
bank.artifact('fixture',digest(data),{},True)
run=controlled_run(bank,data,CONTEXTS,dict(PROTOCOL,matched_controls=SPEC))
summary=analyze(run['result'])
summary.update(run=run['id'],action=run['action'],ranking=run['result']['ranking'],
               synthetic=True,profitability_verified=False,comparison_criteria_changed=False)
(ROOT/'stage8-corrected-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('groups','examples')}))
