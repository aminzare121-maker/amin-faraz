import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from registry import Registry,digest
from engine_bridge import evaluate_strategies,existing_engine
existing_engine()
from amin_mt5.strategy import Candidate
from research_engine.experiments import rank

PROTOCOL=dict(scope='SYNTHETIC_DIAGNOSTIC',time_interpretation='SYNTHETIC_UTC',news=[],selection='validation-only-worst-case',seed=581)
CONTEXTS={k:dict(cost_basis='ASSUMPTION',exit_policy='fixed_sltp',assumed_spread=s,slippage=l,commission=40,swap=0,assumed_swap=None) for k,s,l in (('base',.2,.1),('stress',.3,.15))}

def bars():
    return [dict(time=i*900,open=100,high=102,low=99.5,close=101,final=True,observed_at=(i+1)*900,available=(i+1)*900,time_basis='synthetic-UTC',tick_volume=100) for i in range(320)]

def setup(history,asof,candidate):
    if not history:return None
    return dict(side='buy',signal_time=history[-1]['time'],learning_features=[0]*7,features={'range_atr_proxy':1,'trend':'up'},family=candidate.family)

def size(setup,*args,**kwargs):
    stop,tp={'breakout':('99','100.6'),'rejection':('99.8','101'),'retest':('99','101.5')}[setup['family']]
    return dict(volume='.01',stop_loss=stop,take_profit=tp)

def controlled_run(bank,data,contexts=CONTEXTS,protocol=PROTOCOL):
    # Only signal and sizing fixtures are replaced; runner/evaluator/cost/ranking/ledger are real.
    with patch('research_engine.experiments.candidates',return_value=[Candidate(f) for f in ('breakout','rejection','retest')]),patch('scenario_segment.plan',side_effect=setup),patch('scenario_segment.size_and_target',side_effect=size):
        return evaluate_strategies(bank,data,'fixture',contexts,dict(protocol,fixture_source_sha256=__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest()))

class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.bank=Registry(Path(self.tmp.name)/'bank.sqlite');self.data=bars()
        self.bank.artifact('fixture',digest(self.data),{'synthetic':True},True)
    def tearDown(self):self.tmp.cleanup()
    def run_fixture(self,contexts=None):return controlled_run(self.bank,self.data,contexts or CONTEXTS)['result']
    def test_end_to_end_three_methods(self):
        r=self.run_fixture();self.assertEqual(len(r['candidates']),3)
        rows={x['id']:x for x in r['ranking']['rows']}
        self.assertLess(rows['breakout-20-1.5-rules']['worst_case_net'],0)
        self.assertIn('UNKNOWN_COST_OR_PATH',rows['rejection-20-1.5-rules']['reasons'])
        self.assertEqual(r['scenario_nominee'],'retest-20-1.5-rules');self.assertIsNone(r['selected_candidate'])
        self.assertFalse(r['market_profitability_verified']);self.assertIsNotNone(r['out_of_sample'])
    def test_cache_exact(self):
        a=controlled_run(self.bank,self.data);b=controlled_run(self.bank,self.data)
        self.assertEqual(b['action'],'REUSE');self.assertEqual(a['result'],b['result'])
    def test_unknown_swap_blocks_even_with_assumed_profit(self):
        c=copy.deepcopy(CONTEXTS)
        for x in c.values():x.update(swap=None,assumed_swap=0)
        r=self.run_fixture(c);self.assertIsNone(r['scenario_nominee'])
        self.assertTrue(all('UNKNOWN_COST_OR_PATH' in x['reasons'] for x in r['ranking']['rows']))
    def test_missing_spread_failure_recorded(self):
        c=copy.deepcopy(CONTEXTS);c['base']['assumed_spread']=None
        with self.assertRaisesRegex(ValueError,'SPREAD_UNKNOWN'):self.run_fixture(c)
        self.assertEqual(controlled_run(self.bank,self.data,c)['action'],'BLOCKED_FAILED')
    def test_invalid_dataset_cannot_reuse(self):
        self.run_fixture();self.bank.invalidate('fixture','test evidence withdrawal')
        with self.assertRaisesRegex(ValueError,'DATA_NOT_VALIDATED'):self.run_fixture()
    def test_out_of_order_recorded_failed(self):
        self.data[2]['time']=0;self.bank=Registry(Path(self.tmp.name)/'bad.sqlite');self.bank.artifact('fixture',digest(self.data),{},True)
        with self.assertRaisesRegex(ValueError,'TIME_ORDER'):self.run_fixture()
    def test_same_bar_unknown_pnl_none(self):
        r=self.run_fixture();c=r['candidates'][1]
        self.assertLess(c['validation']['base:stop_first']['net_usd'],0)
        self.assertGreater(c['validation']['base:target_first']['net_usd'],0)
        self.assertIsNone(c['validation']['base:unknown']['net_usd'])
    def test_holdout_change_does_not_change_selection(self):
        a=self.run_fixture();other=copy.deepcopy(self.data)
        for b in other[248:]:b.update(high=100.1,low=98,close=99)
        bank=Registry(Path(self.tmp.name)/'other.sqlite');bank.artifact('fixture',digest(other),{},True)
        b=controlled_run(bank,other)['result']
        self.assertEqual(a['ranking'],b['ranking']);self.assertNotEqual(a['out_of_sample'],b['out_of_sample'])
    def test_different_assumptions_not_comparable(self):
        r=self.run_fixture();r['candidates'][0]['comparison_hash']='other'
        ranked=rank(r['candidates']);self.assertFalse(ranked['comparable']);self.assertIsNone(ranked['scenario_nominee'])
    def test_cost_hash_changes(self):
        a=controlled_run(self.bank,self.data);c=copy.deepcopy(CONTEXTS);c['stress']['slippage']=.2
        b=controlled_run(self.bank,self.data,c);self.assertNotEqual(a['id'],b['id'])
    def test_future_news_blocked(self):
        with self.assertRaisesRegex(ValueError,'NEWS_NOT_SUPPORTED'):controlled_run(self.bank,self.data,protocol=dict(PROTOCOL,news=[{'available_ms':999999999}]))
    def test_real_year_blocked(self):
        with self.assertRaisesRegex(ValueError,'REAL_YEAR_GATE'):controlled_run(self.bank,self.data,protocol=dict(PROTOCOL,scope='REAL_YEAR'))
    def test_no_signal_from_delayed_bar(self):
        data=copy.deepcopy(self.data)
        for b in data:b['observed_at']+=1800;b['available']=b['observed_at']
        bank=Registry(Path(self.tmp.name)/'late.sqlite');bank.artifact('fixture',digest(data),{},True)
        def check(history,asof,candidate):
            self.assertTrue(all(b['observed_at']<=asof for b in history));return None
        with patch('scenario_segment.plan',side_effect=check):r=evaluate_strategies(bank,data,'fixture',CONTEXTS,PROTOCOL)
        self.assertIsNone(r['result']['scenario_nominee'])
    def test_unmocked_existing_candidates(self):
        r=evaluate_strategies(self.bank,self.data,'fixture',CONTEXTS,PROTOCOL)['result']
        self.assertEqual(len(r['candidates']),6);self.assertIsNone(r['scenario_nominee'])
    def test_variable_quote_trace(self):
        c=copy.deepcopy(CONTEXTS)
        for ctx in c.values():
            ctx['quotes']={b['time']:dict(time=b['time'],bid=100,ask=100.05+(i%2)*.05,status='VERIFIED',receipt_id='synthetic') for i,b in enumerate(self.data)}
            ctx['receipt_ids']=['synthetic'];ctx['assumed_spread']=None
        r=self.run_fixture(c)
        trace=r['candidates'][2]['validation']['base:stop_first']['rows'][0]['trace']
        self.assertEqual(trace['entry_spread_basis'],'VERIFIED_QUOTE_AT_BAR_OPEN');self.assertEqual(trace['cost_basis'],'ASSUMPTION')
    def test_net_arithmetic_no_double_cost(self):
        r=self.run_fixture();row=r['candidates'][2]['validation']['base:stop_first']['rows'][0]
        self.assertAlmostEqual(row['net'],.7)
        self.assertEqual(row['trace']['entry'],'100.3');self.assertEqual(row['trace']['exit'],'101.4')
    def test_actual_unmocked_signals_and_adaptive_exit(self):
        from test_real_stage import fixture
        data=[dict(b,available=b['observed_at'],time_basis='synthetic-UTC') for b in fixture()]
        bank=Registry(Path(self.tmp.name)/'real-engine-synthetic.sqlite');bank.artifact('fixture',digest(data),{},True)
        contexts=copy.deepcopy(CONTEXTS)
        for c in contexts.values():c['exit_policy']='adaptive_existing'
        r=evaluate_strategies(bank,data,'fixture',contexts,PROTOCOL)['result']
        rows=[t for c in r['candidates'] for s in c['train'].values() for t in s['rows']]
        self.assertGreater(len(rows),0);self.assertTrue(all(t['order']['target'] is None for t in rows))
    def test_future_quote_not_verified(self):
        from execution_scenarios import spread_at
        with self.assertRaisesRegex(ValueError,'SPREAD_UNKNOWN'):
            spread_at(0,{0:dict(time=0,available=1,bid=100,ask=101,receipt_id='x',status='VERIFIED')},None,['x'])
    def test_gap_open_proves_stop_before_range_target(self):
        from execution_scenarios import replay
        from test_stage3 import bar,ORDER,COST
        out=replay([bar(0,h=100.5,l=99.5),bar(900,o=98,h=102,l=97)],ORDER,**COST,intrabar_policy='target_first')
        self.assertEqual(out['exit_reason'],'STOP_AT_OPEN');self.assertFalse(out['ambiguous_sl_tp'])

if __name__=='__main__':unittest.main()
