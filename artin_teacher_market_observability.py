#!/usr/bin/env python3
"""Private teacher-source → real M15 *observability* bridge, NOT a trade engine.

Teacher speech remains unauthenticated machine ASR until original audio review.
A handwritten PDF is only a supplemental glossary. Two alternative meanings
of candle "body larger than shadows" are reported, neither is certified.

Reads the original owner-supplied M15 archive and exact 10 teaching candidates.
Exports no historical trades, entries, exits, TP, SL, win rate, or P&L.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from artin_real_m15_observation_replay import read_verified_bars
from artin_conditional_teacher_replay import SCENARIOS, recheck_source

CANDIDATE_CATEGORIES = {
    'A04-QUOTE-MECHANICS': ('BID_ASK_NOT_IN_BID_ONLY_M15', 'bid/ask tick series and original teacher words'),
    'A12-CANDLE-BODY': ('RAW_CANDLE_GEOMETRY_ALTERNATIVES', 'exact interpretation of each wick versus sum of wicks, plus teacher audio'),
    'A13-WEAK-TREND-REVERSE': ('WEAK_TREND_NOT_DEFINED', 'teacher-defined trend strength, reversal entry and timeframe'),
    'A14-TREND-TYPES': ('TREND_CLASSIFIER_NOT_DEFINED', 'teacher-defined up/down/range rule and timeframe'),
    'A15-BREAKOUT-VS-PULLBACK': ('ONLY_PREVIOUS_BAR_RELATIONS_AVAILABLE', 'teacher-specific breakout type, direction, pivot and pullback rule'),
    'A18-ENTRY-SCHEMATIC': ('TEACHER_CHART_REFERENCE_NOT_MAPPED_TO_BROKER_TIME', 'independently checked original chart context and entry rule'),
    'A19-PIERCING-EXAMPLE': ('PIERCING_NOT_DEFINED', 'which object is pierced, confirmation, direction and exceptions'),
    'A21-STOP-BEHIND-LIQUIDITY': ('LIQUIDITY_PIVOT_NOT_DEFINED', 'teacher-defined liquidity pivot, stop distance and position sizing'),
    'A24-RR-ARITHMETIC': ('ILLUSTRATION_NO_ORDER_SPECS', 'entry/SL/TP from the original lesson for each eligible order'),
    'A25-TARGET2-RISKFREE': ('TARGET2_NOT_DEFINED_FOR_MARKET_BAR', 'teacher target-two definition, move trigger, costs and SL location'),
}


def scan_market(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('verified M15 rows required')
    stats = Counter()
    samples = []
    month_counts = defaultdict(Counter)
    first_example = {}
    prior = None
    for i, row in enumerate(rows):
        if len(row) != 5:
            raise ValueError('expected OHLC tuple')
        t, o, h, l, c = row
        if (type(t) is not int or t % 900 or any(type(x) not in (int, float) or not math.isfinite(x) for x in (o, h, l, c))
                or not 0 < l <= min(o, c) <= max(o, c) <= h):
            raise ValueError('invalid verified OHLC source')
        if prior is not None and t <= prior[0]:
            raise ValueError('unsorted or duplicated market time')
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - l
        # The literal phrase in lesson 12 is AMBIGUOUS. Both hypotheses are
        # market observations at CANDLE CLOSE, never a trading criterion.
        body_over_each_wick = body > upper and body > lower
        body_over_combined_wicks = body > (upper + lower)
        if body_over_combined_wicks and not body_over_each_wick:
            raise AssertionError('logical body/wick relation violated')
        contiguous = prior is not None and t - prior[0] == 900
        raw_high_above_prev = h > prior[2] if contiguous else None
        raw_low_below_prev = l < prior[3] if contiguous else None
        # Do NOT classify this as a "breakout" or "piercing" in teacher terms.
        month = datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m')
        labels = {
            'body_gt_each_wick': body_over_each_wick,
            'body_gt_sum_wicks': body_over_combined_wicks,
            'two_body_readings_disagree': body_over_each_wick and not body_over_combined_wicks,
            'prior_bar_contiguous': contiguous,
            'raw_high_gt_previous_high': raw_high_above_prev is True,
            'raw_low_lt_previous_low': raw_low_below_prev is True,
            'follows_unclassified_gap': prior is not None and not contiguous,
        }
        for name, hit in labels.items():
            if hit:
                stats[name] += 1
                month_counts[month][name] += 1
                if (month, name) not in first_example:
                    first_example[month, name] = {
                        'raw_epoch_not_verified_broker_timezone': t,
                        'source_row_index': i,
                        'open': o, 'high': h, 'low': l, 'close': c,
                        'body': round(body, 8),
                        'upper_wick': round(upper, 8),
                        'lower_wick': round(lower, 8),
                        'prior_contiguous': contiguous,
                        'kind': name,
                        'trade_decision': None,
                        'teacher_decision_verified': False,
                    }
        stats['total_closed_candle_observations'] += 1
        month_counts[month]['total'] += 1
        prior = row
    for key in sorted(first_example):
        samples.append({'month_label_only_raw_epoch_utc_interpretation_unverified': key[0],
                        **first_example[key]})
    return dict(stats), {k: dict(v) for k, v in sorted(month_counts.items())}, samples


def bridge(source_zip, teacher_cases_path):
    rows, metadata, source_sha = read_verified_bars(source_zip)
    cases = json.loads(Path(teacher_cases_path).read_text(encoding='utf8'))
    if not isinstance(cases, list) or len(cases) != 10 or set(c.get('case_id') for c in cases) != set(SCENARIOS):
        raise ValueError('ten exact source-linked teacher candidates required')
    if len({c['case_id'] for c in cases}) != 10:
        raise ValueError('duplicate teacher candidate')
    indexes = []
    for c in sorted(cases, key=lambda e: e['session']):
        proof = recheck_source(c)
        cid = c['case_id']
        category, needed = CANDIDATE_CATEGORIES[cid]
        indexes.append({
            'teacher_case_id': cid, 'teacher_session': c['session'],
            'teacher_speech_seconds': c['speech_start_seconds'],
            'source_audio_sha256': c['source_audio_sha256'],
            'source_frame_sha256': c['original_image_sha256'],
            'machine_context_sha256': proof['anchor_text_sha256'],
            'observability_category': category,
            'missing_for_teacher_decision': needed,
            'is_hypothetical_teaching_case_allowed': True,
            'teacher_speech_independently_verified': False,
            'teacher_trade_rule_verified': False,
            'motor_teacher_match_verified': False,
            'real_or_demo_order_permitted': False,
            'same_market_event_as_teacher_video_claimed': False,
        })
    counts, monthly, examples = scan_market(rows)
    # Source hashes/counters must reflect the owner's original unmodified bundle.
    if metadata['source_rows'] != len(rows):
        raise ValueError('source row count mismatch')
    return {
        'schema': 'artin_m15_teacher_lesson_observability_v1',
        'source_archive_sha256': source_sha,
        'source_manifest_sha256_as_reported': metadata['source_manifest_sha256'],
        'teacher_source': 'PRIVATE_BEHROOZ_MACHINE_ASR_NOT_CERTIFIED',
        'teacher_pdf': 'REFERENCE_ONLY_NOT_TRADE_RULE',
        'm15_source_claim': metadata['source_claim'],
        'm15_rows_verified': len(rows),
        'bar_clock_meaning': 'raw broker epoch; not independently proven UTC over whole year',
        'observations_are_at_bar_close_only': True,
        'observations_use_future_candles': False,
        'market_observation_counts': counts,
        'per_month_observations': monthly,
        'selected_source_examples': examples,
        'teacher_candidates': indexes,
        'conditional_hypotheses_not_trading_rules': {
            'A12_CANDLE_BODY': ['body strictly larger than EACH wick', 'body strictly larger than SUM of wicks'],
            'A15_BREAKOUT': 'raw above previous high is NOT teacher-certified breakout',
        },
        'verified_teacher_trade_rules': 0,
        'validated_motor_vs_teacher_decisions': 0,
        'bar_events_classified_as_teacher_trades': 0,
        'executed_real_or_demo_orders': 0,
        'pnl': None,
        'win_rate': None,
        'actual_trade_backtest_performed': False,
        'reason_trade_backtest_blocked': 'original teacher audio not independently verified, no complete teacher-defined entry+stop+target+exceptions; bid/ask and historical costs unavailable',
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--eplanet',required=True,type=Path)
    parser.add_argument('--teacher-cases',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    report=bridge(args.eplanet,args.teacher_cases)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'real_bars':report['m15_rows_verified'],
                      'teacher_candidates':len(report['teacher_candidates']),
                      'ambiguous_body_readings_differ_at':report['market_observation_counts'].get('two_body_readings_disagree',0),
                      'certified_rules':0,'trades':0},ensure_ascii=False))

if __name__=='__main__':
    main()