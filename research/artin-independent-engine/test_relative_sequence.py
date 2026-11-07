import unittest
from decimal import Decimal as D,localcontext
from fractions import Fraction
from entry_engine import Fact
from raw_geometry import Candle
from relative_sequence import measure

def bar(t,o,c):
    a,b=D(o),D(c)
    return Candle(t,t+60,a,max(a,b),min(a,b),b)

class RelativeSequenceTests(unittest.TestCase):
    def test_explicit_window_max_and_no_strength_label(self):
        history=(bar(0,'1','20'),bar(60,'10','12'),bar(120,'12','15'))
        r=measure(history,bar(180,'15','21'),Fact(60,60,'SYNTHETIC_SELECTED_START'),'SYNTHETIC_HISTORY',240,60)
        self.assertEqual(r['context_max_body'],Fraction(3))
        self.assertEqual(r['target_body_to_context_max_body'],Fraction(2))
        self.assertTrue(r['target_larger_than_every_prior_body'])
        self.assertEqual(r['parent_open_times'],(60,120,180))
        self.assertIsNone(r['strength_label']);self.assertFalse(r['actionable']);self.assertTrue(r['candidate_only'])

    def test_missing_gap_and_future_are_unknown_not_false(self):
        history=(bar(0,'10','11'),bar(120,'11','12'));target=bar(180,'12','13')
        for selected,at,reason in [(None,240,'MISSING_SOURCED_SEQUENCE_START'),
                (Fact(0,181,'SYNTHETIC'),240,'SEQUENCE_SELECTION_NOT_KNOWN_BEFORE_TARGET'),
                (Fact(0,0,'SYNTHETIC'),239,'TARGET_NOT_CLOSED_AS_OF_DECISION'),
                (Fact(60,0,'SYNTHETIC'),240,'SELECTED_START_BAR_MISSING'),
                (Fact(0,0,'SYNTHETIC'),240,'GAP_IN_SELECTED_SEQUENCE')]:
            r=measure(history,target,selected,'SYNTHETIC',at,60)
            self.assertEqual(r['reason'],reason);self.assertEqual(r['status'],'UNKNOWN')
            self.assertIsNone(r['target_larger_than_every_prior_body'])
        future=measure(history+(bar(240,'13','14'),),target,Fact(0,0,'SYNTHETIC'),'SYNTHETIC',300,60)
        self.assertEqual(future['reason'],'FUTURE_OR_UNCLOSED_PRIOR_HISTORY')
        self.assertEqual(future['status'],'UNKNOWN')

    def test_exact_ratio_ignores_decimal_context_precision_and_equality(self):
        history=(bar(0,'1','1.12345678901234567890123456789'),)
        target=bar(60,'1','1.37037036703703703670370370367')
        with localcontext() as ctx:
            ctx.prec=2
            r=measure(history,target,Fact(0,0,'SYNTHETIC'),'SYNTHETIC',120,60)
        self.assertEqual(r['target_body_to_context_max_body'],Fraction(3))
        equal=measure(history,bar(60,'1','1.12345678901234567890123456789'),Fact(0,0,'SYNTHETIC'),'SYNTHETIC',120,60)
        self.assertFalse(equal['target_larger_than_every_prior_body'])
        self.assertEqual(equal['target_body_to_context_max_body'],Fraction(1))

    def test_zero_body_denominator_is_undefined(self):
        r=measure((bar(0,'10','10'),),bar(60,'10','12'),Fact(0,0,'SYNTHETIC'),'SYNTHETIC',120,60)
        self.assertEqual(r['status'],'UNDEFINED');self.assertIsNone(r['target_body_to_context_max_body'])

    def test_invalid_order_interval_or_start_type_rejected(self):
        for history,target,selected,interval in [
            ((bar(60,'10','11'),bar(0,'11','12')),bar(120,'12','13'),Fact(0,0,'SYNTHETIC'),60),
            ((bar(0,'10','11'),),bar(60,'11','12'),Fact(True,0,'SYNTHETIC'),60),
            ((bar(0,'10','11'),),bar(60,'11','12'),Fact(0,0,'SYNTHETIC'),15)]:
            with self.assertRaises(ValueError):measure(history,target,selected,'SYNTHETIC',180,interval)

if __name__=='__main__':unittest.main()
