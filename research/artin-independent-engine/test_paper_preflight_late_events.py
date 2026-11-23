"""Regression: a malformed late event must fail before paper replay starts."""
import unittest
from types import SimpleNamespace
from run_engine import validate_paper_events

class PaperPreflightRegression(unittest.TestCase):
    def setUp(self):
        self.observation=SimpleNamespace(at=100)
        self.good={'event':'fill_entry','at':100,'known_at':100,'source':'fixture','lots':'0.01','fill_price':'102'}

    def check_late_rejected(self,late):
        case={'paper_trade':{'events':[self.good,late]}}
        with self.assertRaises(ValueError):
            validate_paper_events(case,self.observation)

    def test_late_management_future_trigger(self):
        self.check_late_rejected({'event':'manage','at':101,'known_at':101,'source':'fixture','label':'riskfree','new_stop':'101',
            'trigger':{'value':True,'known_at':102,'source':'fixture'}})

    def test_late_management_bad_stop(self):
        self.check_late_rejected({'event':'manage','at':101,'known_at':101,'source':'fixture','label':'riskfree','new_stop':'NaN',
            'trigger':{'value':True,'known_at':101,'source':'fixture'}})

    def test_late_close_negative_fee(self):
        self.check_late_rejected({'event':'close','at':101,'known_at':101,'source':'fixture','exit_fill':'105','actual_round_trip_fee':'-1'})

    def test_valid_late_events(self):
        events=[self.good,{'event':'manage','at':101,'known_at':101,'source':'fixture','label':'riskfree','new_stop':'101',
            'trigger':{'value':True,'known_at':101,'source':'fixture'}},
            {'event':'close','at':102,'known_at':102,'source':'fixture','exit_fill':'105','actual_round_trip_fee':'0'}]
        validate_paper_events({'paper_trade':{'events':events}},self.observation)

if __name__=='__main__':
    unittest.main()
