import unittest
from all_gap_neighbor_audit import candidate,label
class ParentSlotEvidence(unittest.TestCase):
    def test_recurrence_is_only_candidate(self):
        self.assertEqual(candidate(dict(pattern='ONE_HOUR_RECURRENT_CANDIDATE',id=1,absent_m15_slots=4)),'SESSION_CLOSURE_CANDIDATE')
    def test_single_holiday_stays_feed_absence_candidate(self):
        self.assertEqual(candidate(dict(pattern='OTHER',id=142,absent_m15_slots=1)),'FEED_ABSENCE_CANDIDATE')
    def test_unlisted_exception_unresolved(self):
        self.assertEqual(candidate(dict(pattern='OTHER',id=999,absent_m15_slots=5)),'UNRESOLVED')
    def test_label_does_not_assert_utc(self):
        self.assertEqual(label(0),'1970-01-01T00:00:00')
if __name__=='__main__':unittest.main()
