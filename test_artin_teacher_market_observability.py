import copy
import unittest
from pathlib import Path
from artin_teacher_market_observability import bridge, scan_market

ROOT=Path(__file__).resolve().parent
EPLANET=Path('/mnt/data/EPLANET_M15_FOR_ARTIN_PRIVATE_UPLOAD.zip')
TEACHERS=ROOT/'ARTIN_TEACHER_10_PROVISIONAL_DECISION_CASES_PRIVATE.json'

class PureObservations(unittest.TestCase):
    def test_body_vs_each_and_sum_are_distinct(self):
        rows=[(900,10.0,12.5,9.5,12.0)]
        stats,month,examples=scan_market(rows)
        self.assertEqual(stats['body_gt_each_wick'],1)
        self.assertEqual(stats['body_gt_sum_wicks'],1)
        self.assertEqual(stats.get('two_body_readings_disagree',0),0)
    def test_ambiguous_shadow_phrase_is_not_silently_resolved(self):
        # body=2, each wick=1.5; together=3: interpretations differ.
        s,_,_=scan_market([(900,10.,13.5,8.5,12.)])
        self.assertEqual(s['body_gt_each_wick'],1)
        self.assertEqual(s.get('body_gt_sum_wicks',0),0)
        self.assertEqual(s['two_body_readings_disagree'],1)
    def test_previous_bar_relation_needs_exact_contiguity(self):
        s,_,_=scan_market([(900,10.,11.,9.,10.),(1800,10.,12.,9.,11.),(5400,11.,20.,1.,13.)])
        self.assertEqual(s['prior_bar_contiguous'],1)
        self.assertEqual(s['raw_high_gt_previous_high'],1)
        self.assertEqual(s['follows_unclassified_gap'],1)
    def test_no_trade_decisions_in_observational_examples(self):
        _,_,e=scan_market([(900,10.,11.,9.,10.),(1800,10.,12.,9.,11.)])
        self.assertTrue(all(x['trade_decision'] is None and not x['teacher_decision_verified'] for x in e))
    def test_reject_bad_geometry(self):
        with self.assertRaisesRegex(ValueError,'invalid verified OHLC'):scan_market([(900,10.,9.,8.,9.)])
    def test_reject_time_reversal(self):
        with self.assertRaisesRegex(ValueError,'unsorted'):scan_market([(1800,10.,11.,9.,10.),(900,10.,11.,9.,10.)])
    def test_no_future_observation_at_first_bar(self):
        a,_,_=scan_market([(900,10.,11.,9.,10.),(1800,10.,12.,9.,11.)])
        self.assertEqual(a.get('raw_high_gt_previous_high',0),1)
        self.assertEqual(a['total_closed_candle_observations'],2)

@unittest.skipUnless(EPLANET.is_file() and TEACHERS.is_file(), 'Private original M15 and teacher archive unavailable on public GitHub Actions')
class PrivateOriginals(unittest.TestCase):
    def test_actual_eplanet_10_teaching_candidates_not_trading(self):
        r=bridge(EPLANET,TEACHERS)
        self.assertEqual(r['m15_rows_verified'],23643)
        self.assertEqual(len(r['teacher_candidates']),10)
        self.assertFalse(r['actual_trade_backtest_performed'])
        self.assertEqual(r['verified_teacher_trade_rules'],0)
        self.assertEqual(r['validated_motor_vs_teacher_decisions'],0)
        self.assertTrue(all(not x['real_or_demo_order_permitted'] for x in r['teacher_candidates']))
    def test_ohlc_hypotheses_are_different_and_not_teacher_rules(self):
        r=bridge(EPLANET,TEACHERS)
        self.assertGreater(r['market_observation_counts']['two_body_readings_disagree'],0)
        self.assertIn('A12_CANDLE_BODY',r['conditional_hypotheses_not_trading_rules'])
    def test_every_month_sample_preserves_provenance(self):
        r=bridge(EPLANET,TEACHERS)
        self.assertEqual(len(r['per_month_observations']),13)
        self.assertTrue(all(e['raw_epoch_not_verified_broker_timezone']%900==0 and e['trade_decision'] is None for e in r['selected_source_examples']))

if __name__=='__main__':unittest.main()