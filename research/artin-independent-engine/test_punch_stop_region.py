import unittest
from decimal import Decimal as D,localcontext
from punch_stop_region import SelectedPunch

class PunchStopRegionTests(unittest.TestCase):
    def test_source_drawing_point_inside_region_is_not_exact_third_rule(self):
        # Drawing labels, not broker fills. Endpoint interpretation stays explicit.
        p=SelectedPunch('BUY',D('4665.048'),D('4681.455'),100,
            'S22_DRAWN_HORIZONTAL_TO_ILLUSTRATED_ENTRY_HYPOTHESIS','S22_FRAMES548_558')
        r=p.assess(D('4668.633'),100)
        self.assertTrue(r['inside_first_third_from_selected_start'])
        self.assertEqual(r['first_third_high_exact'],'4670517/1000')
        self.assertNotEqual(D('4668.633'),D('4670.517'))
        self.assertFalse(r['exact_stop_generated']);self.assertFalse(r['actionable'])
    def test_sell_direction_and_context_precision_do_not_invert_region(self):
        p=SelectedPunch('SELL',D(110),D(101),10,'SYNTHETIC_SELECTED_ENDPOINTS','SYNTHETIC')
        with localcontext() as c:
            c.prec=2
            self.assertEqual(p.region(10),(107,110))
            self.assertTrue(p.assess(D(109),10)['inside_first_third_from_selected_start'])
            self.assertFalse(p.assess(D(106),10)['inside_first_third_from_selected_start'])
    def test_future_selection_invalid_direction_and_float_are_not_accepted(self):
        p=SelectedPunch('BUY',D(100),D(109),10,'SYNTHETIC','SYNTHETIC')
        with self.assertRaises(ValueError):p.assess(D(101),9)
        with self.assertRaises(ValueError):SelectedPunch('BUY',D(110),D(101),0,'SYNTHETIC','SYNTHETIC')
        with self.assertRaises(ValueError):p.assess(101.0,10)

if __name__=='__main__':unittest.main()
