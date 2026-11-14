import unittest
from quote_math import closed_bar_profit_per_oz,trailing_candidate
class TestQuoteMath(unittest.TestCase):
    def test_short_uses_ask(self):self.assertAlmostEqual(closed_bar_profit_per_oz(-1,4000,.8,4010),9.2)
    def test_long_uses_bid(self):self.assertAlmostEqual(closed_bar_profit_per_oz(1,4000,.8,3990),10)
    def test_short_trailing_stop(self):self.assertAlmostEqual(trailing_candidate(-1,4000,.8,5),4005.8)
    def test_long_trailing_stop(self):self.assertAlmostEqual(trailing_candidate(1,4000,.8,5),3995)
    def test_wider_spread_penalizes_short(self):
        self.assertGreater(closed_bar_profit_per_oz(-1,4000,.5,4010),closed_bar_profit_per_oz(-1,4000,1.5,4010))
    def test_no_optimistic_short_profit(self):
        old=7; corrected=closed_bar_profit_per_oz(-1,4000,.8,4007)
        self.assertAlmostEqual(old-corrected,.8)
if __name__=="__main__":unittest.main()
