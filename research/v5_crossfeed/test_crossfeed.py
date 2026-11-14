import unittest
import pandas as pd
from v5_crossfeed_gate import choose_offset, direction_score
from v5_incremental_information import prepare, predictive_check

class CrossfeedGuardTests(unittest.TestCase):
    def base(self):
        t=pd.date_range('2026-03-10 12:00Z',periods=8,freq='15min')
        ep=pd.DataFrame({
            'open':[10,11,12,13,14,15,16,17],
            'close':[11,10,13,12,15,14,17,16],
            'direction':['up','down']*4},index=t)
        ext=pd.DataFrame({'time':t[:4],'corrected_time':t[:4],
            'offset_minutes':[0]*4,'external_dir':['up','down','up','down']})
        return ep,ext
    def test_same_bar_match_does_not_predict_next(self):
        ep,ext=self.base()
        result=prepare(ep,ext)
        self.assertEqual((result.external_dir==result.direction).sum(),4)
        self.assertEqual(predictive_check(result,1)['external_momentum_accuracy'],0)
    def test_next_bar_is_strictly_future(self):
        ep,ext=self.base()
        result=prepare(ep,ext)
        self.assertEqual(result.iloc[0].next1_dir,'down')
    def test_offset_mismatch_rejected(self):
        ep,ext=self.base();ext.loc[1,'offset_minutes']=60
        with self.assertRaises(ValueError):prepare(ep,ext)
    def test_repeated_time_rejected(self):
        ep,ext=self.base();ext.loc[1,'corrected_time']=ext.loc[0,'corrected_time']
        with self.assertRaises(ValueError):prepare(ep,ext)
    def test_calibration_rejects_tiny_sample(self):
        ep,ext=self.base()
        with self.assertRaises(ValueError):choose_offset(ext,ep)
    def test_missing_join_not_success(self):
        ep,ext=self.base()
        ext['corrected_time']=ext['corrected_time']+pd.Timedelta(days=3)
        ext['offset_minutes']=3*24*60
        with self.assertRaises(ValueError):prepare(ep,ext)
    def test_next_gap_excluded(self):
        ep,ext=self.base()
        ep=ep.drop(ep.index[2])
        test=prepare(ep,ext.iloc[:2])
        self.assertTrue(pd.isna(test.iloc[1].next1_dir))

if __name__=='__main__':unittest.main()
