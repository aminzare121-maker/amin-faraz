import copy,json,tempfile,unittest
from pathlib import Path
from registry import Registry,identity
from comparison import compare,news_at,net_cost

SHA='a'*64
def spec():
    return dict(code_sha256=SHA,datasets={'synthetic-v1':SHA},settings={'window':3},costs={'mode':'synthetic','spread':1},protocol_sha256=SHA,environment={'python':'test'},metrics_version='v1',split={'train':[0,99],'validation':[100,199],'holdout':[200,299]},seed=7)
def bar(t=0,p=10):return dict(time=t,open=p,high=p+2,low=p-1,close=p+1)
def meta():return dict(canonical='XAUUSD',price_side='BID',timezone='UTC',bar_seconds=900,unit='USD/oz',session_evidence='synthetic',mapping_evidence='synthetic')

class BankTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'research.sqlite';self.bank=Registry(self.path)
        self.bank.artifact('synthetic-v1',SHA,{'synthetic':True},valid=True)
    def tearDown(self):self.temp.cleanup()
    def test_negative_result_reused_after_restart(self):
        s=spec();run=self.bank.start(s);self.bank.finish_run(run['id'],{'net':-10,'synthetic':True},True)
        reused=Registry(self.path).start(s);self.assertEqual(reused['action'],'REUSE');self.assertEqual(reused['result']['net'],-10)
    def test_every_dependency_changes_identity(self):
        s=spec();base=identity(s)
        for key,value in dict(code_sha256='b'*64,datasets={'synthetic-v2':'b'*64},settings={'window':4},costs={'spread':2},protocol_sha256='b'*64,environment={'python':'new'},metrics_version='v2',split={'holdout':[300,400]},seed=8).items():
            changed=copy.deepcopy(s);changed[key]=value
            with self.subTest(key=key):self.assertNotEqual(base,identity(changed))
    def test_unknown_dependency_rejected(self):
        s=spec();s['untracked']='x'
        with self.assertRaisesRegex(ValueError,'SCHEMA'):identity(s)
    def test_unvalidated_real_data_blocked(self):
        self.bank.artifact('demo-unvalidated','b'*64,{'source':'DEMO'},False)
        s=spec();s['datasets']={'demo-unvalidated':'b'*64}
        with self.assertRaisesRegex(ValueError,'DATA_NOT_VALIDATED'):self.bank.start(s)
    def test_immutable_artifact(self):
        with self.assertRaisesRegex(ValueError,'IMMUTABLE'):self.bank.artifact('synthetic-v1','b'*64,{},True)
    def test_running_not_reexecuted(self):
        self.bank.start(spec());self.assertEqual(self.bank.start(spec())['action'],'BLOCKED_RUNNING')
    def test_failed_not_reused(self):
        run=self.bank.start(spec());self.bank.finish_run(run['id'],{'error':'synthetic'},False)
        self.assertEqual(self.bank.start(spec())['action'],'BLOCKED_FAILED')
    def test_invalidation_retains_reason_and_blocks_finish(self):
        run=self.bank.start(spec());self.bank.invalidate('synthetic-v1','bad timestamp evidence')
        with self.assertRaises(ValueError):self.bank.finish_run(run['id'],{},True)
        with self.bank.connect() as db:self.assertEqual(db.execute('SELECT reason FROM invalidations').fetchone()[0],'bad timestamp evidence')
    def test_result_tamper(self):
        run=self.bank.start(spec());self.bank.finish_run(run['id'],{'net':-1},True)
        with self.bank.connect() as db:db.execute("UPDATE reusable_runs SET result=?",('{"net":99}',))
        with self.assertRaisesRegex(ValueError,'TAMPER'):self.bank.start(spec())
    def test_double_finish_rejected(self):
        run=self.bank.start(spec());self.bank.finish_run(run['id'],{},True)
        with self.assertRaises(ValueError):self.bank.finish_run(run['id'],{},True)
    def test_indicator_invalid_hash(self):
        with self.assertRaises(ValueError):self.bank.indicator('SMA','1','z'*64,'TESTED',{'synthetic':True})

class ComparisonTests(unittest.TestCase):
    def test_exact_overlap_and_differences(self):
        result=compare([bar(0),bar(900),bar(1800)],[bar(900,12),bar(2700,12)],meta(),meta())
        self.assertEqual(result['matched'],1);self.assertEqual(result['left_only_in_overlap'],1)
        self.assertEqual(result['price_differences']['close']['signed_mean'],'-2')
        self.assertEqual(result['financial_comparison'],'NOT_RUN')
    def test_side_mismatch(self):
        m=meta();m['price_side']='ASK'
        with self.assertRaises(ValueError):compare([bar()],[bar()],meta(),m)
    def test_unknown_session(self):
        m=meta();m['session_evidence']='UNKNOWN'
        with self.assertRaises(ValueError):compare([bar()],[bar()],meta(),m)
    def test_bad_rows(self):
        for rows in ([bar(),bar()], [bar(1)], [bar(900),bar(0)], [dict(bar(),close=100)], [dict(bar(),open='NaN')]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):compare(rows,[bar()],meta(),meta())
    def test_no_overlap(self):self.assertEqual(compare([],[],meta(),meta())['status'],'NO_OVERLAP')
    def test_unknown_cost_not_zero(self):self.assertIsNone(net_cost(10,1,0,None,1)['net'])
    def test_signed_swap(self):
        self.assertEqual(net_cost(10,1,0,-2,1)['net'],'6');self.assertEqual(net_cost(10,1,0,2,1)['net'],'10')
    def test_bad_cost(self):
        for cost in (-1,'NaN','Infinity'):
            with self.assertRaises(ValueError):net_cost(10,cost,0,0,0)
    def test_future_news_never_available(self):
        base=dict(kind='FACT',status='VERIFIED',receipt_sha256=SHA,published_ms=10,available_ms=20)
        self.assertEqual(news_at([base],19),[]);self.assertEqual(len(news_at([base],20)),1)
        for changed in (dict(base,kind='FORECAST'),dict(base,receipt_sha256='fake'),dict(base,retracted=True),dict(base,published_ms=21)):
            self.assertEqual(news_at([changed],100),[])

if __name__=='__main__':unittest.main(verbosity=2)
