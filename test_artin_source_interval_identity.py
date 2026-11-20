"""Same-session but different clip ranges must not silently pass source identity."""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from artin_13_real_m15_gap_audit import REQUIRED

class IntervalIdentityTest(unittest.TestCase):
    def test_same_session_different_ranges_are_flagged_without_orders(self):
        routes=[]
        for i,route in enumerate(REQUIRED):
            indices=[i+1]+([i+14] if i<11 else [])
            routes.append({'route_id':route,'source_sessions':[21],
                'citation_intervals':[{'index':n,'session':21,'start':float(n),'end':float(n)+0.5} for n in indices]})
        dossier={'routes':routes,'citations':24}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bars.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(('timestamp','open','high','low','close'))
                w.writerow((1800000000,4000,4002,3999,4001))
            result=evaluate(p,dossier,as_of=1800000900)
        self.assertEqual(len(result['source_identity_conflicts']),13)
        self.assertTrue(all(v['interval_identity_mismatch'] for v in result['source_identity_conflicts'].values()))
        self.assertEqual(result['independent_engine']['orders_created'],0)
        self.assertEqual(result['trades_executed'],0)
        self.assertTrue(all(not x['side_decisions'][s]['trade_permitted']
                            for x in result['routes'] for s in ('BUY','SELL')))

if __name__=='__main__':unittest.main()
