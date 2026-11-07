"""Offline evidence only; never imports MT5 or performs network operations."""
import hashlib,io,json,platform,unittest
from pathlib import Path
from registry import Registry

root=Path(__file__).resolve().parent
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.discover(str(root),pattern='test_controls.py'))
(root/'test-results.txt').write_text(stream.getvalue(),encoding='utf-8')
qa_path=root.parent/'eplanet-history-revision'/'independent-qa-sanitized.json'
qa=json.loads(qa_path.read_text(encoding='utf-8'))
qa_sha=hashlib.sha256(qa_path.read_bytes()).hexdigest()
bank=Registry(root/'local-research.sqlite')
bank.artifact('eplanet-demo-year-20261105','57d0734217b44ccdacbac58bd68f47e7706f3d0be71ffc1c4d735a1325a12a07',{
    'source':'Eplanet DEMO','symbol':'XAUUSD.st','qa_sha256':qa_sha,
    'm15_rows':qa['m15_rows'],'tick_rows':qa['tick_rows'],
    'final_backtest_approved':False,'reasons':qa['reasons']},valid=False)
report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
    'python':platform.python_version(),'synthetic_tests_only':True,'financial_backtests_run':0,
    'actual_dataset_registered':True,'actual_dataset_valid_for_final_backtest':False,
    'm15_rows':qa['m15_rows'],'tick_rows':qa['tick_rows'],'qa_sha256':qa_sha,
    'source_sha256':{str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))}}
(root/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
