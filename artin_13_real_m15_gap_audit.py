#!/usr/bin/env python3
"""Offline 13-branch evidence/dependency audit on the owner's unchanged Eplanet M15.

NOT an expert advisor, teacher semantic verification, trade/backtest/P&L system.
Outputs raw bar observations and a source-indexed missing-predicate inventory;
never creates orders or labels raw patterns as teacher-approved entry signals.

Reproduces predicate *names*, not speculative values, from the legacy independent
engine's `raw_pipeline.REQUIRED` and `entry_engine.SOURCES` on branch
review/artin-m15-shadow-20261107.  The original branch is not modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Mapping

from artin_real_m15_observation_replay import read_verified_bars
from artin_13_source_coverage_audit import SOURCE_CITATIONS
from artin_legacy_identity_reconciliation import remap_citation, validate_shift

# Immutable ordered source-name transcription from old raw_pipeline.REQUIRED.
REQUIRED = {
 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE':('teacher_model_variant','strong_run_in_sentiment_direction','run_break_closed_at','confirmation_reference_kind','pause_opened_at','pause_closed_at','confirmation_opened_at','confirmation_closed_at','pause_body_close','pause_wick_low','break_before_pause','pause_doubt_confirmed','pause_in_run_direction','confirmation_in_run_direction','following_confirmation_closed','confirmation_timely','confirmation_close','teacher_confirmation_reference'),
 'PULLBACK_STANDARD':('break_occurred','post_break_pivot_confirmed','retest_confirmed','decision_candle_closed','decision_close','post_break_pivot_level'),
 'REVERSAL_CLASSIC':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','doubt_confirmed','first_confidence_confirmed'),
 'REVERSAL_THREE':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','three_same_direction_sequence','doubt_confidence_condition','half_leg_condition'),
 'REVERSAL_STAR':('zone_context','reversal_relative_to_last_leg','decision_candle_closed','star_sequence','body_penetration_condition','half_leg_condition'),
 'BREAK_STRONG':('break_strength','fullbody_or_marubozu','decision_candle_closed','level_kind','decision_close'),
 'BREAK_WEAK_PIVOT':('break_strength','pullback_confirmed','post_break_pivot_confirmed','decision_candle_closed','decision_close','post_break_pivot_level'),
 'BREAK_WEAK_FULLBODY_EXCEPTION':('break_strength','pullback_confirmed','fullbody_or_marubozu','fullbody_exception_context','decision_candle_closed'),
 'BREAK_VERY_STRONG_RETEST':('break_strength','not_chasing','reference_body_open','reference_body_close','retouch_low','retouch_high'),
 'STOPPUNCH_SAME_COLOUR':('strong_run_in_sentiment_direction','zone_context','same_colour_pause','pause_candle_closed'),
 'STOPPUNCH_DOJI_AHEAD':('strong_run_in_sentiment_direction','zone_context','doji_confirmed','day_analysis_state','doji_candle_closed'),
 'STOPPUNCH_DOJI_TIED':('strong_run_in_sentiment_direction','zone_context','doji_confirmed','day_analysis_state','following_confirmation_closed','confirmation_near','confirmation_timely','confirmation_close','doji_shadow_high'),
 'STOPPUNCH_OPPOSITE_CONFIRMATION':('strong_run_in_sentiment_direction','opposite_colour_pause','complete_punch_sequence','following_confirmation_closed','entry_location','confirmation_near','confirmation_timely','confirmation_close','teacher_confirmation_reference')
}

COMMON = ('sentiment_permission','current_setup')
FAMILY = ('family_selection_context','trend_strength')
# The old raw_pipeline derives some information with source-bound, non-OHLC
# context. This module counts only reproducible raw geometry, not these claims.
UNCONDITIONAL_PRICE_FACTS = ('decision_close','decision_candle_closed')
BODY_SHADOW_AMBIGUOUS = 'TEACHER_BODY_SHADOW_INTERPRETATION_UNRESOLVED'
STATIC_PIN_SHA = '2998d66f933f1edad4eccf7fb574b9f14007cf35'
# Strict observational SUBSETS only. None of these certifies the full teacher shape.
SHAPE_SUBSET_BY_ROUTE = {
 'BREAK_STRONG':'exact_shadowless_nonflat_subset',
 'BREAK_WEAK_FULLBODY_EXCEPTION':'exact_shadowless_nonflat_subset',
 'REVERSAL_THREE':'three_same_direction_raw_candidate',
 'STOPPUNCH_DOJI_AHEAD':'exact_zero_body_subset',
 'STOPPUNCH_DOJI_TIED':'exact_zero_body_subset',
}



def source_identity_summary():
    if set(SOURCE_CITATIONS) != set(REQUIRED) or len(REQUIRED)!=13:
        raise ValueError('legacy 13-entry manifest drift')
    if sum(map(len,SOURCE_CITATIONS.values()))!=24:
        raise ValueError('legacy citation count drift')
    if not validate_shift(-1)['all_25_mapped_without_duration_conflict']:
        raise ValueError('source identity mapping no longer fits originals')
    return {name:[{'original_engine_session':s, 'current_queue_video':remap_citation(s,a,b)[0],
                   'speech_start_seconds':a, 'speech_end_seconds':b,
                   'content_semantics_independently_verified':False}
                  for s,a,b in SOURCE_CITATIONS[name]] for name in REQUIRED}


def requirements(name:str, side:str):
    """List all branch dependencies in legacy engine; do not synthesize them."""
    if name not in REQUIRED:raise KeyError(name)
    if side not in ('BUY','SELL'):raise ValueError('BUY or SELL required')
    common=COMMON + (() if name.startswith('STOPPUNCH_') else FAMILY)
    keys=list(dict.fromkeys(common+REQUIRED[name]))
    if name=='BREAK_STRONG':
        # Reference geometry is an alternative, not a mandatory universal level.
        keys.append('zone_low_and_high_OR_line_level_after_level_kind')
    if name.startswith('REVERSAL_'):
        keys.append('teacher_prz_exception_if_strong_trend')
    if name.startswith('STOPPUNCH_') and name != 'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE' and side=='SELL':
        keys.append('teacher_sell_geometry_not_independently_mapped')
    if name=='STOPPUNCH_S22_SELL_CONFIRMED_PAUSE' and side=='BUY':
        keys.append('teacher_buy_geometry_not_independently_mapped')
    return tuple(keys)


def pure_features(three):
    """Only prices of *closed* preceding/current bars are supplied.

    Input [(epoch,o,h,l,c),...] ending in current bar. Does not know market
    sentiment, validated levels, strength, zones, stops, or teacher decisions.
    """
    if not three or len(three)>3:raise ValueError('1-3 closed M15 bars required')
    t,o,h,l,c=three[-1]
    if not (0<l<=min(o,c)<=max(o,c)<=h and t%900==0):
        raise ValueError('invalid closed M15 OHLC')
    n=len(three)
    # The causality of pattern relations ends at the last closed candle.
    prev=three[-2] if n>=2 and t-three[-2][0]==900 else None
    triple= n==3 and three[-2][0]-three[-3][0]==900 and t-three[-2][0]==900
    body=abs(c-o);upper=h-max(o,c);lower=min(o,c)-l
    raw={
       'body':round(body,10),'upper_shadow':round(upper,10),'lower_shadow':round(lower,10),
       'close_known_at_raw_epoch_plus_900':t+900,
       'candle_direction':'UP' if c>o else 'DOWN' if c<o else 'FLAT',
       'exact_shadowless_nonflat_subset':body>0 and upper==0 and lower==0,
       'exact_zero_body_subset':body==0,
       'body_greater_than_both_shadows_separately':body>max(upper,lower),
       'body_greater_than_sum_of_shadows':body>upper+lower,
       'previous_contiguous':bool(prev),
       'three_candles_contiguous':bool(triple),
       'three_same_direction_raw_candidate':False,
       'up_fvg_three_bar_raw_candidate':False,
       'down_fvg_three_bar_raw_candidate':False,
       'outside_previous_range_raw_candidate':False,
       'extracted_teacher_entry_signal':False,
       'trade_executed':False,
    }
    if prev:
        raw['outside_previous_range_raw_candidate']=h>prev[2] and l<prev[3]
    if triple:
        dirs=[('UP' if x[4]>x[1] else 'DOWN' if x[4]<x[1] else 'FLAT') for x in three]
        raw['three_same_direction_raw_candidate']=(dirs[0]!='FLAT' and dirs[0]==dirs[1]==dirs[2])
        raw['up_fvg_three_bar_raw_candidate']=three[-3][2]<l
        raw['down_fvg_three_bar_raw_candidate']=h<three[-3][3]
    return raw


def non_trade_readiness(name,side):
    """Fail-closed even if a caller claims arbitrary manual context.

    A true readiness decision requires a separate, independently authenticated
    teacher decision evidence system; that is not implemented in this script.
    """
    keys=requirements(name,side)
    return {'status':'BLOCKED_TEACHER_ENTRY_SEMANTICS_NOT_CERTIFIED',
            'needed_predicates_from_legacy_engine':list(keys),
            'unresolved_core_context':list(COMMON),
            'teacher_conditions_substituted_from_ohlc':[],
            'teacher_decision_certified':False,
            'broker_order_permitted':False,
            'backtest_trade_permitted':False}


def _digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(source:Path,report:Path):
    if report.resolve()==source.resolve():
        raise ValueError('source file is immutable')
    rows, manifest, zip_sha=read_verified_bars(source)
    provenance=source_identity_summary()
    counts=Counter()
    route_subsets=Counter()
    route_side_pairs_evaluated=0
    static_gates={(name,side):non_trade_readiness(name,side)
                  for name in REQUIRED for side in ('BUY','SELL')}
    for i,bar in enumerate(rows):
        feat=pure_features(rows[max(0,i-2):i+1])
        counts['bars_scanned']+=1
        for key in ('exact_shadowless_nonflat_subset','exact_zero_body_subset',
                   'body_greater_than_both_shadows_separately','body_greater_than_sum_of_shadows',
                   'previous_contiguous','three_candles_contiguous','three_same_direction_raw_candidate',
                   'up_fvg_three_bar_raw_candidate','down_fvg_three_bar_raw_candidate',
                   'outside_previous_range_raw_candidate'):
            counts[key]+=int(feat[key])
        if feat['body_greater_than_both_shadows_separately'] != feat['body_greater_than_sum_of_shadows']:
            counts['teacher_body_shadow_hypotheses_differ']+=1
        if i and bar[0]-rows[i-1][0]>900:counts['unclassified_time_gaps']+=1
        for name in REQUIRED:
            subset_key=SHAPE_SUBSET_BY_ROUTE.get(name)
            if subset_key is not None and feat[subset_key]:
                route_subsets[name]+=1
            for side in ('BUY','SELL'):
                gate=static_gates[name,side]
                if gate['status']!='BLOCKED_TEACHER_ENTRY_SEMANTICS_NOT_CERTIFIED':
                    raise AssertionError('evidence-free trade gate opened')
                route_side_pairs_evaluated+=1
        # All 13 routes and both sides are visited for each original closed candle.
        # Their global teacher-evidence gate remains blocked. No entry is inferred.
        # No order generation, future-bar data, or personalized signals.
    if route_side_pairs_evaluated!=len(rows)*len(REQUIRED)*2:
        raise AssertionError('route-side bar scan incomplete')
    by_rule=[]
    for name in REQUIRED:
        by_rule.append({
          'rule_id':name,
          'source_windows':provenance[name],
          'source_windows_count':len(provenance[name]),
          'required_conditions_buy':list(requirements(name,'BUY')),
          'required_conditions_sell':list(requirements(name,'SELL')),
          'raw_geometry_supported':list(UNCONDITIONAL_PRICE_FACTS),
          'raw_geometry_hypotheses_not_teacher_confirmed':[
              'exact_shadowless_nonflat_subset','exact_zero_body_subset',
              'three_same_direction_raw_candidate','up_fvg_three_bar_raw_candidate',
              'down_fvg_three_bar_raw_candidate'],
          'raw_shape_subset_name_not_full_teacher_condition':SHAPE_SUBSET_BY_ROUTE.get(name),
          'raw_shape_subset_matches_not_trade_signals':(route_subsets[name] if name in SHAPE_SUBSET_BY_ROUTE else None),
          'teacher_context_and_full_entry_rule_semantics_certified':False,
          'source_audio_hash_and_asr_24_of_24_available_for_review':True,
          'video_chart_referent_verified_for_all_window_examples':False,
          'status_buy':non_trade_readiness(name,'BUY')['status'],
          'status_sell':non_trade_readiness(name,'SELL')['status'],
          'eligible_market_trades':0,
          'teacher_behavior_verified':False})
    result={
      'schema':'artin_13_legacy_route_real_m15_readonly_gap_audit_v1',
      'data_source_archive_sha256':zip_sha,
      'source_manifest_broker_claim':manifest.get('source_claim'),
      'source_m15_rows':len(rows),
      'source_m15_chunks':manifest['source_chunks'],
      'm15_calendar_gaps_unclassified':counts['unclassified_time_gaps'],
      'assumed_broker_utc_offset':None,
      'engine_source_code_blob_sha256':STATIC_PIN_SHA,
      'source_citation_count':sum(map(len,SOURCE_CITATIONS.values())),
      'source_identity_remap':'legacy_session minus one; original lesson identity not fully cross-hash verified',
      'machine_asr_citations_available_for_review':24,
      'original_audio_sha_verified_for_all_24_citations':False,
      'teacher_original_audio_independently_listened_citations':0,
      'teacher_semantics_certified_rule_ids':[],
      'legacy_rule_count':len(REQUIRED),
      'buy_sell_route_bar_pairs_audited_as_blocked':route_side_pairs_evaluated,
      'measured_raw_market_fact_counts':dict(counts),
      'teacher_body_shadow_meaning':BODY_SHADOW_AMBIGUOUS,
      'route_specs':by_rule,
      'future_market_observations_used':False,
      'teacher_specific_stop_target_or_risk_params_inferred':False,
      'buy_signals_created':0,'sell_signals_created':0,'mt5_orders_sent':0,
      'trade_backtest_completed':False,'profit_loss_usd':None,
      'next_mandatory_step':'Independent original audio/chart referent review for each teacher predicate, then evidence-bound paper entry/SL/TP, then cost-aware broker-history replay.',
    }
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--eplanet',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();r=run(a.eplanet,a.out)
    print(json.dumps({k:r[k] for k in ('legacy_rule_count','source_m15_rows','buy_sell_route_bar_pairs_audited_as_blocked','mt5_orders_sent')},ensure_ascii=False))
if __name__=='__main__':main()