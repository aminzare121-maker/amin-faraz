import unittest
from decimal import Decimal as D
from historical_engine import simulate
from factorial_controls import control,matched,validate_windows
from test_historical_management import bars,setup

class Tests(unittest.TestCase):
    def test_fixed_exit_survives_variable_sizing(self):
        r=simulate(bars(20),setup,management=control('VF'),spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        self.assertEqual(r['rows'][0]['reason'],'MAX_HOLD_CLOSE_ASSUMED')
        self.assertIsNotNone(r['rows'][0]['target'])
        self.assertNotEqual(D(r['rows'][0]['lots']),D('.01'))
        self.assertEqual(r['rows'][0]['stop_adjustments'],[])
    def test_fixed_volume_adaptive_no_horizon(self):
        r=simulate(bars(20),setup,management=control('FA'),spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        self.assertEqual(r['unresolved'],1);self.assertEqual(D(r['rows'][0]['lots']),D('.01'))
        self.assertIsNone(r['rows'][0]['target'])
    def test_matching_uses_entry_not_trade_ordinal(self):
        def r(t,net='1'):return dict(signal_time=t,entry_time=t,side='buy',exit_time=t+900,reason='STOP',lots='.01',net_scenario_usd=net)
        m=matched({'rows':[r(1),r(2,None)]},{'rows':[r(2),r(3)]})
        self.assertEqual((m['matched'],m['only_left'],m['only_right']),(1,1,1))
        self.assertIsNone(m['pairs'][0]['net_difference'])
    def test_overlap_blocked(self):
        with self.assertRaisesRegex(ValueError,'OVERLAPPING'):validate_windows([dict(start=1,end=4),dict(start=3,end=6)])
        self.assertTrue(validate_windows([dict(start=1,end=4),dict(start=4,end=6)]))
    def test_cost_envelope_not_equal_scenario_fee(self):
        data=bars(3);data[1]['low']=D('94')
        a=simulate(data,setup,management=control('FA'),spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        b=simulate(data,setup,management=control('FA'),spread='.3',slippage='.1',commission_roundtrip_per_lot='10')
        x,y=a['rows'][0],b['rows'][0]
        self.assertEqual(x['initial_risk_usd'],y['initial_risk_usd'])
        self.assertEqual(D(x['net_scenario_usd'])-D(y['net_scenario_usd']),D('.10'))
    def test_fixed_veto_difference_explicit(self):
        b=bars();s=setup(b[:1]);m=control('VF')
        self.assertIsNone(m.prepare(s,D('101.1'),b[1],b[:1],D('1')))
        self.assertIsNotNone(control('FA').prepare(s,D('101.1'),b[1],b[:1],D('1')))

if __name__=='__main__':unittest.main()
