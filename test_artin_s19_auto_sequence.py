"""Verify direct, source-bounded S19 3-candle geometry on closed OHLC."""
import unittest
from decimal import Decimal as D
from artin_automatic_teacher_recognizer import Bar
from artin_s19_auto_sequence import observe_s19_three
from artin_teacher_13route_live_gate import review_closed_bars


def B(t,o,h,l,c):return Bar(t,D(o),D(h),D(l),D(c))


class S19AutoSequenceTests(unittest.TestCase):
    def setUp(self):
        # A strict trough at the middle bar; third close is known only at 2700.
        self.seq=[B(0,'100','102','99','101'),B(900,'101','102','95','100'),
                  B(1800,'100','107','99','106')]

    def test_measured_middle_pivot_is_not_teacher_confirmed(self):
        r=observe_s19_three(self.seq)
        self.assertTrue(r['by_side']['BUY']['strict_middle_extremum_pivot_candidate'])
        self.assertFalse(r['by_side']['BUY']['teacher_pivot_selected_or_confirmed'])
        self.assertEqual(r['third_close_known_at'],2700)
        self.assertEqual(r['by_side']['BUY']['third_candle_close'],'106')
        self.assertFalse(r['trade_authorized'])

    def test_doubt_requires_real_aligned_candle_not_any_color(self):
        r=observe_s19_three(self.seq)
        self.assertTrue(r['by_side']['SELL']['conditional_one_doubt_in_side_candles'])
        self.assertFalse(r['by_side']['BUY']['conditional_one_doubt_in_side_candles'])
        self.assertFalse(r['by_side']['SELL']['sentiment_aligned_doubt_proven'])

    def test_gap_cannot_form_teacher_sequence(self):
        x=[self.seq[0],self.seq[1],B(3600,'100','107','99','106')]
        r=observe_s19_three(x)
        self.assertEqual(r['status'],'GAPPED_THREE_CANDLE_WINDOW')
        self.assertFalse(r['trade_authorized'])

    def test_future_and_duplicate_time_rejected(self):
        with self.assertRaisesRegex(ValueError,'NON_CAUSAL'):
            observe_s19_three([self.seq[0],self.seq[1],self.seq[1]])

    def test_shape_ambiguity_remains_unknown_not_false(self):
        # Body 2, largest wick 1.5, total shadows 3; neither S13
        # comparison resolves it, so no "confidence" claim is permitted.
        x=B(0,'100','103.5','98.5','102')
        r=observe_s19_three([x,B(900,'99','101','98','100'),B(1800,'100','102','99','101')])
        self.assertIsNone(r['shapes'][0]['doubt'])
        self.assertIsNone(r['shapes'][0]['confidence'])

    def test_full_engine_receives_auto_measurement_but_does_not_approve(self):
        r=review_closed_bars(self.seq)
        self.assertEqual(r['s19_three_candle_auto_measurement']['third_close_known_at'],2700)
        self.assertFalse(r['broker_orders_authorized'])
        self.assertFalse(r['s19_three_candle_auto_measurement']['trade_authorized'])
        d=next(v for v in r['decisions'] if v['rule_id']=='REVERSAL_THREE' and v['side']=='BUY')
        self.assertIn('sentiment_permission',d['missing_dependencies'])
        self.assertIn('three_sequence_pivot_confirmed',d['missing_dependencies'])


if __name__=='__main__':unittest.main()