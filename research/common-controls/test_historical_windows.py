import unittest
from decimal import Decimal as D
from unittest.mock import patch
from historical_engine import canonical_bars,simulate
from test_historical_engine import bars,run,first
from historical_candidates import methods,adapter,closed_input,candidates,plan

class WindowsTests(unittest.TestCase):
    def test_rollover_server_midnight_not_utc(self):
        b=bars([100]*5,start=84600)
        for x in b:x['raw_time']=x['time'];x['time']-=7200
        r=run(b,max_holding_bars=3,rollover_exposure='UNKNOWN')
        self.assertEqual(r['rows'][0]['reason'],'ROLLOVER_COST_UNKNOWN')
    def test_utc_midnight_alone_not_server_rollover(self):
        b=bars([100]*5,start=84600)
        for x in b:x['raw_time']=x['time']+7200
        r=run(b,max_holding_bars=3,rollover_exposure='UNKNOWN')
        self.assertIsNotNone(r['scenario_net_usd'])
    def test_unresolved_position_prevents_next_segment_entry(self):
        b=bars([100,100],0)+bars([200,200,215],3600)
        self.assertEqual(run(b)['positions'],1)
    def test_fractional_timestamp_rejected(self):
        with self.assertRaises(ValueError):canonical_bars([dict(time=900.5,open=1,high=1,low=1,close=1)],offset_seconds=0,offset_evidence='CONDITIONAL')
    def test_six_frozen_candidates_and_direct_plan_equivalence(self):
        self.assertEqual(len(methods()),6)
        b=bars([100+i*.3 for i in range(65)])
        inputs,asof=closed_input(b)
        for candidate in candidates():self.assertEqual(adapter(candidate)(b),plan(inputs,asof,candidate))
    def test_adapter_actual_signal_stop_preserved(self):
        b=bars([100+i*.3 for i in range(64)])
        b[-1].update(close=D('130'),high=D('131'))
        signal=adapter(candidates()[0])(b)
        self.assertIsNotNone(signal)
        next_bar=dict(b[-1],time=b[-1]['time']+900,raw_time=b[-1]['raw_time']+900,open=D('130'),high=D('131'),low=D('129'),close=D('130'))
        r=run(b+[next_bar],fn=adapter(candidates()[0]),max_holding_bars=1)
        self.assertEqual(r['rows'][-1]['stop'],signal['stop_loss'])
    def test_callback_sees_only_closed_input(self):
        calls=[]
        def checked(data,asof,candidate):
            self.assertTrue(all(x['final'] and x['observed_at']<=asof for x in data));calls.append(asof);return None
        with patch('historical_candidates.plan',side_effect=checked):run(bars([100]*30),fn=adapter(candidates()[0]))
        self.assertTrue(calls)

if __name__=='__main__':unittest.main()
