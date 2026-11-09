"""Tests are code invariants + real Eplanet input tests where private data exists."""
import unittest
import tempfile
from pathlib import Path
from artin_13_real_m15_gap_audit import (REQUIRED, SOURCE_CITATIONS, source_identity_summary,
     pure_features,non_trade_readiness,requirements,run)

SOURCE=Path(__file__).resolve().parent.parent/'EPLANET_M15_FOR_ARTIN_PRIVATE_UPLOAD.zip'

class Pure(unittest.TestCase):
    def test_13_and_24_exact(self):
        self.assertEqual(len(REQUIRED),13)
        self.assertEqual(sum(map(len,SOURCE_CITATIONS.values())),24)
        self.assertEqual(set(REQUIRED),set(SOURCE_CITATIONS))
    def test_source_map_same_seconds(self):
        mapping=source_identity_summary()
        self.assertEqual(mapping['STOPPUNCH_SAME_COLOUR'][2]['current_queue_video'],20)
        self.assertEqual(mapping['STOPPUNCH_OPPOSITE_CONFIRMATION'][-1]['current_queue_video'],22)
    def test_each_route_denied_both_sides(self):
        for rule in REQUIRED:
            for side in ('BUY','SELL'):
                d=non_trade_readiness(rule,side)
                self.assertFalse(d['teacher_decision_certified'])
                self.assertFalse(d['broker_order_permitted'])
                self.assertFalse(d['backtest_trade_permitted'])
                self.assertIn('sentiment_permission',d['needed_predicates_from_legacy_engine'])
                self.assertIn('current_setup',d['needed_predicates_from_legacy_engine'])
    def test_complete_required_lists_no_fabricated_confidence(self):
        self.assertIn('reference_body_close',requirements('BREAK_VERY_STRONG_RETEST','BUY'))
        self.assertIn('day_analysis_state',requirements('STOPPUNCH_DOJI_TIED','BUY'))
        self.assertIn('three_same_direction_sequence',requirements('REVERSAL_THREE','BUY'))
    def test_sell_mapping_not_invented(self):
        self.assertIn('teacher_sell_geometry_not_independently_mapped',requirements('STOPPUNCH_DOJI_AHEAD','SELL'))
        self.assertIn('teacher_buy_geometry_not_independently_mapped',requirements('STOPPUNCH_S22_SELL_CONFIRMED_PAUSE','BUY'))
    def test_invalid_side(self):
        with self.assertRaises(ValueError):requirements('PULLBACK_STANDARD','BOTH')
    def test_invalid_rule(self):
        with self.assertRaises(KeyError):non_trade_readiness('INVENTED','BUY')
    def test_exact_shadows_no_approximate_tolerance(self):
        f=pure_features([(0,100,102,100,102)])
        self.assertTrue(f['exact_shadowless_nonflat_subset'])
        self.assertFalse(f['exact_zero_body_subset'])
        self.assertFalse(f['extracted_teacher_entry_signal'])
    def test_body_shadow_two_readings_disagree(self):
        f=pure_features([(0,100,105,97,104)])
        self.assertTrue(f['body_greater_than_both_shadows_separately'])
        self.assertFalse(f['body_greater_than_sum_of_shadows'])
    def test_exact_zero_body_not_teacher_doji(self):
        f=pure_features([(0,100,102,99,100)])
        self.assertTrue(f['exact_zero_body_subset'])
        self.assertFalse(f['extracted_teacher_entry_signal'])
    def test_three_bars_needs_contiguity(self):
        f=pure_features([(0,1,2,1,2),(900,2,3,2,3),(1800,3,4,3,4)])
        self.assertTrue(f['three_same_direction_raw_candidate'])
        g=pure_features([(0,1,2,1,2),(1800,2,3,2,3),(2700,3,4,3,4)])
        self.assertFalse(g['three_same_direction_raw_candidate'])
    def test_fvg_only_closed_three_contiguous(self):
        f=pure_features([(0,1,2,1,2),(900,2,3,2,3),(1800,4,5,3,5)])
        self.assertTrue(f['up_fvg_three_bar_raw_candidate'])
        g=pure_features([(0,1,2,1,2),(1800,2,3,2,3),(2700,4,5,3,5)])
        self.assertFalse(g['up_fvg_three_bar_raw_candidate'])
    def test_ohlc_validation_rejects_bad_high(self):
        with self.assertRaises(ValueError):pure_features([(0,100,100,99,101)])
    def test_time_of_current_close_not_future_close(self):
        f=pure_features([(900,1,2,1,2)])
        self.assertEqual(f['close_known_at_raw_epoch_plus_900'],1800)
    def test_report_protects_input(self):
        if not SOURCE.is_file():self.skipTest('private Eplanet original M15 absent')
        with self.assertRaises(ValueError):run(SOURCE,SOURCE)
    def test_report_end_to_end_real_private(self):
        if not SOURCE.is_file():self.skipTest('private Eplanet original M15 absent')
        with tempfile.TemporaryDirectory() as d:
            report=run(SOURCE,Path(d)/'report.json')
        self.assertEqual(report['legacy_rule_count'],13)
        self.assertEqual(report['source_m15_rows'],23643)
        self.assertEqual(report['m15_calendar_gaps_unclassified'],260)
        self.assertEqual(report['buy_sell_route_bar_pairs_audited_as_blocked'],13*2*23643)
        self.assertEqual(report['mt5_orders_sent'],0)
        self.assertFalse(report['trade_backtest_completed'])

if __name__=='__main__':unittest.main()