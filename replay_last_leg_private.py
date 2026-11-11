"""Private OHLC replay; only aggregate, non-identifying output to publish."""
from __future__ import annotations
import hashlib,json,argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path
from artin_automatic_teacher_recognizer import Bar
from artin_teacher_last_leg_observer import LastLegObserver


def run(path):
    sha=hashlib.sha256()
    machine=LastLegObserver()
    counts=Counter()
    sides=Counter()
    comparisons=Counter()
    rows=0
    distinct=set()
    with Path(path).open('rb') as stream:
        for raw in stream:
            if not raw.strip():continue
            sha.update(raw)
            d=json.loads(raw)
            bar=Bar(int(d['raw_open_epoch_no_certified_utc_offset']),*(Decimal(str(d[k])) for k in ('open','high','low','close')))
            o=machine.step(bar);rows+=1
            counts[o['status']]+=1
            if o['gap_reset']:counts['gap_reset']+=1
            if o['candidate_leg']:
                leg=o['candidate_leg']; pair=(leg['begin_pivot_open_native'],leg['end_pivot_open_native'])
                distinct.add(pair)
                sides[leg['direction_candidate']]+=1
            if o['third_candle_half_comparison']:
                c=o['third_candle_half_comparison']
                comparisons['three_below_half']+=int(c['three_closes_all_below_candidate_half'])
                comparisons['three_above_half']+=int(c['three_closes_all_above_candidate_half'])
                comparisons['three_inside_candidate_range']+=int(c['three_closes_all_inside_candidate_range'])
                comparisons['three_compared']+=1
            assert o['trade_authorized'] is False
    return {'schema':'artin_s19_last_leg_private_replay_aggregate_v1',
            'source':'PRIVATE_CAPTURED_EPLANET_CANDLE_SET_NOT_INDEPENDENTLY_REVALIDATED_ON_TERMINAL',
            'source_sha256':sha.hexdigest(), 'rows':rows,
            'candidate_pivot_count':machine.pivots_detected,
            'ambiguous_middle_pivot_count':machine.ambiguous_centers,
            'discontinuity_resets':machine.gaps,
            'distinct_pivot_pair_candidates':len(distinct),
            'statuses':dict(counts),'directions_observed':dict(sides),
            'half_comparison':dict(comparisons),
            'teacher_last_leg_semantically_verified':False,
            'teacher_sentiment_verified':False,
            'teacher_entry_approved_count':0,
            'orders_submitted':0,
            'remarks':'Geometric measurements only; no PnL, broker fill or teacher-rule certification.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    d=run(a.input);Path(a.output).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:d[k] for k in ('rows','candidate_pivot_count','distinct_pivot_pair_candidates','discontinuity_resets','half_comparison','orders_submitted')},ensure_ascii=False))