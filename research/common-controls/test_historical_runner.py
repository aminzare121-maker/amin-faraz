import unittest
from historical_runner import report_for_bars,epoch_utc

def records(n, start=7200):
    return [dict(time=str(start+i*900),open='100',high='102',low='98',close='100') for i in range(n)]

class RunnerTests(unittest.TestCase):
    def test_existing_window_is_exploratory_even_when_cost_supplied(self):
        r=report_for_bars(records(35),offset_seconds=-7200,start_utc=0,end_utc=35*900,
             spread='0.3',slippage='0.1',commission='0')
        self.assertEqual(r['status'],'EXPLORATORY_ONLY')
        self.assertFalse(r['market_profitability_verified'])
        self.assertFalse(r['strategies_are_existing_faraz_six'])
        self.assertEqual(r['m15_rows'],35)
    def test_raw_time_filter(self):
        r=report_for_bars(records(35),offset_seconds=-7200,start_utc=900,end_utc=34*900,
             spread='0.3',slippage='0.1',commission='0')
        self.assertEqual(r['m15_rows'],33)
    def test_no_data(self):
        r=report_for_bars(records(2),offset_seconds=-7200,start_utc=9000,end_utc=10800,
             spread='0.3',slippage='0.1',commission='0')
        self.assertEqual(r['status'],'NO_DATA')
    def test_window_must_be_utc(self):
        with self.assertRaises(ValueError):epoch_utc('2026-11-04T00:00:00')

if __name__=='__main__':unittest.main()
