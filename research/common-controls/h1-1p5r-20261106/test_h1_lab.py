import os,sys,unittest
from pathlib import Path
from decimal import Decimal as D
sys.path.insert(0,os.environ['FARAZ_RESEARCH_SOURCE'])
import historical_engine as engine
from h1_lab import one,size,pair_part

COST=dict(spread='0',slippage='0',commission_roundtrip_per_lot='0')
MANAGEMENT=dict(policy=dict(max_order_risk_fraction='.005',max_slippage='.2',
    commission_per_lot='10',max_notional_multiple='2'),
    spec=dict(contract_size='100',volume_step='.01',volume_min='.01',volume_max='10',tick_size='.01'))
SETUP=dict(side='buy',stop_loss='95',signal_time=0,candidate={'family':'breakout','lookback':20,'stop_multiple':1.5})
def bars(data):
    return engine.canonical_bars([dict(time=i*900,open=o,high=h,low=l,close=c) for i,(o,h,l,c) in enumerate(data)],
                                 offset_seconds=0,offset_evidence='CONDITIONAL')
class H1Tests(unittest.TestCase):
    def test_exact_target_changes_only_target(self):
        p=bars([(100,101,99,100),(100,111,99,110)])
        base=one(engine,p,1,SETUP,COST,D('.01'),D(10))
        h1=one(engine,p,1,SETUP,COST,D('.01'),D('7.5'))
        self.assertEqual(D(base['target']),D(110));self.assertEqual(D(h1['target']),D('107.5'))
        for k in ('entry','initial_stop','lots','entry_time'):self.assertEqual(base[k],h1[k])
        self.assertEqual(D(h1['net_scenario_usd']),D('7.5'))

    def test_same_bar_ambiguity_keeps_net_unknown(self):
        p=bars([(100,101,99,100),(100,112,94,101)])
        r=one(engine,p,1,SETUP,COST,D('.01'),D('7.5'))
        self.assertEqual(r['reason'],'AMBIGUOUS_SL_TP')
        self.assertIsNone(r['net_scenario_usd'])

    def test_minimum_lot_is_rejected(self):
        sized,reason=size(D(2000),D(1000),D(2000),[D(10000)]*2,MANAGEMENT)
        self.assertIsNone(sized);self.assertEqual(reason,'MIN_LOT_EXCEEDS_BUDGET_OR_NOTIONAL')

    def test_size_uses_smaller_known_equity_and_rounds_down(self):
        s,reason=size(D(100),D(95),D(100),[D(10000),D(9000)],MANAGEMENT)
        self.assertIsNone(reason);self.assertEqual(s['reference_equity'],D(9000))
        self.assertEqual(s['budget'],D('22.5'))
        self.assertEqual(s['lots'],D('.04'));self.assertLessEqual(s['risk'],s['budget'])

    def test_no_early_equity_settlement_and_common_flat_clock(self):
        p=bars([(100,101,99,100),(100,104,99,101),(100,111,99,110),
                (100,111,99,110),(100,111,99,110)])
        def plan(history,t,candidate):return dict(SETUP,signal_time=history[-1]['time'])
        r=pair_part(engine,plan,None,p,COST,MANAGEMENT,[D(10000)]*2)
        self.assertEqual(r['rows'][0][0]['entry_time'],900)
        self.assertEqual(r['rows'][0][1]['entry_time'],2700)
        self.assertEqual(D(r['rows'][0][1]['sizing']['reference_equity']),D(10030))
        self.assertEqual(r['rows'][0][1]['lots'],r['rows'][1][1]['lots'])

    def test_boundary_unknown_blocks_pair_equity(self):
        p=bars([(100,101,99,100),(100,101,99,100)])
        def plan(history,t,candidate):return dict(SETUP,signal_time=history[-1]['time'])
        r=pair_part(engine,plan,None,p,COST,MANAGEMENT,[D(10000)]*2)
        self.assertTrue(r['unknown'])
        self.assertEqual(r['equity'],['10000','10000'])
        self.assertTrue(r['mtm'][0]['truncated_before_uncertain_bar'])

if __name__=='__main__':unittest.main()
