import unittest
from decimal import Decimal as D
from session_research import SessionManagement,ANCHOR,assess_gap,raw_signal,candidates
from historical_engine import simulate
from test_historical_management import bars,setup

class Tests(unittest.TestCase):
    def test_scenario_day_not_historical_utc(self):
        b=bars();a=SessionManagement(b[0]['time']);c=SessionManagement(b[0]['time']+86400*180)
        self.assertEqual(a.scenario_time(b[1]['time']),c.scenario_time(b[1]['time']+86400*180))
        self.assertEqual(a.scenario_time(b[0]['time']),ANCHOR)
    def test_reject_day_overflow(self):
        with self.assertRaisesRegex(ValueError,'OVERFLOW'):SessionManagement(0).scenario_time(86400)
    def test_current_compatible_does_not_verify_gap(self):
        for count in (1,4,196,13):
            r=assess_gap(dict(absent_m15_slots=count,pattern='OTHER'))
            self.assertEqual(r['classification'],'UNKNOWN');self.assertFalse(r['executable_across_gap'])
            if count==1:self.assertEqual(r['cause_assessment'],'UNKNOWN')
    def test_raw_midnight_still_unknown(self):
        b=bars(3)
        for i,x in enumerate(b):x['time']=x['raw_time']=86400*20000+84600+i*900
        b[-1]['low']=D('94')
        r=simulate(b,setup,management=SessionManagement(b[0]['time']),spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        self.assertIsNone(r['scenario_net_usd'])
        self.assertEqual(r['rows'][0]['reason'],'ROLLOVER_COST_UNKNOWN')
    def test_same_primitive_risk_budget(self):
        b=bars();m=SessionManagement(b[0]['time'])
        s=m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3'))
        self.assertEqual(D(s['initial_risk_usd']),D('45.6'));self.assertEqual(m.stage.day,'2000-01-01')
    def test_raw_callback_retains_time_order(self):
        b=bars(50)
        for c in candidates():self.assertIsNone(raw_signal(c)(b[:10]))

if __name__=='__main__':unittest.main()
