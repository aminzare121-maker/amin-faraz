"""Synthetic, reproducible visual-only regression tests (no private video)."""
import unittest
import numpy as np
import cv2
from artin_9_chart_registration_v1 import register_chart_pair


def sample(seed=5):
    rng=np.random.default_rng(seed)
    frame=np.full((640,960,3),255,dtype=np.uint8)
    for x in range(120,760,37):cv2.line(frame,(x,190),(x,520),(229,229,229),1)
    for y in range(200,520,34):cv2.line(frame,(100,y),(770,y),(227,227,227),1)
    for x in range(150,760,13):
        y=int(rng.integers(220,500));wide=int(rng.integers(2,6))
        cv2.line(frame,(x,y-12),(x,y+17),(20,20,20),1)
        cv2.rectangle(frame,(x-wide,y-6),(x+wide,y+8), (30,110,60) if x%2 else (70,70,180),-1)
    return frame

class TestPureChartRegistration(unittest.TestCase):
    ROI=(100,190,770,525)
    def test_stable_chart_anchor(self):
        a=sample();result,_=register_chart_pair(a,a.copy(),self.ROI)
        self.assertEqual(result['status'],'CHART_FEATURES_ALIGNED_VIEWPORT_ONLY')
        self.assertLess(abs(result['translate_x_pixels']),1)
        self.assertLess(abs(result['translate_y_pixels']),1)
        self.assertFalse(result['same_trade_state_verified'])
    def test_correct_horizontal_vertical_view_shift(self):
        a=sample();m=np.float32([[1,0,-12],[0,1,-18]])
        b=cv2.warpAffine(a,m,(960,640),borderValue=(255,255,255))
        result,_=register_chart_pair(a,b,self.ROI)
        self.assertEqual(result['status'],'CHART_FEATURES_ALIGNED_VIEWPORT_ONLY')
        self.assertAlmostEqual(result['translate_x_pixels'],-12,delta=1.5)
        self.assertAlmostEqual(result['translate_y_pixels'],-18,delta=1.5)
        self.assertLess(result['changed_pixels_after_alignment_fraction'],result['changed_pixels_raw_fraction'])
    def test_overlay_changed_not_market_condition_certification(self):
        a=sample();b=a.copy();cv2.rectangle(b,(550,280),(610,400),(255,0,0),-1)
        result,_=register_chart_pair(a,b,self.ROI)
        self.assertEqual(result['status'],'CHART_FEATURES_ALIGNED_VIEWPORT_ONLY')
        self.assertGreater(result['changed_pixels_after_alignment_fraction'],0)
        self.assertFalse(result['teacher_semantics_verified'])
        self.assertFalse(result['same_trade_state_verified'])
        self.assertEqual(result['orders_authorized'],0)
    def test_blank_has_no_provable_anchor(self):
        blank=np.full((640,960,3),255,np.uint8)
        result,_=register_chart_pair(blank,blank,self.ROI)
        self.assertEqual(result['status'],'INCONCLUSIVE_UNDERLYING_CHART_MATCH')
    def test_mismatched_dimensions_refused(self):
        with self.assertRaises(ValueError):register_chart_pair(sample(),sample()[:400],self.ROI)
    def test_invalid_roi_refused(self):
        with self.assertRaises(ValueError):register_chart_pair(sample(),sample(),(0,0,30,20))
    def test_no_unearned_teacher_speech_claim(self):
        r,_=register_chart_pair(sample(),sample(),self.ROI)
        self.assertFalse(r['teacher_semantics_verified'])
        self.assertFalse(r['same_trade_state_verified'])
        self.assertEqual(r['orders_authorized'],0)
    def test_metadata_values_are_finite(self):
        r,_=register_chart_pair(sample(),sample(),self.ROI)
        for key in ['translate_x_pixels','translate_y_pixels','scale','median_inlier_reprojection_pixels','changed_pixels_raw_fraction','changed_pixels_after_alignment_fraction']:
            self.assertTrue(np.isfinite(r[key]),key)

if __name__=='__main__':unittest.main()