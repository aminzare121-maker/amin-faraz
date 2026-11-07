import hashlib,io,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from test_calendar_revision import report,ledger,BASE,NOW,REG,RULES
from amin_mt5.calendar_intelligence import normalize,render_fa
from amin_mt5.economic_source_guardians import assess
from amin_mt5.local_research import calendar_report
stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
l=ledger();initial=report(l);l.append({**BASE,'revision':1,'actual':'2.8'},NOW);revision=report(l,previous=initial)
l.append({**BASE,'revision':2},NOW,'RETRACT');retracted=report(l,previous=revision)
data={'scope':'SYNTHETIC_OFFLINE_NOT_FINANCIAL_VALIDATION','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
      'initial':initial,'revised':revision,'retracted':retracted,
      'before_cases_fixed':{'stale_receipt':assess('calendar',['a'],[{'id':'a','status':'available','received_ms':NOW-30*86400000}],[],NOW)[0]['status'],
                           'future_event':normalize({**BASE,'event_at':'2026-12-05T12:00:00Z'},NOW,REG)['status'],
                           'duplicate_replay_same':report(ledger())==report(ledger())},
      'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'candidate').rglob('*') if p.is_file()}}
(ROOT/'test-results.txt').write_text(stream.getvalue(),encoding='utf-8')
(ROOT/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'preview-report-fa.txt').write_text(render_fa(initial)+'\n\nپس از اصلاح:\n'+render_fa(revision)+'\n\nپس از تکذیب:\n'+render_fa(retracted),encoding='utf-8')
(ROOT/'preview-state.json').write_text(json.dumps({'last_report':calendar_report({'sources':[]},NOW,calendar_intelligence=initial)},ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:data[k] for k in ('tests','failures','errors','skips','before_cases_fixed')},ensure_ascii=False))
raise SystemExit(not result.wasSuccessful())
