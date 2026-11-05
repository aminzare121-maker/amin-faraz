import unittest
from decimal import Decimal as D
from historical_engine import canonical_bars,segments,simulate,sma_cross_signal

def bars(vals,start=0):
    return canonical_bars([dict(time=start+i*900,open=x,high=x+3,low=x-3,close=x) for i,x in enumerate(vals)],offset_seconds=0,offset_evidence='CONDITIONAL')

def first(hist):return 'buy' if len(hist)==1 else None

def run(bs,fn=first,**kw):
    return simulate(bs,fn,spread='0.2',slippage='0.1',commission_roundtrip_per_lot='4',
                    lots='0.01',stop_distance='5',target_distance='10',
                    **({'rollover_exposure':'PROVEN_NONE'} | kw))

class ResearchTests(unittest.TestCase):
    def test_basic_win(self):
        b=bars([100,100,112,111]);r=run(b)
        self.assertEqual(r['positions'],1);self.assertEqual(r['resolved'],1)
        self.assertEqual(r['rows'][0]['reason'],'TARGET_AT_OPEN_CAPPED')
        self.assertEqual(D(r['scenario_net_usd']),D('9.86'))
    def test_signal_only_prior_closed_bars(self):
        lengths=[]
        def s(h): lengths.append(len(h));return 'buy' if len(h)==1 else None
        run(bars([100,100,112]),s)
        self.assertEqual(lengths,[1])
    def test_open_stop_gap_no_favorable_stop_fill(self):
        r=run(bars([100,100,90,91]));self.assertEqual(r['rows'][0]['reason'],'STOP_OPEN_GAP')
        self.assertLess(D(r['scenario_net_usd']),D('-5'))
    def test_intrabar_ambiguity_unknown(self):
        b=canonical_bars([dict(time=0,open=100,high=100,low=100,close=100),
          dict(time=900,open=100,high=120,low=90,close=100)],offset_seconds=0,offset_evidence='CONDITIONAL')
        r=run(b,policy='unknown')
        self.assertEqual(r['rows'][0]['reason'],'AMBIGUOUS_SL_TP')
        self.assertIsNone(r['scenario_net_usd'])
        self.assertEqual(r['unresolved'],1)
    def test_stop_and_target_policies(self):
        b=canonical_bars([dict(time=0,open=100,high=100,low=100,close=100),
          dict(time=900,open=100,high=120,low=90,close=100)],offset_seconds=0,offset_evidence='CONDITIONAL')
        a=run(b,policy='stop_first');z=run(b,policy='target_first')
        self.assertLess(D(a['scenario_net_usd']),D('0'))
        self.assertGreater(D(z['scenario_net_usd']),D('0'))
    def test_gap_no_crossing_and_unresolved_open_position(self):
        b=bars([100,100],0)+bars([200,200,215],3600)
        r=run(b)
        self.assertEqual(r['segments'],2);self.assertEqual(r['gaps'],1)
        self.assertEqual(r['rows'][0]['reason'],'UNRESOLVED_BOUNDARY')
        self.assertIsNone(r['scenario_net_usd'])
    def test_raw_broker_offset_preserved(self):
        b=canonical_bars([dict(time=7200,open=100,high=101,low=99,close=100)],offset_seconds=-7200,offset_evidence='CONDITIONAL')
        self.assertEqual(b[0]['time'],0);self.assertEqual(b[0]['raw_time'],7200)
    def test_missing_clock_rejected(self):
        with self.assertRaises(ValueError):canonical_bars([dict(time=0,open=1,high=1,low=1,close=1)])
    def test_overlap_duplicate_rejected(self):
        with self.assertRaises(ValueError):canonical_bars([dict(time=0,open=1,high=1,low=1,close=1)]*2,offset_seconds=0,offset_evidence='CONDITIONAL')
    def test_spread_cannot_be_unknown(self):
        with self.assertRaises(ValueError):simulate(bars([100,100]),first,spread=None,slippage='0',commission_roundtrip_per_lot='0')
    def test_rollover_unknown_blocks_net(self):
        b=bars([100,100,100,100,100],start=84600)
        r=run(b,fn=first, max_holding_bars=3,rollover_exposure='UNKNOWN')
        self.assertIsNone(r['scenario_net_usd'])
    def test_sma_requires_history_and_does_not_optimize(self):
        self.assertIsNone(sma_cross_signal(bars([100]*20)))
        with self.assertRaises(ValueError):sma_cross_signal(bars([100]*25),fast=25,slow=20)
    def test_short_spread_cost_not_zero(self):
        def short(h):return 'sell' if len(h)==1 else None
        r=run(bars([100,100,90]),fn=short)
        self.assertEqual(r['rows'][0]['side'],'sell')
        self.assertGreater(D(r['scenario_net_usd']),0)
    def test_no_signal_zero_no_trades(self):
        r=run(bars([100]*30),fn=lambda h:None)
        self.assertEqual(r['positions'],0)
        self.assertEqual(r['scenario_net_usd'],'0')

if __name__=='__main__':unittest.main()
