"""Independent-source 13-route live gate integration; absolutely no broker calls."""
import tempfile,unittest,json,shutil
from pathlib import Path
from decimal import Decimal as D
from unittest.mock import patch
from artin_automatic_teacher_recognizer import Bar,Recognition
from artin_teacher_13route_live_gate import (review_closed_bars,gate_pdf_candidate,
                                                 verified_core,TeacherCoreUnavailable)


def B(t,o='100',h='103',l='97',c='101'):
    return Bar(t,D(o),D(h),D(l),D(c))


class Real13RouteSourceGateTests(unittest.TestCase):
    def test_all_13_routes_both_sides_and_no_automatic_authorization(self):
        r=review_closed_bars([B(i*900) for i in range(5)])
        self.assertEqual(r['decisions_checked'],26)
        self.assertEqual(r['rules_checked'],13)
        self.assertEqual(len({d['rule_id'] for d in r['decisions']}),13)
        self.assertEqual({d['side'] for d in r['decisions']},{'BUY','SELL'})
        self.assertFalse(r['video_teacher_semantics_independently_approved'])
        self.assertFalse(r['broker_orders_authorized'])
        self.assertEqual(len(r['teacher_source_manifest_sha256']),64)

    def test_pdf_candidate_not_sufficient_even_with_original_video_stub(self):
        r=review_closed_bars([B(i*900) for i in range(5)])
        signal=Recognition(4500,'BUY','BREAK_FVG_EXACT_FULLBODY','FVG:0:900:1800',
                           '101','103','105','100',(0,900,1800),('Technical(1).pdf#page=14',))
        x=gate_pdf_candidate(signal,r)
        self.assertEqual(x['status'],'BLOCKED_INCOMPLETE_TEACHER_SOURCE')
        self.assertFalse(x['teacher_entry_authorized'])
        self.assertEqual(len(x['matched_teacher_routes']),4)

    def test_three_candle_pivot_not_conjured_from_ohlc(self):
        r=review_closed_bars([B(0,'10','13','10','11'),
                              B(900,'11','11.1','9.5','10'),
                              B(1800,'10','12','10','12')])
        d=next(v for v in r['decisions'] if v['rule_id']=='REVERSAL_THREE' and v['side']=='BUY')
        self.assertNotEqual(d['status'],'ELIGIBLE')
        self.assertIn('three_sequence_pivot_confirmed',d['missing_dependencies'])
        self.assertIn('sentiment_permission',d['missing_dependencies'])

    def test_source_sha_matches_original_patch_manifest(self):
        self.assertEqual(len(verified_core()),64)

    def test_duplicate_or_reverse_bar_times_fail_closed(self):
        with self.assertRaisesRegex(TeacherCoreUnavailable,'UNSORTED_OR_DUPLICATE'):
            review_closed_bars([B(0),B(900),B(900)])

    def test_fake_context_cannot_approve_pdf_candidate(self):
        r=review_closed_bars([B(i*900) for i in range(4)])
        r['decisions']=[{'side':'BUY','rule_id':'BREAK_STRONG','status':'ELIGIBLE',
                         'missing_dependencies':[],'future_dependencies':[]}]
        signal=Recognition(3600,'BUY','BREAK_FVG_EXACT_FULLBODY','FVG:0:900:1800',
                           '101','103','105','100',(0,900,1800),('Technical(1).pdf#page=14',))
        self.assertFalse(gate_pdf_candidate(signal,r)['orders_allowed'])


if __name__=='__main__':unittest.main()