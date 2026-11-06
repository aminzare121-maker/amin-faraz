"""Independent arithmetic examples; not a trading engine or profitability test."""
from decimal import Decimal as D, ROUND_FLOOR
import unittest

class Semantics(unittest.TestCase):
    def test_forecast_and_actual_are_different_comparisons(self):
        previous, forecast, actual = D('3'), D('5'), D('4')
        self.assertGreater(forecast-previous, 0)
        self.assertLess(actual-forecast, 0)
    def test_relative_pair_denominator(self):
        self.assertLess(D('1.01')/D('1.02')-1, 0)
    def test_first_drawing_arithmetic(self):
        self.assertEqual(D('4681.455')-D('12.822'), D('4668.633'))
    def test_second_drawing_arithmetic(self):
        self.assertEqual(D('4566.101')-D('20.366'), D('4545.735'))
        self.assertEqual(D('4593.491')-D('4566.101'), D('27.390'))
        self.assertEqual(round(D('27.390')/D('20.366'),2), D('1.34'))
    def test_assumed_anchor_does_not_match(self):
        entry, anchor, stop = map(D, ('4681.455','4665.048','4668.633'))
        self.assertEqual(entry-(entry-anchor)/3-stop, D('7.353'))
        self.assertEqual(anchor+(entry-anchor)/3-stop, D('1.884'))
    def test_fitted_anchor_is_only_inverse_identity(self):
        entry, stop = D('4681.455'), D('4668.633')
        fitted = 3*stop-2*entry
        self.assertEqual(fitted,D('4642.989'))
        self.assertEqual(entry-(entry-fitted)/3,stop)
        # This identity supplies no independent observation of the anchor.
    def test_declared_contract_example_floor_and_minimum(self):
        budget, distance, units_per_lot, step = map(D,('10','3','100','0.01'))
        lots=(budget/(distance*units_per_lot)/step).to_integral_value(rounding=ROUND_FLOOR)*step
        self.assertEqual(lots,D('0.03'))
        self.assertLessEqual(lots*distance*units_per_lot,budget)
        self.assertLess(lots,D('0.10')) # hypothetical minimum => infeasible; don't move stop
    def test_protected_profit_is_not_cash_realization(self):
        entry, stop, current, realized = map(D,('100','101','103','0'))
        self.assertGreater(stop-entry,0)
        self.assertGreater(current-entry,0)
        self.assertEqual(realized,0)
    def test_future_pivot_is_not_available_at_entry(self):
        pivot_time, first_confirmation, proposed_entry = 10,12,11
        self.assertLess(pivot_time, proposed_entry)
        self.assertGreater(first_confirmation,proposed_entry)

if __name__=='__main__': unittest.main(verbosity=2)

