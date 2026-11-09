"""Unit tests and optional actual original Eplanet private archive integration."""
import json
import tempfile
import unittest
from pathlib import Path
from artin_eplanet_monthly_evidence import monthly_review,build

PRIVATE=Path('/mnt/data/EPLANET_M15_FOR_ARTIN_PRIVATE_UPLOAD.zip')

class Rules(unittest.TestCase):
    def test_small_observations_no_signal(self):
        b=[(900,10,12,9,11),(1800,11,12.5,10,10.5),(2700,10.5,11,10,10.3)]
        out=monthly_review(b)
        self.assertEqual(out['total_real_bars'],3)
        self.assertEqual(out['total_unclassified_gap_events'],0)
        self.assertFalse(out['teacher_original_speech_verified'])
        self.assertEqual(out['teacher_rules_or_trading_signals_created'],0)
        self.assertTrue(all(s['trade_action'] is None for m in out['months'] for s in m['review_samples']))
    def test_gap_prevents_false_previous_candle_relation(self):
        b=[(900,10,12,9,11),(2700,10,14,8,12)]
        out=monthly_review(b)
        self.assertEqual(out['total_unclassified_gap_events'],1)
        self.assertEqual(out['total_missing_calendar_slots_unclassified'],1)
        sample=next(s for m in out['months'] for s in m['review_samples'] if s['row_index']==1)
        self.assertFalse(sample['outside_previous_bar'])
        self.assertFalse(sample['previous_m15_contiguous'])
    def test_no_future_price_leak_for_current_features(self):
        a=[(900,10,12,9,11),(1800,11,13,10,12)]
        b=a+[(2700,12,5000,1,15)]
        def get(result,idx):
            return next(s for m in result['months'] for s in m['review_samples'] if s['row_index']==idx)
        first=get(monthly_review(a),0);other=get(monthly_review(b),0)
        for k in ('body_abs','range_abs','upper_wick_abs','lower_wick_abs',
                  'high_above_previous_bar_high','outside_previous_bar'):
            self.assertEqual(first[k],other[k])
    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):monthly_review([])
        with self.assertRaises(ValueError):monthly_review([(901,10,11,9,10)])
        with self.assertRaises(ValueError):monthly_review([(900,10,11,9,10),(900,10,12,9,10)])

@unittest.skipUnless(PRIVATE.is_file(),'Original private M15 not available in public GitHub runner')
class ActualArchive(unittest.TestCase):
    def test_actual_25_months_not_invented(self):
        with tempfile.TemporaryDirectory() as folder:
            r=build(PRIVATE,Path(folder)/'actual.json')
            self.assertEqual(r['total_real_bars'],23643)
            self.assertEqual(r['total_unclassified_gap_events'],260)
            self.assertEqual(r['total_missing_calendar_slots_unclassified'],11397)
            self.assertEqual(len(r['months']),13)
            self.assertEqual(r['orders_sent'],0)
            self.assertIsNone(r['profit_result'])
            self.assertEqual(sum(m['bar_count'] for m in r['months']),23643)
            self.assertEqual(sum(m['counts']['follows_unclassified_gap'] for m in r['months']),260)
            self.assertTrue(all(len(m['review_samples'])<=7 for m in r['months']))
            data=json.loads((Path(folder)/'actual.json').read_text(encoding='utf-8'))
            self.assertEqual(data['original_source_archive_sha256'],r['original_source_archive_sha256'])
if __name__=='__main__':unittest.main()