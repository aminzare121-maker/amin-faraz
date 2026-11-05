from pathlib import Path
import json,hashlib,unittest,io
from readiness import run_fixture
root=Path.cwd();lock=json.loads((root/'protocol-lock.json').read_text());assert hashlib.sha256((root/'AI_EVALUATION_PROTOCOL_FA.md').read_bytes()).hexdigest()==lock['protocol_sha256']
buf=io.StringIO();result=unittest.TextTestRunner(stream=buf,verbosity=2).run(unittest.defaultTestLoader.discover('qa',pattern='test_budget.py'))
(root/'reports/A-tests.log').write_text(buf.getvalue(),encoding='utf8');payload=run_fixture();(root/'reports/A-fixture.json').write_text(json.dumps(payload,indent=2),encoding='utf8');print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'ai_net':payload['ai_one']['net_hypothetical_usd'],'unmatched_net':payload['unmatched_100']['net_hypothetical_usd'],'matched_nets':[x['metrics']['net_hypothetical_usd'] for x in payload['matched_controls']]}));raise SystemExit(not result.wasSuccessful())
