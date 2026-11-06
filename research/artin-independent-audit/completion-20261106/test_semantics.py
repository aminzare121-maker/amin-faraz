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
    def test_first_drawing_inside_origin_third_not_exact_boundary(self):
        origin, entry, stop=map(D,('4665.048','4681.455','4668.633'))
        boundary=origin+(entry-origin)/3
        self.assertEqual(boundary,D('4670.517'))
        self.assertLessEqual(origin,stop)
        self.assertLessEqual(stop,boundary)
        self.assertNotEqual(stop,boundary)
    def test_second_visual_origin_bracket_is_consistent_with_region(self):
        # A coarse axis bracket for the visible low, not a precise OHLC reading.
        entry,stop=D('4566.101'),D('4545.735')
        for origin in (D('4540'),D('4544')):
            self.assertLessEqual(origin,stop)
            self.assertLessEqual(stop,origin+(entry-origin)/3)
    def test_deep_wick_changes_the_hypothesis(self):
        # Never substitute the inverse-fitted low for the teacher's marked line.
        origin,entry,stop=map(D,('4642.989','4681.455','4668.633'))
        self.assertGreater(stop,origin+(entry-origin)/3)
    def test_entry_price_stop_is_not_net_breakeven_with_costs(self):
        # Entirely synthetic: 10 units, actual entry100, exit slippage0.05,
        # fixed round-trip fee2; no separate spread charge in this model.
        entry,units,stop,slip,fee=map(D,('100','10','100','0.05','2'))
        exit_fill=stop-slip
        self.assertEqual((exit_fill-entry)*units-fee,D('-2.50'))
    def test_net_breakeven_requires_cost_compensation_in_declared_model(self):
        entry,units,slip,fee=map(D,('100','10','0.05','2'))
        stop=entry+slip+fee/units
        self.assertEqual(stop,D('100.25'))
        self.assertEqual(((stop-slip)-entry)*units-fee,D('0'))
    def test_gap_can_defeat_nominal_protected_profit(self):
        # Assumed executable gap fill already includes the price jump;
        # do not add the same slippage a second time.
        entry,units,stop,gap_fill,fee=map(D,('100','10','101','99.5','2'))
        self.assertGreater((stop-entry)*units,0)
        self.assertEqual((gap_fill-entry)*units-fee,D('-7'))

if __name__=='__main__': unittest.main(verbosity=2)
