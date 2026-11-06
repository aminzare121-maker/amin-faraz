"""Independent source-condition review, entirely synthetic annotations."""
import ast
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
import unittest
from entry_engine import Engine, Fact, Observation, RULE_IDS


def observation(side='BUY', future=None, **facts):
    values = {'sentiment_permission': 'LONG_ONLY' if side == 'BUY' else 'SHORT_ONLY',
              'current_setup': True}
    values.update(facts)
    return Observation(side, 100, {key: Fact(value, 101 if key == future else 99, 'SYNTHETIC_REVIEW')
                                   for key, value in values.items()})


class EntryReviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine('SYNTHETIC_FIXED_PLAN', RULE_IDS)

    def same_colour(self, **changes):
        values = dict(strong_run_in_sentiment_direction=True, zone_context=True,
                      same_colour_pause=True, pause_candle_closed=True)
        values.update(changes)
        return values

    def doji(self, tied=False, **changes):
        values = dict(strong_run_in_sentiment_direction=True, zone_context=True, doji_confirmed=True,
                      day_analysis_state='TIED_BY_COUNT' if tied else 'AHEAD_BY_COUNT', doji_candle_closed=True)
        if tied:
            values.update(following_confirmation_closed=True, confirmation_near=True,
                          confirmation_timely=True, confirmation_close=Decimal('102'), doji_shadow_high=101)
        values.update(changes)
        return values

    def test_future_required_fact_is_review(self):
        result = self.engine.evaluate('STOPPUNCH_SAME_COLOUR', observation(future='same_colour_pause', **self.same_colour()))
        self.assertEqual(result.status, 'REVIEW')
        self.assertEqual(result.reasons, ('FUTURE_INFORMATION:same_colour_pause',))

    def test_same_colour_own_close_no_extra_confirmation_or_trend_gate(self):
        result = self.engine.evaluate('STOPPUNCH_SAME_COLOUR', observation(**self.same_colour()))
        self.assertEqual(result.status, 'ELIGIBLE')
        self.assertFalse(result.order_created)
        self.assertEqual(self.engine.evaluate('STOPPUNCH_SAME_COLOUR', observation(**self.same_colour(pause_candle_closed=False))).status, 'WAIT')

    def test_doji_ahead_count_not_money_and_unextracted_day(self):
        self.assertEqual(self.engine.evaluate('STOPPUNCH_DOJI_AHEAD', observation(**self.doji())).status, 'ELIGIBLE')
        values = self.doji(); del values['day_analysis_state']; values['dollar_pnl'] = 50
        self.assertEqual(self.engine.evaluate('STOPPUNCH_DOJI_AHEAD', observation(**values)).status, 'REVIEW')
        for state in ('START_OF_DAY', 'BEHIND_BY_COUNT'):
            result = self.engine.evaluate('STOPPUNCH_DOJI_AHEAD', observation(**self.doji(day_analysis_state=state)))
            self.assertEqual(result.status, 'REVIEW')
            self.assertIn('NOT_A_TEACHER_VETO', result.reasons[0])

    def test_tied_doji_requires_strict_shadow_cross_and_near(self):
        for changes, expected in (({}, 'ELIGIBLE'), ({'confirmation_close':101}, 'WAIT'),
                                  ({'following_confirmation_closed':False}, 'WAIT'), ({'confirmation_near':False}, 'REJECT')):
            self.assertEqual(self.engine.evaluate('STOPPUNCH_DOJI_TIED', observation(**self.doji(True, **changes))).status, expected)

    def test_opposite_form_between_preexisting_zones_conditional(self):
        values = dict(strong_run_in_sentiment_direction=True, opposite_colour_pause=True,
                      complete_punch_sequence=True, following_confirmation_closed=True,
                      entry_location='BETWEEN_PREEXISTING_ZONES', confirmation_near=True,
                      confirmation_timely=True, confirmation_close=102, teacher_confirmation_reference=101)
        self.assertEqual(self.engine.evaluate('STOPPUNCH_OPPOSITE_CONFIRMATION', observation(**values)).status, 'ELIGIBLE')
        values['complete_punch_sequence'] = False
        self.assertEqual(self.engine.evaluate('STOPPUNCH_OPPOSITE_CONFIRMATION', observation(**values)).status, 'WAIT')

    def test_weak_fullbody_exception_does_not_require_pivot_cross(self):
        values = dict(family_selection_context='TRENDLINE_ONLY', trend_strength='NORMAL',
                      break_strength='WEAK', pullback_confirmed=True, fullbody_or_marubozu=True,
                      fullbody_exception_context=True, decision_candle_closed=True)
        self.assertEqual(self.engine.evaluate('BREAK_WEAK_FULLBODY_EXCEPTION', observation(**values)).status, 'ELIGIBLE')

    def test_very_strong_half_body_touch_without_closed_candle(self):
        values = dict(family_selection_context='TRENDLINE_ONLY', trend_strength='STRONG',
                      break_strength='VERY_STRONG', not_chasing=True, reference_body_open=100,
                      reference_body_close=104, retouch_low=Decimal('101.9'), retouch_high=102)
        self.assertEqual(self.engine.evaluate('BREAK_VERY_STRONG_RETEST', observation(**values)).status, 'ELIGIBLE')
        values['retouch_high'] = Decimal('101.99')
        self.assertEqual(self.engine.evaluate('BREAK_VERY_STRONG_RETEST', observation(**values)).status, 'WAIT')

    def test_strong_trend_prz_exception_with_source_trace(self):
        values = dict(family_selection_context='ZONE_CONTEXT', trend_strength='STRONG',
                      teacher_prz_exception_confirmed=True, zone_context=True,
                      reversal_relative_to_last_leg=True, decision_candle_closed=True,
                      doubt_confirmed=True, first_confidence_confirmed=True)
        result = self.engine.evaluate('REVERSAL_CLASSIC', observation(**values))
        self.assertEqual(result.status, 'ELIGIBLE')
        self.assertIn((15, 3443, 3512), result.sources)
        values['teacher_prz_exception_confirmed'] = False
        self.assertEqual(self.engine.evaluate('REVERSAL_CLASSIC', observation(**values)).status, 'REJECT')

    def test_sell_stoppunch_is_review_not_unproven_mirror(self):
        result = self.engine.evaluate('STOPPUNCH_SAME_COLOUR', observation(side='SELL', **self.same_colour()))
        self.assertEqual(result.status, 'REVIEW')
        self.assertEqual(result.reasons, ('SELL_FORM_MAPPING_NOT_ESTABLISHED_IN_REVIEWED_EXAMPLES',))

    def test_zone_far_edge_immutable_trace_and_isolated_imports(self):
        values = dict(family_selection_context='ZONE_CONTEXT', trend_strength='STRONG', break_strength='STRONG',
                      fullbody_or_marubozu=True, decision_candle_closed=True, level_kind='FVG',
                      zone_low=100, zone_high=102, decision_close=101)
        first = observation(**values)
        self.assertEqual(self.engine.evaluate('BREAK_STRONG', first).status, 'WAIT')
        values['decision_close'] = 103
        second = observation(**values)
        a, b = self.engine.evaluate('BREAK_STRONG', second), self.engine.evaluate('BREAK_STRONG', second)
        self.assertEqual(a.status, 'ELIGIBLE'); self.assertEqual(a.input_fingerprint, b.input_fingerprint)
        with self.assertRaises(TypeError):
            second.facts['zone_low'] = Fact(99, 99, 'SYNTHETIC')
        with self.assertRaises(FrozenInstanceError):
            self.engine.plan_id = 'CHANGED'
        with self.assertRaises(ValueError):
            Fact(1.5, 99, 'SYNTHETIC')
        tree = ast.parse(Path(__file__).with_name('entry_engine.py').read_text(encoding='utf-8'))
        modules = {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        modules.update(alias.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names)
        self.assertLessEqual(modules, {'dataclasses','decimal','hashlib','json','types','typing'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
