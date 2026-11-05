"""Reproducible offline tests; writes synthetic results only."""
import hashlib, io, json, pathlib, unittest
from test_adapter import run

root=pathlib.Path(__file__).resolve().parent
stream=io.StringIO()
suite=unittest.defaultTestLoader.discover(str(root),pattern='test_adapter.py')
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
report={'scope':'SYNTHETIC_ONLY','tests':result.testsRun,'failures':len(result.failures),
        'errors':len(result.errors),'skips':len(result.skipped),'example':run(),
        'not_executed':['REAL_PRICE_DOWNLOAD','TRAIN','BACKTEST','MT5','AWS','TRADE'],
        'source_sha256':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(root.rglob('*.py'))}}
(root/'test-results.txt').write_text(stream.getvalue(),encoding='utf-8')
(root/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(stream.getvalue()); print(json.dumps({k:v for k,v in report.items() if k!='example'},indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
