import copy,tempfile,unittest
from pathlib import Path
from matched_controls import SPEC,side
from test_selector import bars,CONTEXTS,PROTOCOL,controlled_run
from registry import Registry,digest

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.bank=Registry(Path(self.tmp.name)/'bank');self.data=bars()
        self.bank.artifact('fixture',digest(self.data),{},True)
        self.protocol=dict(PROTOCOL,matched_controls=SPEC)
    def run_controls(self,contexts=None):return controlled_run(self.bank,self.data,contexts or CONTEXTS,self.protocol)
    def test_end_to_end_all_seeds_and_ledger(self):
        r=self.run_controls();result=r['result']
        rows=result['candidates'][0]['validation']['base:stop_first']['rows']
        self.assertEqual([c['seed'] for c in rows[0]['matched_controls']],SPEC['seeds'])
        self.assertEqual(self.run_controls()['action'],'REUSE')
        self.assertIsNone(result['selected_candidate']);self.assertFalse(result['market_profitability_verified'])
        self.assertTrue(all(x['status']=='BLOCKED' for x in result['ranking']['rows']))
    def test_equal_entry_lots_risk_and_context(self):
        rows=self.run_controls()['result']['candidates'][0]['validation']['base:stop_first']['rows']
        for row in rows:
            for c in row['matched_controls']:
                self.assertEqual(c['entry_time'],row['entry_time'])
                self.assertEqual(c['order']['lots'],row['order']['lots'])
                self.assertAlmostEqual(float(c['risk_usd']),abs(float(row['trace']['entry'])-float(row['order']['stop']))*100*float(row['order']['lots']))
                self.assertEqual(c['context_hash'],digest(dict(CONTEXTS['base'],matched_control_spec=SPEC)))
    def test_unknown_swap_suppresses(self):
        ctx=copy.deepcopy(CONTEXTS)
        for c in ctx.values():c.update(swap=None,assumed_swap=0)
        r=self.run_controls(ctx)['result']
        self.assertIsNone(r['scenario_nominee'])
        for candidate in r['candidates']:
            self.assertFalse(candidate['validation']['base:stop_first']['matched_controls']['comparable'])
    def test_seed_depends_only_on_decision_time(self):
        a=[side(s,1000) for s in SPEC['seeds']]
        self.data[-1]['close']=0
        self.assertEqual(a,[side(s,1000) for s in SPEC['seeds']])
    def test_holdout_does_not_change_ranking(self):
        r=self.run_controls()['result'];other=copy.deepcopy(self.data)
        for b in other[248:]:b.update(high=100.1,low=98,close=99)
        bank=Registry(Path(self.tmp.name)/'second');bank.artifact('fixture',digest(other),{},True)
        result=controlled_run(bank,other,CONTEXTS,self.protocol)['result']
        self.assertEqual(r['ranking'],result['ranking'])
    def test_capital_or_duration_mismatch_not_filtered(self):
        r=self.run_controls()['result'];all_rows=[row for c in r['candidates'] for s in c['validation'].values() for row in s['rows']]
        failures=[x for row in all_rows for x in row['matched_controls'] if x['status']=='INCOMPARABLE']
        self.assertTrue(failures)
        self.assertTrue(any('CAPITAL_PATH_MISMATCH' in x['reasons'] or 'DURATION_MISMATCH' in x['reasons'] for x in failures))
    def test_changed_seed_rejected(self):
        self.protocol['matched_controls']=dict(SPEC,seeds=[1])
        with self.assertRaisesRegex(ValueError,'CONTROL_PROTOCOL_CHANGED'):self.run_controls()
    def test_missing_cost_failure_persisted(self):
        ctx=copy.deepcopy(CONTEXTS);ctx['base']['assumed_spread']=None
        with self.assertRaises(ValueError):self.run_controls(ctx)
        self.assertEqual(self.run_controls(ctx)['action'],'BLOCKED_FAILED')
    def test_variable_volume_and_duration_trace(self):
        from matched_controls import paired
        from execution_scenarios import replay
        data=bars()[:4]
        # First stop is reached on the second bar; the other position reaches it immediately.
        data[0].update(high=100.1,low=99.9,close=100)
        kwargs={k:v for k,v in CONTEXTS['base'].items() if k not in ('cost_basis','exit_policy')}
        durations=[]
        for lot,stop in (('.01','99'),('.02','100')):
            order=dict(side='buy',signal_available=0,lots=lot,contract=100,stop=stop,target='105')
            result=replay(data,order,**kwargs,intrabar_policy='stop_first')
            outputs=paired(data,order,CONTEXTS['base'],None,'stop_first',result,10000,{})
            durations.append(result['exit_time'])
            for c in outputs:
                self.assertEqual(c['order']['lots'],lot)
                self.assertEqual(c['candidate_duration_seconds'],result['exit_time'])
                if c['duration_seconds']!=result['exit_time']:self.assertIn('DURATION_MISMATCH',c['reasons'])
        self.assertNotEqual(*durations)

if __name__=='__main__':unittest.main()
