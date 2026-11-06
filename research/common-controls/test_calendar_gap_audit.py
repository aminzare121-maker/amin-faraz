import unittest
from calendar_gap_audit import classify,valid
class EvidenceBoundary(unittest.TestCase):
    def test_single_holiday_not_closed(self):
        self.assertEqual(classify(dict(id=142,absent_m15_slots=1)),'UNKNOWN')
    def test_unlisted_gap_not_promoted(self):
        self.assertEqual(classify(dict(id=999,absent_m15_slots=100)),'UNKNOWN')
    def test_calendar_candidate_not_verified(self):
        self.assertEqual(classify(dict(id=53,absent_m15_slots=12)),'CONDITIONAL')
    def test_invalid_ohlc_detected(self):
        self.assertFalse(valid(dict(open='10',high='9',low='8',close='9',spread='1',tick_volume='1')))
if __name__=='__main__':unittest.main()
