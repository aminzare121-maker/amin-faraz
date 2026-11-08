import copy
import hashlib
import unittest
from diagnostics.probabilities import diagnose_fold, TARGETS
from diagnostics.controls import evaluate_activity, uniform, SEEDS
from diagnostics.quality import audit_quality
from faraz_lab.types import Bar, Candidate, Policy, Symbol, Scenario

class DiagnosticsTests(unittest.TestCase):
    def test_base_and_budget_do_not_use_future_labels(self):
        bars=[Bar(i*900,100,101,99,100) for i in range(1200)]
        signals={i:Candidate('buy',98,[0]*7,i) for i in range(10,1150,10)}
        events={i:{'signal_time':bars[i].time+900,'exit_time':bars[i].time+1800,'net_per_lot':1 if i%30 else -1} for i in signals}
        fold={'name':'unit','train':(0,200000),'calibration':(200000,400000),'validation':(400000,600000),'evaluation':(600000,1000000)}
        a=diagnose_fold(fold,signals,events,bars,{},Scenario('test'),Policy())
        altered=copy.deepcopy(events)
        for e in altered.values():
            if e['signal_time']>=400000: e['net_per_lot'] *= -1
        b=diagnose_fold(fold,signals,altered,bars,{},Scenario('test'),Policy())
        self.assertEqual(a[0]['base_c'],b[0]['base_c'])
        self.assertEqual(a[1],b[1]); self.assertEqual(a[2],b[2])
        self.assertTrue(all(v is None for v in a[2].values()))
        self.assertGreater(a[0]['base_c']['usable_labels'],0)
    def test_random_controls_q_zero_one_missing_and_privacy(self):
        start=1783296000
        bars=[Bar(start+i*900,100,100.2,99.8,100) for i in range(96)]
        signals={i:Candidate('buy',99,[0]*7,i) for i in (1,25,50)}
        folds=[{'name':'WF1','evaluation':(start,start+86400)}]
        q={'WF1':{'M1_raw':0,'M1_cal':1,'M2_raw':None,'M2_cal':.5}}
        pub,private=evaluate_activity(bars,signals,signals,{t:{i:1 for i in signals} for t in TARGETS},q,Scenario('test'),Policy(),Symbol(),folds)
        self.assertEqual(len(pub['portfolios']),28)
        for seed in SEEDS:
            self.assertEqual(set(private['random_gate_maps'][f'R_M1_raw_seed{seed}'].values()),{0})
            self.assertEqual(set(private['random_gate_maps'][f'R_M1_cal_seed{seed}'].values()),{1})
            self.assertEqual(set(private['random_gate_maps'][f'R_M2_raw_seed{seed}'].values()),{None})
        self.assertTrue(all('trades' not in r and 'daily_pnl' not in r for r in pub['portfolios']))
        self.assertEqual(pub['portfolios'][0]['normalization']['net_per_exposure_hour'],None)
    def test_uniform_matches_predeclared_hash(self):
        value=int.from_bytes(hashlib.sha256(b'phase2-v1|1729|WF1|123').digest()[:8],'big')/2**64
        self.assertEqual(uniform(1729,'WF1',123),value)
    def test_quality_overlap_and_causal_prefix(self):
        bars=[Bar(1783296000+i*900,100,101,99,100) for i in range(150)]
        bars[65]=Bar(bars[65].time,100,100,100,100)
        result=audit_quality(bars)
        self.assertEqual(sum(result['primary_priority_counts'].values()),150)
        self.assertEqual(sum(result['exact_bitmask_counts'].values()),87)
        self.assertEqual(audit_quality(bars[:65])['primary_priority_counts']['flat_past64'],0)
        self.assertEqual(result['flat_ohlc_actual_cause'],'UNKNOWN')
