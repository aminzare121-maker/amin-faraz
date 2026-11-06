import unittest
from decimal import Decimal as D,localcontext
from retouch_behavior import HalfReference,RetouchWait

class RetouchBehaviorTests(unittest.TestCase):
    def test_s21_body_retouch_can_arrive_before_next_candle_close(self):
        r=HalfReference('BODY','BUY','BODY_S21',D(100),D(110),900,'S21_SOURCE_CONDITIONAL_FIXTURE')
        m=RetouchWait(r,'OBSERVED_ASK')
        self.assertFalse(m.observe(D(108),901,901,'SYNTHETIC_QUOTE',901)['new_trigger'])
        x=m.observe(D(105),905,905,'SYNTHETIC_QUOTE',905)
        self.assertTrue(x['new_trigger']);self.assertFalse(x['new_candle_close_required'])
        self.assertFalse(x['fill_assumed']);self.assertFalse(x['actionable'])
        self.assertTrue(x['source_formula_verified'])
        self.assertEqual(x['reference_interpretation'],'EXPLICIT_BODY_REFERENCE_S21')
        self.assertFalse(m.observe(D(104),906,906,'SYNTHETIC_QUOTE',906)['new_trigger'])
    def test_s19_selected_range_kept_distinct_from_body_reference(self):
        # Normalized reference geometry, not raw source NZDUSD market OHLC.
        r=HalfReference('RANGE','SELL','SELECTED_RANGE_S19',D(100),D(200),900,'S19_SOURCE_RANGE_GEOMETRY')
        m=RetouchWait(r,'TEACHER_SELECTED_RANGE_COORDINATE')
        self.assertFalse(m.observe(D(140),901,901,'NORMALIZED_COORDINATE',901)['new_trigger'])
        x=m.observe(D(150),902,902,'NORMALIZED_COORDINATE',902)
        self.assertTrue(x['new_trigger'])
        self.assertTrue(x['alternative_body_not_excluded'])
        self.assertFalse(x['source_formula_verified'])
        self.assertEqual(x['reference_interpretation'],'SELECTED_DRAWING_RANGE_NOT_PROVEN_UNIQUE_TEACHER_FORMULA')
        self.assertEqual(r.kind,'SELECTED_RANGE_S19')
        with self.assertRaises(ValueError):HalfReference('X','SELL','AUTO_PICK_BODY_OR_RANGE',D(100),D(200),900,'SOURCE')
    def test_parent_candle_range_cannot_count_as_post_completion_touch(self):
        m=RetouchWait(HalfReference('B','BUY','BODY_S21',D(100),D(110),900,'SOURCE'),'OBSERVED_ASK')
        with self.assertRaises(ValueError):m.observe(D(105),900,900,'PARENT_CANDLE_RANGE',900)
        with self.assertRaises(ValueError):m.observe(D(105),901,900,'FUTURE_PRICE',901)
        with self.assertRaises(ValueError):m.observe(D(105),901,902,'NOT_AVAILABLE',901)
        self.assertEqual(m.state,'WAITING')
    def test_midpoint_is_exact_even_with_small_decimal_context(self):
        r=HalfReference('R','SELL','SELECTED_RANGE_S19',D('100.00002'),D('100.00006'),900,'SYNTHETIC_CONTEXT_ROUNDING')
        with localcontext() as c:
            c.prec=2
            self.assertEqual(r.midpoint,D('100.00004'))

if __name__=='__main__':unittest.main()
