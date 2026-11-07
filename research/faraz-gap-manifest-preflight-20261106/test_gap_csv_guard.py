import csv,tempfile,unittest
from pathlib import Path
from gap_csv_guard import validate

class Tests(unittest.TestCase):
    def check(self,rows):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'gaps.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['gap_id','first_missing_candle_open_raw_label','missing_m15_count']);w.writerows(rows)
            return validate(p)
    def test_valid(self):self.assertEqual(self.check([[1,'2025-11-28T11:00:00',2],[2,'2025-11-28T11:30:00',1]]),[])
    def test_overlap(self):self.assertTrue(self.check([[1,'2025-11-28T11:00:00',2],[2,'2025-11-28T11:15:00',1]]))
    def test_duplicate(self):self.assertTrue(self.check([[1,'2025-11-28T11:00:00',1],[1,'2025-11-28T12:00:00',1]]))
    def test_unaligned(self):self.assertTrue(self.check([[1,'2025-11-28T11:01:00',1]]))
    def test_timezone(self):self.assertTrue(self.check([[1,'2025-11-28T11:00:00+02:00',1]]))
    def test_negative(self):self.assertTrue(self.check([[1,'2025-11-28T11:00:00',-1]]))
    def test_noninteger(self):self.assertTrue(self.check([[1,'2025-11-28T11:00:00','1.5']]))
    def test_bad_date(self):self.assertTrue(self.check([[1,'not-a-date',1]]))
if __name__=='__main__':unittest.main()
