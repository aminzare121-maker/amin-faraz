"""Regression checks for the real independent entry-engine / M15 bridge.
Synthetic bars test software wiring only, never teacher meaning or P&L.
"""
import csv
import tempfile
import unittest
from pathlib import Path
from artin_13_per_bar_teacher_bridge import evaluate
from artin_13_real_m15_gap_audit import REQUIRED

class TestIntegratedEntryBridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"bars.csv"
        with self.path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            w.writerow(("timestamp","open","high","low","close"))
            w.writerow((1800000000,4000,4002,3999,4001))
            w.writerow((1800000900,4001,4003,4000,4002))
    def tearDown(self):
        self.tmp.cleanup()
    def test_all_routes_both_sides_reach_real_engine_and_remain_blocked(self):
        result=evaluate(self.path,as_of=1800001800)
        self.assertEqual(result["source_rows"],2)
        self.assertEqual(result["independent_engine"]["evaluations"],2*len(REQUIRED)*2)
        self.assertEqual(set(result["independent_engine"]["route_statuses"]),set(REQUIRED))
        self.assertEqual(result["independent_engine"]["orders_created"],0)
        for route_id in REQUIRED:
            self.assertEqual(result["independent_engine"]["route_statuses"][route_id].get("REVIEW"),4)
            self.assertEqual(result["independent_engine"]["route_reasons"][route_id].get("MISSING:sentiment_permission"),4)
        self.assertEqual(result["teacher_approved_entries"],0)
        self.assertEqual(result["trades_executed"],0)
        self.assertIsNone(result["net_profit"])
        self.assertFalse(result["evidence_gate"]["trade_authorized"])
        for route in result["routes"]:
            for side in ("BUY","SELL"):
                self.assertFalse(route["side_decisions"][side]["trade_permitted"])
                self.assertEqual(route["side_decisions"][side]["states"]["ENGINE_REVIEW"],2)
                self.assertEqual(route["side_decisions"][side]["states"]["REASON:MISSING:sentiment_permission"],2)
                self.assertEqual(route["side_decisions"][side]["states"]["BLOCKED_TEACHER_AV_UNVERIFIED"],2)
    def test_private_dossier_session_mismatch_is_diagnostic_only(self):
        from artin_13_teacher_acceptance_matrix import EXPECTED_ROUTES
        # Build a structurally complete *synthetic* dossier, with no approval.
        # All 24 indexes are unique; a deliberate session conflict must surface.
        ids=sorted(EXPECTED_ROUTES)
        routes=[]
        for i,route in enumerate(ids):
            intervals=[{'index':j+1,'session':15 if route=='PULLBACK_STANDARD' else 20,
                        'start':j*10,'end':j*10+5} for j in range(i*24//len(ids),(i+1)*24//len(ids))]
            if not intervals:
                intervals=[{'index':i+1,'session':20,'start':i*10,'end':i*10+5}]
            routes.append({'route_id':route,'citation_intervals':intervals})
        # Normalize coverage without claiming these intervals came from videos.
        for r in routes:r['citation_intervals']=[]
        for j in range(24):
            route=routes[j%len(routes)]
            route['citation_intervals'].append({'index':j+1,
                'session':15 if route['route_id']=='PULLBACK_STANDARD' else 20,
                'start':j*10,'end':j*10+5})
        dossier={'routes':routes,'citations':24,'trading_authorized':False}
        result=evaluate(self.path,dossier,as_of=1800001800)
        conflict=result['source_identity_conflicts']['PULLBACK_STANDARD']
        self.assertEqual(conflict['dossier_sessions_unverified'],[15])
        self.assertEqual(conflict['engine_sessions_unverified'],[16])
        self.assertFalse(result['evidence_gate']['trade_authorized'])
        self.assertEqual(result['independent_engine']['orders_created'],0)

    def test_future_bar_is_rejected_before_entry_evaluation(self):
        with self.assertRaisesRegex(ValueError,"UNCLOSED_OR_FUTURE_SOURCE_BAR"):
            evaluate(self.path,as_of=1800001799)
    def test_duplicate_or_out_of_order_bar_is_rejected(self):
        with self.path.open("a",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow((1800000900,4002,4003,4001,4002))
        with self.assertRaisesRegex(ValueError,"INVALID_SOURCE_BAR"):
            evaluate(self.path,as_of=1800002700)

    def test_direct_entry_segments_missing_m15_candle_without_orders(self):
        # Direct engine callers must enforce the same causal continuity as MT5 intake.
        with self.path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(("timestamp", "open", "high", "low", "close"))
            w.writerow((1800000000, 4000, 4002, 3999, 4001))
            w.writerow((1800001800, 4001, 4003, 4000, 4002))
        result = evaluate(self.path, as_of=1800002700)
        self.assertEqual(result["causal_segments"], 2)
        self.assertEqual(result["gap_boundaries"], [{"previous_open":1800000000,"next_open":1800001800,"missing_m15_slots":1}])
        self.assertEqual(result["independent_engine"]["orders_created"], 0)
        self.assertEqual(result["teacher_approved_entries"], 0)
        self.assertEqual(result["decision_arbitration"]["decision"], "BLOCKED")

    def test_untrusted_approval_rejected_before_market_clock(self):
        # Reject invalid evidence before any bar replay or market clock check.
        with self.assertRaisesRegex(ValueError,"INVALID_PRIVATE_DOSSIER:INCOMPLETE_PRIVATE_DOSSIER"):
            evaluate(self.path,{"trading_authorized":True},as_of=1800001799)

    def test_private_approval_flag_cannot_authorize(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PRIVATE_DOSSIER:INCOMPLETE_PRIVATE_DOSSIER"):
            evaluate(self.path,{"trading_authorized":True},as_of=1800001800)

if __name__=="__main__":
    unittest.main()
