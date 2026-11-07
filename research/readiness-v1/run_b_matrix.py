from pathlib import Path
import io,json,unittest
from risk_matrix import matrix
b=io.StringIO();r=unittest.TextTestRunner(stream=b,verbosity=2).run(unittest.defaultTestLoader.discover('qa',pattern='test_risk_matrix.py'));Path('reports/B-matrix-tests.log').write_text(b.getvalue(),encoding='utf8');Path('reports/B-matrix.json').write_text(json.dumps(matrix(),indent=2),encoding='utf8');print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'matrix':matrix()}));raise SystemExit(not r.wasSuccessful())
