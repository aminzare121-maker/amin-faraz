"""Run changed controls and save an actual cached integration experiment (synthetic)."""
import io,json,unittest,hashlib
from pathlib import Path
from registry import Registry,digest
from test_real_stage import fixture,COSTS,PROTOCOL
from engine_bridge import execute,engine_fingerprint
root=Path(__file__).resolve().parent
stream=io.StringIO();suite=unittest.TestSuite()
for module in ('test_controls','test_real_stage'):suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(root/'stage2-test-results.txt').write_text(stream.getvalue(),encoding='utf-8')
if not result.wasSuccessful():raise SystemExit(stream.getvalue())
bank=Registry(root/'local-research.sqlite');bars=fixture()
bank.artifact('synthetic-engine-integration-320-v1',digest(bars),{'synthetic':True,'not_market_data':True},True)
run=execute(bank,bars,'synthetic-engine-integration-320-v1',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
cached=execute(bank,bars,'synthetic-engine-integration-320-v1',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
assert cached['action']=='REUSE' and cached['result']==run['result']
(root/'synthetic-engine-integration.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
out={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
    'engine_sha256':engine_fingerprint(),'integration_first_action':run['action'],'second_action':cached['action'],
    'integration_scope':'SYNTHETIC_DIAGNOSTIC','real_market_strategy_runs':0,
    'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))}}
(root/'stage2-results.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
