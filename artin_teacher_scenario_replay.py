#!/usr/bin/env python3
"""Safe, symbolic candidate replay for the user's privately archived Artin lessons.

Only works on *provisional* teacher examples. No market orders, no price feeds,
no teacher certification, and no fabricated fills. Every candidate is blocked
until original audio, speaker, and rule meanings have been independently checked.
"""
import argparse
import json
from pathlib import Path

DECISIONS = {'ENTER', 'EXIT', 'HOLD', 'NO_TRADE'}
KNOWN_SCENARIOS = {'CONCEPT', 'WEAK_TREND', 'BREAKOUT', 'PIERCING',
                   'STOP_LOCATION', 'TARGET2_RISKFREE', 'RR_ARITHMETIC'}


def evaluate(candidate, state):
    """Return a symbolic interpretation, NEVER an executable instruction."""
    if not isinstance(candidate, dict) or not isinstance(state, dict):
        raise TypeError('candidate and state must be objects')
    typ = candidate.get('scenario_type')
    if typ not in KNOWN_SCENARIOS:
        return {'interpretation': 'UNKNOWN_SCENARIO', 'trade_authorized': False}
    result = {'interpretation': 'NO_EXECUTABLE_STRATEGY_DEFINED', 'trade_authorized': False,
              'teacher_semantics_verified': False, 'engine_teacher_match_certified': False,
              'actual_trade_was_observed': False, 'scenario_type': typ,
              'rule_id': candidate.get('case_id')}
    # No inferred numeric thresholds: market state flags are symbolic placeholders.
    if typ == 'WEAK_TREND':
        result['interpretation'] = ('REVERSAL_AFTER_CORRECTION_CONCEPT' if
                                    state.get('trend_regime') == 'weak' else
                                    'NOT_APPLICABLE_TO_PRESENT_STATE')
        result['missing_to_execute'] = ['definition_of_weak_trend',
                                       'definition_of_correction',
                                       'actual_reversal_entry_conditions']
    elif typ == 'BREAKOUT':
        result['interpretation'] = ('PULLBACK_VS_IMMEDIATE_BRANCH_UNRESOLVED' if
                                    state.get('breakout_occurred') is True else
                                    'NO_BREAKOUT_ASSUMED')
        result['missing_to_execute'] = ['breakout_classification',
                                       'conditions_for_immediate_vs_pullback']
    elif typ == 'PIERCING':
        result['interpretation'] = ('CONDITIONAL_ENTRY_MENTIONED' if
                                    state.get('teacher_described_piercing') is True else
                                    'ENTRY_CONDITION_NOT_ESTABLISHED')
        result['missing_to_execute'] = ['precise_piercing_definition',
                                       'candle_reference', 'trade_direction',
                                       'stop', 'risk']
    elif typ == 'STOP_LOCATION':
        result['interpretation'] = ('STOP_NEAR_LIQUIDITY_PIVOT_CONCEPT' if
                                    state.get('liquidity_pivot_identified') is True else
                                    'PIVOT_NOT_IDENTIFIED')
        result['missing_to_execute'] = ['pivot_selection', 'buffer', 'risk_limit']
    elif typ == 'TARGET2_RISKFREE':
        result['interpretation'] = ('BREAK_EVEN_STOP_MOVE_ILLUSTRATION' if
                                    state.get('target2_reached') is True else
                                    'TARGET2_NOT_REACHED')
        result['missing_to_execute'] = ['is_example_applicable_to_this_trade',
                                       'commission_adjustment',
                                       'trigger_threshold', 'actual_stop_price']
    elif typ == 'RR_ARITHMETIC':
        risk, reward = state.get('risk'), state.get('reward')
        if type(risk) in (float, int) and type(reward) in (float, int) and risk > 0 and reward >= 0:
            result['illustrative_rr'] = reward / risk
            result['interpretation'] = 'REWARD_RISK_ARITHMETIC_ONLY'
        else:
            result['interpretation'] = 'NEED_VALID_NUMERIC_RISK_AND_REWARD'
        result['missing_to_execute'] = ['teacher_minimum_rr_policy_not_proven']
    return result


def compile_private_cases(cases_path):
    cases = json.loads(Path(cases_path).read_text(encoding='utf-8'))
    if len(cases) != 10 or len({x.get('case_id') for x in cases}) != 10:
        raise ValueError('exactly 10 distinct anchored candidate case IDs required')
    out = []
    for row in cases:
        for field in ('case_id', 'session', 'speech_start_seconds', 'source_audio_sha256',
                      'original_image_sha256', 'machine_quote'):
            if row.get(field) is None or row.get(field) == '':
                raise ValueError(f"{row.get('case_id')} missing {field}")
        if row.get('speaker_verified') is not False or row.get('teacher_semantics_verified') is not False:
            raise ValueError('unverified source cannot be labeled teacher-certified')
        if row.get('historical_order_proven') is not False:
            raise ValueError('teaching example is not proof of a historical order')
        out.append(dict(row, execution_authorized=False, reviewer_required=True,
                        status='PROVISIONAL_TEACHER_EXAMPLE',
                        replay=evaluate(row, row.get('symbolic_state', {}))))
    return {'schema': 'artin_teacher_scenario_replay_draft_v1',
            'cases': out, 'candidate_cases': 10,
            'source_status': 'MACHINE_SPEECH_ORIGINAL_IMAGE_UNVERIFIED_MEANING',
            'independent_teacher_meaning_verified': False,
            'engine_teacher_decision_verified': 0, 'trading_authorized': False,
            'note': 'Hypothetical conditions model possible real-market states. Each symbolic result is a provisional interpretation, not the teacher-certified algorithm.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('private_cases')
    p.add_argument('private_output')
    args = p.parse_args()
    result = compile_private_cases(args.private_cases)
    Path(args.private_output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'cases':len(result['cases']), 'real_teacher_rules_certified': 0,
                      'trading_authorized':False},ensure_ascii=False))
if __name__ == '__main__':
    main()