"""Verify dossier-to-engine source identity remains evidence-only (never a signal)."""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from artin_13_real_m15_gap_audit import REQUIRED

class DossierIdentityBridgeTest(unittest.TestCase):
    def test_all_24_citations_link_to_correct_route_without_orders(self):
        ids=list(REQUIRED)
        routes=[]
        for i,route in enumerate(ids):
            indices=[i+1] + ([i+14] if i<11 else [])
            routes.append({'route_id':route,'source_sessions':[20],
                           'citation_intervals':[{'index':n,'session':20,'start':float(n),'end':float(n)+0.5} for n in indices]})
        dossier={'routes':routes,'citations':24,'trading_authorized':True}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bars.csv'
            with path.open('w',newline='') as f:
                writer=csv.writer(f)
                writer.writerow(('timestamp','open','high','low','close'))
                writer.writerow((1800000000,4000,4002,3999,4001))
            result=evaluate(path,dossier,as_of=1800000900)
        mapped={x['route_id']:x['source_identity'] for x in result['routes']}
        self.assertEqual(set(mapped),set(ids))
        self.assertEqual(sum(len(x['citation_indexes']) for x in mapped.values()),24)
        self.assertEqual(mapped[ids[0]]['citation_indexes'],[1,14])
        # Synthetic session 20 conflicts with multiple engine source references;
        # this must appear on each affected route, not only in a top-level audit.
        for route in result['routes']:
            expected = ('SOURCE_IDENTITY_CONFLICT_REQUIRES_ORIGINAL_AV'
                        if route['route_id'] in result['source_identity_conflicts']
                        else 'SOURCE_IDENTITY_MATCH_UNVERIFIED')
            self.assertEqual(route['source_identity_status'], expected)
        self.assertEqual(result['independent_engine']['orders_created'],0)
        self.assertEqual(result['teacher_approved_entries'],0)
        self.assertFalse(result['evidence_gate']['trade_authorized'])
        self.assertTrue(all(not x['side_decisions'][side]['trade_permitted'] for x in result['routes'] for side in ('BUY','SELL')))

if __name__=='__main__':unittest.main()
