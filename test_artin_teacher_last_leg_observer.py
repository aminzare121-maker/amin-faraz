"""Teacher S19 geometric last-leg evidence: causal, no auto trade approvals."""
import unittest
from decimal import Decimal as D
from artin_automatic_teacher_recognizer import Bar
from artin_teacher_last_leg_observer import LastLegObserver, observe_last_leg
from artin_teacher_13route_live_gate import review_closed_bars


def B(n, o, h, l, c):
    return Bar(n*900, D(str(o)), D(str(h)), D(str(l)), D(str(c)))


def sample_up_leg():
    return [
        B(0,100,101,95,99), B(1,99,100,90,95), B(2,95,99,93,97),
        B(3,97,105,96,102), B(4,102,110,99,108), B(5,108,108,100,101),
        B(6,101,107,99,104), B(7,104,106,98,103), B(8,103,105,97,102)]


class LastLegTests(unittest.TestCase):
    def test_last_opposite_pair_midpoint_and_closes_are_causal(self):
        rows=sample_up_leg()
        engine=LastLegObserver()
        before=[]
        for row in rows:
            before.append(engine.step(row))
        self.assertIsNone(before[4]['candidate_leg'])
        self.assertEqual(before[5]['candidate_leg']['midpoint'],'100')
        self.assertEqual(before[5]['candidate_leg']['direction_candidate'],'UP')
        self.assertEqual(before[5]['candidate_leg']['end_pivot_confirmed_native'],5400)
        self.assertIsNone(before[7]['third_candle_half_comparison'])
        comparison=before[8]['third_candle_half_comparison']
        self.assertTrue(comparison['three_closes_all_above_candidate_half'])
        self.assertFalse(comparison['three_closes_all_below_candidate_half'])
        self.assertEqual(comparison['open_times_native'],[5400,6300,7200])
        self.assertEqual(before[8]['known_at_native'],8100)
        self.assertFalse(before[8]['teacher_last_leg_selected'])
        self.assertFalse(before[8]['trade_authorized'])
        self.assertEqual(len(before[8]['observation_sha256']),64)

    def test_live_gate_emits_measured_lag_as_unapproved_context(self):
        r=review_closed_bars(sample_up_leg())
        self.assertEqual(r['decisions_checked'],26)
        leg=r['automatic_last_leg']
        self.assertEqual(leg['candidate_leg']['midpoint'],'100')
        self.assertTrue(leg['third_candle_half_comparison']['three_closes_all_above_candidate_half'])
        self.assertFalse(leg['teacher_last_leg_selected'])
        self.assertFalse(r['broker_orders_authorized'])
        self.assertFalse(r['video_teacher_semantics_independently_approved'])

    def test_gap_resets_pivots_so_stale_legs_cannot_signal(self):
        engine=LastLegObserver()
        for bar in sample_up_leg():engine.step(bar)
        z=engine.step(B(11,103,105,100,104))
        self.assertTrue(z['gap_reset'])
        self.assertIsNone(z['candidate_leg'])
        self.assertEqual(z['gaps_reset'],1)
        self.assertFalse(z['trade_authorized'])

    def test_ambiguous_engulfing_middle_is_not_pivot(self):
        eng=[B(0,100,103,97,101),B(1,101,107,90,104),B(2,104,105,95,103)]
        result=observe_last_leg(eng)
        self.assertEqual(result['ambiguous_pivot_centers'],1)
        self.assertEqual(result['pivots_detected'],0)
        self.assertIsNone(result['candidate_leg'])

    def test_same_side_double_pivot_does_not_forge_direction(self):
        bars=[B(0,100,102,98,101),B(1,101,105,100,104),B(2,104,104,102,103),
              B(3,103,108,103,107),B(4,107,107,102,104)]
        # Both pivots are high candidates, with no valid intervening low pivot.
        result=observe_last_leg(bars)
        self.assertIn(result['status'],('TWO_LAST_PIVOTS_SAME_KIND_NOT_A_SELECTED_LEG','NO_COMPLETED_ALTERNATING_PIVOT_PAIR'))
        self.assertFalse(result['trade_authorized'])

    def test_duplicate_reverse_and_invalid_bars_fail(self):
        engine=LastLegObserver()
        engine.step(B(0,100,105,95,102))
        with self.assertRaises(ValueError):engine.step(B(0,100,105,95,102))
        with self.assertRaises(ValueError):B(-1,100,105,95,102)
        with self.assertRaises(ValueError):engine.step(object())

    def test_flat_market_has_no_pivot_or_trade(self):
        rows=[B(i,100,101,99,100) for i in range(8)]
        r=observe_last_leg(rows)
        self.assertIsNone(r['candidate_leg'])
        self.assertFalse(r['trade_authorized'])

    def test_deterministic_evidence_hash(self):
        a=observe_last_leg(sample_up_leg())
        b=observe_last_leg(sample_up_leg())
        self.assertEqual(a['observation_sha256'],b['observation_sha256'])
        self.assertEqual(a['candidate_leg'],b['candidate_leg'])

if __name__=='__main__':unittest.main()