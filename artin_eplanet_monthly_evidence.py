#!/usr/bin/env python3
"""Monthly visual review windows from original verified Eplanet M15 candle CSVs.

This is an offline *source browsing* sampler, not a signal or backtest. It
never labels teacher decisions; raw broker epoch remains unverified as UTC.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from artin_real_m15_observation_replay import read_verified_bars


def monthly_review(rows):
    if not rows:
        raise ValueError('No source candles')
    months=defaultdict(list)
    gaps=[]
    prev=None
    for idx,(t,o,h,l,c) in enumerate(rows):
        if t%900 or not 0<l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('Invalid or off-grid M15')
        if prev is not None and t<=prev[0]:
            raise ValueError('Repeated or disordered epoch')
        month=datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m')
        contiguous=prev is not None and t-prev[0]==900
        if prev is not None and not contiguous:
            gaps.append({'following_row_index':idx,'previous_raw_epoch':prev[0],
                         'next_raw_epoch':t,'calendar_slots_absent':(t-prev[0])//900-1})
        body=abs(c-o); span=h-l
        observation={
            'row_index':idx, 'raw_epoch_not_verified_utc':t,
            'open':o,'high':h,'low':l,'close':c,
            'body_abs':round(body,8),'range_abs':round(span,8),
            'upper_wick_abs':round(h-max(o,c),8),
            'lower_wick_abs':round(min(o,c)-l,8),
            'previous_m15_contiguous':contiguous,
            'high_above_previous_bar_high': bool(contiguous and h>prev[2]),
            'low_below_previous_bar_low': bool(contiguous and l<prev[3]),
            'outside_previous_bar': bool(contiguous and h>prev[2] and l<prev[3]),
            'inside_previous_bar': bool(contiguous and h<=prev[2] and l>=prev[3]),
            'follows_unclassified_gap':prev is not None and not contiguous,
            'technical_category_only_no_trade':True,
            'teacher_method_verified':False,
            'trade_action':None,
        }
        months[month].append(observation)
        prev=(t,o,h,l,c)
    report=[]; all_samples=[]
    for month,entries in sorted(months.items()):
        reasons={}
        def mark(row, label):
            if row is not None:
                reasons.setdefault(row['row_index'],set()).add(label)
        mark(entries[0],'first_in_month')
        mark(entries[-1],'last_in_month')
        # Monthly maxima are retrospective evidence review selections ONLY.
        mark(max(entries,key=lambda r:(r['body_abs'],-r['row_index'])),'retrospective_largest_candle_body')
        mark(max(entries,key=lambda r:(r['range_abs'],-r['row_index'])),'retrospective_largest_bar_range')
        for label,key in [('example_outside_previous_bar','outside_previous_bar'),
                          ('example_inside_previous_bar','inside_previous_bar'),
                          ('example_after_unclassified_gap','follows_unclassified_gap')]:
            mark(next((e for e in entries if e[key]),None),label)
        selected=[]
        for r in entries:
            if r['row_index'] in reasons:
                selected.append(dict(r,review_reasons=sorted(reasons[r['row_index']])))
        all_samples.extend(selected)
        counts=Counter()
        for e in entries:
            counts['bullish' if e['close']>e['open'] else 'bearish' if e['close']<e['open'] else 'flat']+=1
            for field in ['outside_previous_bar','inside_previous_bar','follows_unclassified_gap','high_above_previous_bar_high','low_below_previous_bar_low']:
                counts[field]+=bool(e[field])
        report.append({
            'month_label_derived_from_raw_epoch_UNVERIFIED_BROKER_TIMEZONE':month,
            'first_raw_epoch':entries[0]['raw_epoch_not_verified_utc'],
            'last_raw_epoch':entries[-1]['raw_epoch_not_verified_utc'],
            'bar_count':len(entries),
            'counts':dict(counts),
            'review_samples':selected,
        })
    return {'schema':'artin_eplanet_m15_monthly_observational_review_v1',
            'raw_time_mapping_broker_timezone_verified':False,
            'review_selection_has_hindsight':True,
            'all_ohlc_features_current_or_past_only':True,
            'market_gap_sessions_classified':False,
            'months_partial_edges_included':len(report),
            'total_real_bars':len(rows),
            'total_unclassified_gap_events':len(gaps),
            'total_missing_calendar_slots_unclassified':sum(g['calendar_slots_absent'] for g in gaps),
            'review_sample_count':len(all_samples),
            'months':report,
            'teacher_original_speech_verified':False,
            'teacher_rules_or_trading_signals_created':0,
            'orders_sent':0,
            'profit_result':None,
            'caution':'Only observed OHLC. A higher high or inside/outside previous bar is not the teacher entry strategy. Monthly highest-range selections are retrospective and cannot be used as predictive performance evidence.'}


def build(source_path,output_path):
    rows,manifest,source_sha=read_verified_bars(source_path)
    result=monthly_review(rows)
    result['original_source_archive_sha256']=source_sha
    result['source_manifest_sha256_as_reported']=manifest['source_manifest_sha256']
    result['real_source_20_chunk_hashes_passed']=manifest['source_chunks']==20
    if result['total_real_bars']!=manifest['source_rows'] or result['total_unclassified_gap_events']!=manifest['gap_events_unclassified']:
        raise ValueError('Real source manifest not reproduced')
    p=Path(output_path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--source',required=True)
    a.add_argument('--out',required=True)
    args=a.parse_args()
    r=build(args.source,args.out)
    print(json.dumps({'actual_bars':r['total_real_bars'],'months':len(r['months']),
                      'review_samples':r['review_sample_count'],'gap_events':r['total_unclassified_gap_events'],
                      'orders_sent':r['orders_sent']},ensure_ascii=False))