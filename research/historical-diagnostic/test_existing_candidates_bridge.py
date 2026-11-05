import unittest
from types import SimpleNamespace
from existing_candidates_bridge import bridge_existing
from test_historical_diagnostic import bar

CTX={'base':{'cost_basis':'ASSUMPTION','assumed_spread':'.3','slippage':'.1','commission':'0','assumed_swap':'0'},
     'stress':{'cost_basis':'ASSUMPTION','assumed_spread':'.5','slippage':'.3','commission':'0','assumed_swap':'0'}}

class Bridge(unittest.TestCase):
    def test_original_evaluator_stub_short_gap_segments(self):
        rows=[bar(i) for i in range(18)]+[bar(i) for i in range(60,82)]
        calls=[]
        def evaluator(bars,start,end,ctx,candidate,model,policy):
            self.assertTrue(all(b['final'] and b['observed_at']==b['time']+900 for b in bars))
            self.assertTrue(all(b['time_basis']=='raw-broker-server-unverified' for b in bars))
            calls.append((candidate.id,len(bars),policy))
            return [{'net':'.5','trace':{'exit_reason':'TARGET'}}]
        out=bridge_existing(rows,CTX,candidates=[SimpleNamespace(id='real-candidate-stub',lookback=10)],evaluator=evaluator)
        self.assertEqual(out['source_segments'],2)
        self.assertEqual(out['max_segment_bars'],22)
        self.assertEqual(len(calls),12)
        self.assertEqual(len(out['results']),6)
        self.assertFalse(out['market_profitability_verified'])
    def test_no_implicit_zero_swap(self):
        bad={k:dict(v) for k,v in CTX.items()}
        bad['base'].pop('assumed_swap')
        with self.assertRaisesRegex(ValueError,'SWAP'):
            bridge_existing([bar(0)],bad,candidates=[],evaluator=lambda *args:[])
    def test_no_unknown_context(self):
        with self.assertRaisesRegex(ValueError,'TWO_FIXED'):
            bridge_existing([bar(0)],{'base':CTX['base']},candidates=[],evaluator=lambda *args:[])
    def test_short_segment_blocks_runner(self):
        hits=[]
        def evaluator(*args):hits.append(1);return []
        out=bridge_existing([bar(i) for i in range(9)],CTX,candidates=[SimpleNamespace(id='x',lookback=10)],evaluator=evaluator)
        self.assertEqual(hits,[])
        self.assertEqual(out['results'][0]['segments_skipped_for_warmup'],1)
    def test_failed_segment_blocks_net(self):
        def evaluator(*args):raise RuntimeError('ERROR')
        out=bridge_existing([bar(i) for i in range(20)],CTX,candidates=[SimpleNamespace(id='x',lookback=10)],evaluator=evaluator)
        self.assertIsNone(out['results'][0]['scenario_net_usd'])
        self.assertEqual(out['results'][0]['failed_segments'][0]['error_type'],'RuntimeError')

if __name__=='__main__':unittest.main()
