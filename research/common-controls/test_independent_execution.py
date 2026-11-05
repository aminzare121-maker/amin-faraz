"""Reference arithmetic uses rational numbers, not engine PnL/size helpers."""
import unittest
from fractions import Fraction as F
from decimal import Decimal as D
from unittest.mock import patch
from historical_engine import simulate
from historical_management import Management
from test_historical_management import bars

def signal(side='buy',stop='95'):
    def s(h):return dict(side=side,stop_loss=stop,signal_time=h[-1]['time']) if len(h)==1 else None
    return s

class Tests(unittest.TestCase):
    def test_returned_sizing_stop_is_executed(self):
        b=bars(3);b[1]['low']=D('97')
        m=Management(adaptive_exit=False)
        with patch('historical_management.size_and_target',return_value=dict(volume='.01',stop_loss='98',take_profit='105')):
            r=simulate(b,signal(),management=m,spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        row=r['rows'][0]
        self.assertEqual(row['initial_stop'],'98')
        self.assertEqual(row['reason'],'STOP')
        self.assertEqual(F(row['initial_risk_usd']),F('2.7'))
        self.assertEqual(F(row['net_scenario_usd']),F('-2.5'))
    def test_current_hlc_never_reaches_sizing(self):
        b=bars(3);m=Management();original=m.prepare;seen=[]
        def checked(setup,entry,bar,history,spread):
            self.assertEqual(set(bar),{'time','raw_time','open','time_evidence'})
            self.assertTrue(all(x['time']+900<=bar['time'] for x in history))
            seen.append(1);return original(setup,entry,bar,history,spread)
        with patch.object(m,'prepare',side_effect=checked):
            simulate(b,signal(),management=m,spread='.3',slippage='.1',commission_roundtrip_per_lot='0')
        self.assertTrue(seen)
    def test_buy_sell_pnl_against_rational_reference(self):
        for side,stop in [('buy','95'),('sell','105')]:
            with self.subTest(side=side):
                b=bars(3);b[1].update(low=D('94'),high=D('106'))
                r=simulate(b,signal(side,stop),spread='.3',slippage='.1',commission_roundtrip_per_lot='7',target_distance='50')
                direction=1 if side=='buy' else -1
                entry=F(100)+(F('.3') if side=='buy' else 0)+direction*F('.1')
                exit=F(stop)-direction*F('.1')
                gross=direction*(exit-entry)*100*F('.01');net=gross-F(7)*F('.01')
                row=r['rows'][0]
                self.assertEqual(F(row['entry']),entry);self.assertEqual(F(row['exit']),exit)
                self.assertEqual(F(row['gross_scenario_usd']),gross);self.assertEqual(F(row['net_scenario_usd']),net)
    def test_variable_lot_and_pnl_independent_reference(self):
        b=bars(3);b[1]['low']=D('94');m=Management(adaptive_exit=False)
        r=simulate(b,signal(),management=m,spread='.3',slippage='.1',commission_roundtrip_per_lot='7')
        price=F('100.4');per_lot=(price-F(95)+F('.2'))*100+10
        bound=min(F(50)/per_lot,F(20000)/(price*100),F(10))
        lots=(bound//F('.01'))*F('.01')
        expected=(F('94.9')-price)*100*lots-7*lots
        row=r['rows'][0]
        self.assertEqual(F(row['lots']),lots)
        self.assertEqual(F(row['initial_risk_usd']),per_lot*lots)
        self.assertEqual(F(row['net_scenario_usd']),expected)
    def test_open_gap_reference_and_unresolved_not_zero(self):
        b=bars(3);b[1].update(open=D('100'),low=D('99'),close=D('100'));b[2].update(open=D('90'),low=D('89'),high=D('91'),close=D('90'))
        r=simulate(b,signal(),spread='.3',slippage='.1',commission_roundtrip_per_lot='7')
        self.assertEqual(F(r['rows'][0]['net_scenario_usd']),(F('89.9')-F('100.4'))-F('.07'))
        r=simulate(bars(3),signal(),spread='.3',slippage='.1',commission_roundtrip_per_lot='7')
        self.assertIsNone(r['rows'][0]['net_scenario_usd']);self.assertIsNone(r['scenario_net_usd'])

if __name__=='__main__':unittest.main()
