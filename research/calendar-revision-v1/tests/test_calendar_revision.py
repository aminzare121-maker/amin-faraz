import copy, importlib.util, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate'))
from amin_mt5.calendar_intelligence import Ledger, infer, normalize, stamp, number, render_fa, digest
from amin_mt5.economic_source_guardians import assess
from amin_mt5.local_research import calendar_report
from amin_mt5.calendar_evaluation import freeze,review
import tempfile

NOW=stamp('2026-11-05T12:20:00Z')
RAW='fixture-raw-cpi-v1'; HASH=__import__('hashlib').sha256(RAW.encode()).hexdigest()
REG={'Fixture authority':{'host':'example.org','origin_id':'cpi-origin','rights':'ALLOWED','evidence_id':'FIXTURE-LICENCE',
     'verified_receipts':[HASH],'forecast_receipts':['forecast-v1'],'max_check_age_ms':3600000,'max_fact_age_ms':86400000}}
BASE={'id':'cpi','origin_id':'cpi-origin','metric':'inflation_surprise','title':'Synthetic CPI','publisher':'Fixture authority','source_url':'https://example.org/report',
      'event_at':'2026-11-05T12:00:00Z','published_at':'2026-11-05T12:01:00Z','observed_at':'2026-11-05T12:10:00Z','checked_at':'2026-11-05T12:10:00Z',
      'actual':'۳٫۲','forecast':'3.0','previous':'2.9','unit':'percent','period':'2026-10','forecast_asof':'2026-11-04T13:00:00Z',
      'forecast_evidence_id':'forecast-v1','raw_sha256':HASH,'revision':0}
def rule(id,target,conditions,then='UP',regime='ANY',lag=0,horizon='short'):
    return {'id':id,'target':target,'conditions':conditions,'then':then,'regime':regime,'lag_ms':lag,'horizon':horizon,
            'rationale_fa':'فرضیه آزمایشی؛ رابطه علّی اثبات نشده','evidence_id':'SYNTHETIC-RULE','version':'1',
            'invalidates_fa':'اصلاح یا تکذیب شاهد یا تغییر رژیم','risks_fa':'شوک سیاستی، نقدینگی و عوامل حذف‌شده'}
RULES=[rule('r1','rates',{'inflation_surprise':'UP'},regime='tightening'),
       rule('r2','dollar',{'rates':'UP'},horizon='medium'),rule('r3','gold',{'dollar':'UP'},then='DOWN',horizon='long')]
def ledger():
    l=Ledger();l.append(BASE,stamp(BASE['observed_at']));return l
def report(l=None,now=NOW,regime='tightening',rules=None,previous=None):
    return infer(l or ledger(),now,REG,RULES if rules is None else rules,regime,previous)

class RevisionTests(unittest.TestCase):
    def test_before_stale_fixed(self):
        r=assess('calendar',['a'],[{'id':'a','status':'available','received_ms':NOW-30*86400000}],[],NOW)[0]
        self.assertEqual(r['status'],'stale');self.assertEqual(r['reason'],'SOURCE_RECEIPT_STALE')
    def test_future_actual_blocked(self):
        r=normalize({**BASE,'event_at':'2026-12-05T12:00:00Z'},NOW,REG)
        self.assertEqual(r['status'],'UNKNOWN')
    def test_exact_numbers(self):
        self.assertEqual(normalize(BASE,NOW,REG)['numbers']['surprise'],'0.2')
    def test_zero_negative(self):
        self.assertEqual(number('۰'),0);self.assertEqual(number('−۲٫۰'),-2)
    def test_nan(self):
        self.assertEqual(normalize({**BASE,'actual':'NaN'},NOW,REG)['status'],'UNKNOWN')
    def test_missing_not_zero(self):
        self.assertIsNone(normalize({**BASE,'actual':None},NOW,REG)['numbers']['actual'])
    def test_future_forecast(self):
        self.assertEqual(normalize({**BASE,'forecast_asof':BASE['event_at']},NOW,REG)['status'],'UNKNOWN')
    def test_caller_boolean_not_proof(self):
        self.assertEqual(normalize({**BASE,'verified_primary':True,'raw_sha256':'a'*64},NOW,REG)['status'],'UNKNOWN')
    def test_source_mismatch(self):
        self.assertEqual(normalize({**BASE,'source_url':'https://fake.example/report'},NOW,REG)['status'],'UNKNOWN')
    def test_stale_fact_cannot_refresh(self):
        r=normalize({**BASE,'checked_at':'2026-11-07T12:10:00Z'},NOW+2*86400000,REG)
        self.assertEqual(r['status'],'STALE');self.assertIn('STALE_FACT',r['reasons'])
    def test_duplicate_idempotent(self):
        l=ledger();a=report(l);self.assertFalse(l.append(BASE,NOW));self.assertEqual(a,report(l))
    def test_syndication_not_independent(self):
        l=ledger();l.append({**BASE,'id':'copy'},NOW)
        r=report(l);self.assertEqual(len(r['scenarios'][0]['root_evidence']),1)
    def test_conflicting_republication_blocks(self):
        l=ledger();l.append({**BASE,'id':'copy','actual':'2.8'},NOW)
        r=report(l);self.assertEqual(r['nodes']['inflation_surprise'],'CONFLICT');self.assertNotIn('gold',r['nodes'])
    def test_revision_recomputes(self):
        l=ledger();before=report(l);l.append({**BASE,'revision':1,'actual':'2.8'},NOW)
        after=report(l,previous=before);self.assertNotIn('gold',after['nodes']);self.assertTrue(after['changes'])
    def test_retract_removes_chain(self):
        l=ledger();before=report(l);l.append({**BASE,'revision':1},NOW,'RETRACT')
        r=report(l,previous=before);self.assertEqual(r['nodes'],{});self.assertTrue(r['changes'])
    def test_retraction_persists_restart(self):
        l=ledger();l.append({**BASE,'revision':1},NOW,'RETRACT');self.assertEqual(report(Ledger(l.export()))['nodes'],{})
    def test_asof_no_future_revision(self):
        l=ledger();l.append({**BASE,'revision':1,'actual':'2.8'},NOW+1000)
        self.assertEqual(report(l)['nodes']['gold'],'DOWN')
    def test_old_revision_rejected(self):
        l=ledger()
        with self.assertRaises(ValueError):l.append({**BASE,'actual':'2.8'},NOW)
    def test_tamper(self):
        values=ledger().export();values[0]['record']['actual']='100'
        with self.assertRaises(ValueError):Ledger(values)
    def test_restart_same(self):self.assertEqual(report(),report(Ledger(ledger().export())))
    def test_multi_horizon_chain(self):
        r=report();self.assertEqual(r['nodes']['gold'],'DOWN');self.assertEqual({s['horizon'] for s in r['scenarios']},{'short','medium','long'})
    def test_regime_changes_result(self):
        self.assertNotIn('gold',report(regime='UNKNOWN')['nodes'])
    def test_lag(self):
        rules=copy.deepcopy(RULES);rules[0]['lag_ms']=3600000
        self.assertNotIn('rates',report(rules=rules)['nodes'])
    def test_cumulative_lags(self):
        rules=copy.deepcopy(RULES);rules[0]['lag_ms']=400000;rules[1]['lag_ms']=400000
        r=report(rules=rules);self.assertIn('rates',r['nodes']);self.assertNotIn('dollar',r['nodes'])
    def test_condition_conjunction(self):
        rules=[rule('r','gold',{'inflation_surprise':'UP','iran_fx':'UP'})]
        self.assertNotIn('gold',report(rules=rules)['nodes'])
    def test_opposed_rules_block_descendants(self):
        rules=[RULES[0],rule('opposite','rates',{'inflation_surprise':'UP'},then='DOWN'),*RULES[1:]]
        r=report(rules=rules);self.assertEqual(r['nodes']['rates'],'CONFLICT');self.assertNotIn('gold',r['nodes'])
    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):report(rules=[rule('a','a',{'b':'UP'}),rule('b','b',{'a':'UP'})])
    def test_no_probability(self):self.assertIsNone(report()['probability'])
    def test_farsi_sections(self):
        text=render_fa(report());self.assertTrue(all(s in text for s in ('وضعیت فعلی','تغییرات جدید','آینده‌پژوهی','ارزیابی عملکرد','https://example.org/report')))
    def test_old_report_integration(self):
        r=calendar_report({'sources':[]},NOW,calendar_intelligence=report())
        self.assertIn('شناسه تحلیل',r['answer']);self.assertFalse(r['can_execute'])
        self.assertEqual(r['decision_signal']['short_term']['direction'],'neutral')
    def test_integration_stale_rejected(self):
        with self.assertRaises(ValueError):calendar_report({'sources':[]},NOW+1,calendar_intelligence=report())
    def test_dst_offsets(self):
        self.assertEqual(stamp('2026-11-01T01:30:00-05:00')-stamp('2026-11-01T01:30:00-04:00'),3600000)
    def test_tehran_utc(self):self.assertEqual(stamp('2026-11-05T15:50:00+03:30'),NOW)
    def test_naive_rejected(self):
        with self.assertRaises(ValueError):stamp('2026-11-05T12:20:00')
    def test_same_receipt_expiry_changes_inference(self):
        before=report();after=report(now=NOW+86400000,previous=before)
        self.assertNotIn('gold',after['nodes']);self.assertTrue(after['changes'])
    def test_disk_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=pathlib.Path(tmp)/'journal.json';l=ledger();l.save(path)
            self.assertEqual(report(l),report(Ledger.load(path)))
    def test_frozen_outcome_review(self):
        f=freeze(report(),'gold','long',NOW+1000)
        r=review(f,{'target':'gold','at_ms':NOW+1000,'observed_ms':NOW+1001,'direction':'UP','evidence_id':'FIXTURE-OUTCOME'},NOW+2000,'INFERENCE')
        self.assertFalse(r['match']);self.assertFalse(r['automatic_model_change'])
    def test_early_outcome(self):
        with self.assertRaises(ValueError):review(freeze(report(),'gold','long',NOW+1000),{},NOW)
    def test_frozen_edit_rejected(self):
        f=freeze(report(),'gold','long',NOW+1000);f['direction']='UP'
        with self.assertRaises(ValueError):review(f,{},NOW+2000)
    def test_horizon_mismatch(self):
        with self.assertRaises(ValueError):freeze(report(),'gold','short',NOW+1000)

if __name__=='__main__': unittest.main(verbosity=2)
