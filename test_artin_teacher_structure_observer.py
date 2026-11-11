"""Proof of causal geometric observations, with teacher approval always false."""
import unittest
from decimal import Decimal as D
from artin_automatic_teacher_recognizer import Bar
from artin_teacher_structure_observer import StructureObserver,observe_structure
from artin_teacher_13route_live_gate import review_closed_bars

def B(t,o,h,l,c):return Bar(t,D(str(o)),D(str(h)),D(str(l)),D(str(c)))

class StructureTests(unittest.TestCase):
    def test_high_pivot_break_then_later_return(self):
        e=StructureObserver()
        bars=[B(0,100,105,99,104),B(900,104,110,103,105),
              B(1800,105,108,102,106),B(2700,106,111,105,111),
              B(3600,111,113,109,112)]
        r=[e.step(b) for b in bars]
        self.assertEqual(len(r[2]['new_pivot_candidates']),1)
        self.assertEqual(r[2]['new_pivot_candidates'][0]['level'],'110')
        self.assertEqual(r[2]['new_pivot_candidates'][0]['known_at'],2700)
        self.assertEqual(r[3]['new_break_candidates'][0]['level'],'110')
        self.assertEqual(r[3]['new_break_candidates'][0]['known_at'],3600)
        self.assertEqual(r[4]['new_retest_candidates'][0]['level'],'110')
        self.assertFalse(r[4]['teacher_trade_authorized'])
        self.assertEqual(e.counts['raw_retests'],1)

    def test_low_pivot_sell_and_retest(self):
        e=StructureObserver()
        bars=[B(0,100,102,98,99), B(900,99,100,90,96),
              B(1800,96,101,94,95), B(2700,95,96,88,89),
              B(3600,89,92,87,91)]
        r=[e.step(x) for x in bars]
        self.assertEqual(r[3]['new_break_candidates'][0]['side'],'SELL')
        self.assertTrue(r[4]['new_retest_candidates'])
        self.assertFalse(r[4]['new_retest_candidates'][0]['teacher_retest_confirmed'])

    def test_gap_clears_pivot_and_prevents_retroactive_break(self):
        e=StructureObserver()
        for b in [B(0,100,105,99,104),B(900,104,110,103,105),B(1800,105,108,102,106)]:e.step(b)
        r=e.step(B(3600,106,116,105,115))
        self.assertTrue(r['gap_reset'])
        self.assertEqual(len(r['new_break_candidates']),0)

    def test_close_on_level_is_not_beyond(self):
        e=StructureObserver()
        for b in [B(0,100,105,99,104),B(900,104,110,103,105),B(1800,105,108,102,106)]:e.step(b)
        r=e.step(B(2700,106,112,106,110))
        self.assertEqual(len(r['new_break_candidates']),0)

    def test_integration_never_authorizes_teacher_trade(self):
        bars=[B(0,100,105,99,104),B(900,104,110,103,105),B(1800,105,108,102,106),B(2700,106,111,105,111)]
        r=review_closed_bars(bars)
        self.assertEqual(r['automatic_structure']['new_break_candidates'][0]['level'],'110')
        self.assertFalse(r['automatic_structure']['teacher_trade_authorized'])
        self.assertFalse(r['broker_orders_authorized'])
        self.assertEqual(r['decisions_checked'],26)

    def test_reject_invalid_time_and_out_of_order(self):
        e=StructureObserver();e.step(B(0,100,102,99,101))
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            e.step(B(0,100,102,99,101))
        with self.assertRaisesRegex(ValueError,'BAD_NATIVE_OPEN_TIME'):
            e.step(object())

if __name__=='__main__':unittest.main()