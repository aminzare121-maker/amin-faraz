"""Safety and liveness regressions for all 13 legacy Artin entry branches.

All positive cases are SYNTHETIC SOFTWARE FIXTURES, not teacher-certified rules,
not signals, not Eplanet historical backtests, and never broker orders. The
unchanged legacy source must be checked out at a pinned SHA by the runner.
"""
import os
from pathlib import Path
import sys
import unittest

ROOT = os.environ.get('ARTIN_PINNED_LEGACY_DIR')
if not ROOT or not Path(ROOT, 'entry_engine.py').is_file():
    raise RuntimeError('ARTIN_PINNED_LEGACY_DIR must point to checked-out legacy code')
sys.path.insert(0, str(Path(ROOT).resolve()))

from entry_engine import Engine, Fact, Observation, RULE_IDS, SOURCES
from examples import demo_document

SYNTHETIC = 'SYNTHETIC_REGRESSION_NOT_TEACHER_OR_PRICE_EVIDENCE'
RULE_SPECIFIC_MANDATORY = {
    'PULLBACK_STANDARD': 'retest_confirmed',
    'REVERSAL_CLASSIC': 'first_confidence_confirmed',
    'REVERSAL_THREE': 'half_leg_condition',
    'REVERSAL_STAR': 'body_penetration_condition',
    'BREAK_STRONG': 'fullbody_or_marubozu',
    'BREAK_WEAK_PIVOT': 'post_break_pivot_confirmed',
    'BREAK_WEAK_FULLBODY_EXCEPTION': 'fullbody_exception_context',
    'BREAK_VERY_STRONG_RETEST': 'not_chasing',
    'STOPPUNCH_SAME_COLOUR': 'same_colour_pause',
    'STOPPUNCH_DOJI_AHEAD': 'doji_candle_closed',
    'STOPPUNCH_DOJI_TIED': 'confirmation_timely',
    'STOPPUNCH_OPPOSITE_CONFIRMATION': 'complete_punch_sequence',
    'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE': 'pause_doubt_confirmed',
}


def fixture_cases():
    doc = demo_document()
    if doc.get('synthetic_only') is not True:
        raise ValueError('Uncertified test inputs must be marked synthetic')
    cases = doc['cases']
    if len(cases) != len(RULE_IDS) or set(c['rule_id'] for c in cases) != set(RULE_IDS):
        raise ValueError('A real legacy rule is missing a synthetic fixture')
    return cases


def evaluate_case(case):
    facts = {k: Fact(v['value'], v['known_at'], v['source']) for k,v in case['facts'].items()}
    return Engine('PINNED_OFFLINE_SYNTHETIC_ONLY', tuple(RULE_IDS)).evaluate(
        case['rule_id'], Observation(case['side'], case['at'], facts))


class LegacyThirteenEntryContractTests(unittest.TestCase):
    def test_13_distinct_rule_ids_and_one_fixture_each(self):
        self.assertEqual(len(RULE_IDS), 13)
        self.assertEqual(set(RULE_IDS), set(RULE_SPECIFIC_MANDATORY))
        self.assertEqual(len(fixture_cases()), 13)

    def test_pinned_source_directory_not_a_modified_clone(self):
        self.assertEqual(Path(sys.modules['entry_engine'].__file__).resolve(),
                         Path(ROOT, 'entry_engine.py').resolve())
        self.assertEqual(Path(sys.modules['examples'].__file__).resolve(),
                         Path(ROOT, 'examples.py').resolve())

    def test_synthetic_fixture_is_reachable_for_each_route(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                result = evaluate_case(case)
                self.assertEqual(result.status, 'ELIGIBLE', result.reasons)
                self.assertFalse(result.order_created)
                self.assertEqual(result.rule_id, case['rule_id'])
                self.assertTrue(result.sources)

    def test_missing_historical_sentiment_blocks_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['facts'].pop('sentiment_permission')
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REVIEW')
                self.assertIn('MISSING:sentiment_permission', result.reasons)
                self.assertFalse(result.order_created)

    def test_unknown_sentiment_not_automatically_two_sided(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['facts']['sentiment_permission']['value'] = 'UNKNOWN'
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REVIEW')
                self.assertFalse(result.order_created)

    def test_future_sentiment_information_blocks_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['facts']['sentiment_permission']['known_at'] = case['at']+1
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REVIEW')
                self.assertIn('FUTURE_INFORMATION:sentiment_permission', result.reasons)

    def test_missing_current_setup_blocks_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['facts'].pop('current_setup')
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REVIEW')
                self.assertIn('MISSING:current_setup', result.reasons)

    def test_false_current_setup_rejects_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['facts']['current_setup']['value'] = False
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REJECT')
                self.assertIn('HISTORICAL_SETUP_NOT_FRESH', result.reasons)

    def test_missing_specific_observation_blocks_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                key = RULE_SPECIFIC_MANDATORY[case['rule_id']]
                self.assertIn(key, case['facts'])
                case['facts'].pop(key)
                result = evaluate_case(case)
                self.assertNotEqual(result.status, 'ELIGIBLE')
                self.assertFalse(result.order_created)

    def test_future_specific_observation_blocks_all_13(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                key = RULE_SPECIFIC_MANDATORY[case['rule_id']]
                case['facts'][key]['known_at'] = case['at'] + 100
                result = evaluate_case(case)
                self.assertNotEqual(result.status, 'ELIGIBLE')
                self.assertFalse(result.order_created)

    def test_prohibited_opposite_economic_direction_rejected(self):
        for case in fixture_cases():
            with self.subTest(rule=case['rule_id']):
                case['side'] = 'SELL' if case['side']=='BUY' else 'BUY'
                result = evaluate_case(case)
                self.assertEqual(result.status, 'REJECT')
                self.assertIn('DIRECTION_NOT_PERMITTED', result.reasons)

    def test_source_references_are_declared_but_not_certified(self):
        for rule in RULE_IDS:
            with self.subTest(rule=rule):
                self.assertIn(rule, SOURCES)
                self.assertTrue(SOURCES[rule])
                for source in SOURCES[rule]:
                    self.assertEqual(len(source), 3)
                    self.assertLess(source[1], source[2])
                # These citations are legacy indices and require remapping before
                # they can be compared to the 25 current source videos.


if __name__ == '__main__':
    unittest.main(verbosity=2)