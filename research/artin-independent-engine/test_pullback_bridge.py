import unittest
from decimal import Decimal as D
from raw_geometry import Candle
from raw_pipeline import RawPipeline

def b(t,o,h,l,c):return Candle(t,t+900,*map(D,map(str,(o,h,l,c))))

class PullbackBridgeTests(unittest.TestCase):
    def test_raw_stream_generates_core_candidate_without_ready_pivot_flags(self):
        p=RawPipeline('B',('PULLBACK_STANDARD',),900,'f'*64)
        rows=[b(0,10,11,9,10),b(900,10,13,10,12),b(1800,13,14,12,13),
              b(2700,13,13,10,10),b(3600,10,10,8,8),b(4500,8,10,8,10),b(5400,10,10,7,7)]
        found=[]
        for bar in rows:
            r=p.step(bar);found.extend(r['pullback_core_candidates'])
        confirmed=[r for r in found if r['stage']=='CORE_CONFIRMED' and r['side']=='SELL']
        self.assertEqual(len(confirmed),1)
        self.assertEqual(confirmed[0]['post_break_extreme'],D(8))
        self.assertEqual(confirmed[0]['first_known_at'],5400)
        self.assertFalse(confirmed[0]['actionable'])
        # The diagnostic path is not falsely promoted to complete OHLC/teacher entry.
        self.assertTrue(all(d['status']=='REVIEW' for d in r['decisions']))
    def test_bridge_does_not_retroactively_emit_after_missing_bar(self):
        p=RawPipeline('B',('PULLBACK_STANDARD',),900,'e'*64)
        for bar in [b(0,10,11,9,10),b(900,10,13,10,12),b(1800,13,14,12,13),b(2700,13,13,10,10)]:p.step(bar)
        r=p.step(b(4500,10,11,8,9))
        self.assertTrue(any(x['stage']=='REVIEW_MISSING_PATH' for x in r['pullback_core_candidates']))
    def test_fork_keeps_source_state_unchanged(self):
        from pullback_bridge import ClosedPullbackBridge
        x=ClosedPullbackBridge(900,'SOURCE');y=x.fork();y.step(b(0,10,11,9,10),[])
        self.assertIsNone(x.previous)

if __name__=='__main__':unittest.main()
