import hashlib, importlib.util, json, pathlib, sys, unittest, io
ROOT=pathlib.Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
guardian=module('legacy_guardian',ROOT/'baseline/amin_mt5/economic_source_guardians.py')
gate=module('evidence_gate',ROOT/'pr26/evidence_gate.py')
hyp=module('hypothesis_engine',ROOT/'pr26/hypothesis_engine.py')
now=1793880000000
base={'id':'cpi','title':'Synthetic CPI','publisher':'Fixture authority','source_url':'https://example.org/report',
      'event_at':'2026-11-05T12:00:00Z','observed_at':'2026-11-05T12:10:00Z','actual':'3.2','forecast':'3.0',
      'previous':'2.9','unit':'percent','period':'2026-10','forecast_asof':'2026-11-04T13:00:00Z','verified_primary':True}
edge=[{'source':'cpi','target':'rates','sign':1,'weight':.6,'evidence_id':'FIXTURE','rationale':'synthetic only'}]
item=[{'id':'cpi','delta':1,'confidence':.5,'verified':True}]
first=hyp.update_hypotheses({},item,edge)
second=hyp.update_hypotheses(first['pressure_by_target'],item,edge)
out={'scope':'ACTUAL_EXECUTION_OF_ORIGINAL_CODE_ON_SYNTHETIC_INPUT_NOT_LIVE_UI',
     'cases':[
      {'id':'old-receipt','now_ms':now,'receipt_ms':now-30*86400000,'expected':'STALE',
       'actual':guardian.assess('calendar',['a'],[{'id':'a','status':'available','received_ms':now-30*86400000}],[],now)[0]},
      {'id':'future-release','expected':'NOT_VERIFIED_CURRENT','actual':gate.assess({**base,'event_at':'2026-12-05T12:00:00Z'},'2026-11-05T12:20:00Z')},
      {'id':'duplicate-replay','expected':first,'actual':second}],
     'snapshot_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'baseline').rglob('*') if p.is_file()}}
stream=io.StringIO(); suite=unittest.defaultTestLoader.discover(str(ROOT/'pr26')); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
out['pr26_tests']={'count':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
(ROOT/'before.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'before-tests.txt').write_text(stream.getvalue(),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
