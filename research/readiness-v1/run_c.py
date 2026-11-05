from pathlib import Path
import io,json,unittest
from feed_contract import REQUIRED,future_gate,synthetic_receipt,dry_run
root=Path.cwd();b=io.StringIO();r=unittest.TextTestRunner(stream=b,verbosity=2).run(unittest.defaultTestLoader.discover('qa',pattern='test_feed.py'))
meta={k:{'status':'UNKNOWN','evidence_id':None} for k in REQUIRED};meta.update({'symbol':'XAUUSD.st','source_data_received':False,'raw_byte_hash':'UNKNOWN','real_data_permission':'UNKNOWN'})
(root/'feed-readiness-unknown.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
raw,receipt=synthetic_receipt([{'ts_ms':0,'bid':'100','ask':'100.3'},{'ts_ms':1,'bid':'101','ask':'101.3'}]);report={'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'future_gate':future_gate(meta),'synthetic_dry_run':dry_run(raw,receipt),'real_downloads':0,'real_rows_processed':0}
(root/'reports/C-tests.log').write_text(b.getvalue(),encoding='utf8');(root/'reports/C-results.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report));raise SystemExit(not r.wasSuccessful())
