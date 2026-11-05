import unittest
from decimal import Decimal
from historical_diagnostic import bars_from_rows,segments,fixed_breakout,replay,diagnose

COST=dict(spread='.2',slippage='.1',commission_roundtrip_lot='0',swap_roundtrip_lot='0')

def bar(i,o=100,h=101,l=99,c=100):
    return dict(time=str(900000+900*i),open=str(o),high=str(h),low=str(l),close=str(c))

def intent(side='BUY'):
    return dict(side=side,stop_distance='2',target_distance='4',lots='.01')

class Tests(unittest.TestCase):
    def test_segment_without_filling_gaps(self):
        self.assertEqual([len(x) for x in segments(bars_from_rows([bar(0),bar(1),bar(6),bar(7)]))],[2,2])
    def test_bad_time_order(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            bars_from_rows([bar(0),bar(0)])
    def test_bad_ohlc(self):
        with self.assertRaisesRegex(ValueError,'OHLC'):
            bars_from_rows([bar(0,h=98)])
    def test_buy_target(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=105,l=100,c=104)])
        result,_=replay(p,1,intent(),COST)
        self.assertEqual(result['exit_reason'],'TARGET')
        self.assertEqual(Decimal(result['net_scenario_usd']),Decimal('3.9'))
    def test_sell_stop_ask_execution(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=103,l=99,c=101)])
        result,_=replay(p,1,intent('SELL'),COST)
        self.assertEqual(result['exit_reason'],'STOP')
        self.assertEqual(Decimal(result['net_scenario_usd']),Decimal('-2.1'))
    def test_collision_unknown_does_not_invent_pnl(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=110,l=90,c=100)])
        r,_=replay(p,1,intent(),COST)
        self.assertTrue(r['intrabar_ambiguous'])
        self.assertIsNone(r['net_scenario_usd'])
    def test_collision_both_scenario_policies(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=110,l=90,c=100)])
        r,_=replay(p,1,intent(),COST,'stop_first')
        s,_=replay(p,1,intent(),COST,'target_first')
        self.assertLess(Decimal(r['net_scenario_usd']),Decimal(s['net_scenario_usd']))
    def test_unclosed_never_marked_profit(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=100,l=100,c=100)])
        r,_=replay(p,1,intent(),COST)
        self.assertEqual(r['exit_reason'],'UNCLOSED_AT_SEGMENT_END')
        self.assertIsNone(r['net_scenario_usd'])
    def test_unknown_swap_blocks_net(self):
        p=bars_from_rows([bar(0),bar(1,o=100,h=105,l=100,c=104)])
        cost=dict(COST,swap_roundtrip_lot=None)
        r,_=replay(p,1,intent(),cost)
        self.assertIsNone(r['net_scenario_usd'])
    def test_signal_never_sees_current_bar(self):
        seen=[]
        def signal(history):
            seen.append(history[-1]['time']);return None
        result=diagnose([bar(i) for i in range(13)],signal,lookback=3,cost=COST)
        self.assertEqual(seen[0],int(bar(2)['time']))
        self.assertEqual(result['n_scenario_entries'],0)
    def test_all_short_segments_skip(self):
        data=[]
        for i in (0,50,100):data.extend(bar(i+j) for j in range(6))
        result=diagnose(data,cost=COST)
        self.assertEqual(result['short_segments_skipped'],3)
        self.assertIsNone(result['net_scenario_usd'])
    def test_fixed_baseline_below_240_bars(self):
        data=[bar(i,o=100+i,h=103+i,l=99+i,c=102.5+i) for i in range(24)]
        result=diagnose(data,cost=COST)
        self.assertEqual(result['n_segments'],1)
        self.assertGreater(result['n_scenario_entries'],0)
        self.assertFalse(result['market_profitability_verified'])
    def test_bad_lots_no_rounding(self):
        p=bars_from_rows([bar(0),bar(1)])
        with self.assertRaisesRegex(ValueError,'INVALID_ORDER'):
            replay(p,1,dict(intent(),lots='.015'),COST)
    def test_missing_cost_blocked(self):
        p=bars_from_rows([bar(0),bar(1)])
        with self.assertRaisesRegex(ValueError,'COST_SCENARIO_MISSING'):
            replay(p,1,intent(),dict(COST,spread=None))
    def test_no_order_api(self):
        import historical_diagnostic as hd
        self.assertFalse(any(hasattr(hd,k) for k in ('order_send','order_check','place_order','MetaTrader5')))

if __name__=='__main__':unittest.main()
