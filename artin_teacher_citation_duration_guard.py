#!/usr/bin/env python3
"""Fail-closed cross-registry time compatibility gate for old Artin entry citations.

This is *not* a new interpretation of the teacher's words. It compares the exact
source time intervals cited by an older independent engine to the 25 CURRENT
queue-video durations in tools-makhzan-hub COURSE_REGISTRY.json. IMPORTANT: the
older engine may have used different lesson numbering: its SOURCE_COVERAGE file
records eleven transcript chunks for legacy source 21 up to 6000 seconds, while
CURRENT queue video 21 lasts 3601 seconds. Time mismatch is evidence of an
UNRESOLVED source identity, not proof that a teacher claim is false.
Never remap to another video without source SHA proof.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from artin_13_source_coverage_audit import SOURCE_CITATIONS

REGISTRY_BLOB_SHA = '5dec2c82c4e2a895bd6f51744d8967b9911f342e'
LEGACY_ENGINE_BLOB_SHA = '2998d66f933f1edad4eccf7fb574b9f14007cf35'
REGISTRY_REF = 'tools-makhzan-hub:tools-makhzan/courses/artin/COURSE_REGISTRY.json'
ENGINE_REF = 'review/artin-m15-shadow-20261107:research/artin-independent-engine/entry_engine.py'
LEGACY_COVERAGE_BLOB_SHA = 'fa955ed57b8e4a2f64588dda0752909b6d8263d5'
# Recorded directly from the immutable registry blob above, not estimated from ASR.
VIDEO_DURATION_SECONDS = {
    1:4820.5452,2:5097.546304,3:5157.198367,4:4348.5768,
    5:4588.6346,6:4856.035556,7:4699.161542,8:5117.167166,
    9:4249.34458,10:3932.22966,11:1245.3854,12:4284.522812,
    13:4576.374422,14:3735.928163,15:3769.375389,16:3512.018141,
    17:4511.5758,18:4948.819933,19:4909.346067,20:6568.089252,
    21:3601.229206,22:4970.001,23:4201.697234,24:4154.073107,
    25:5181.068481,
}


def inspect_citation(lesson, start, end, durations=VIDEO_DURATION_SECONDS):
    if type(lesson) is not int or lesson not in durations:
        raise ValueError('Invalid lesson number or absent canonical source')
    if any(type(v) not in (int,float) for v in (start,end)) or not 0 <= start < end:
        raise ValueError('Invalid source interval')
    duration=durations[lesson]
    valid=end <= duration
    return {
        'session':lesson,'start_seconds':start,'end_seconds':end,
        'canonical_video_duration_seconds':duration,
        'citation_fits_current_queue_video_duration':valid,
        'seconds_start_after_current_queue_video_end':round(max(0, start-duration),3),
        'seconds_end_after_current_queue_video_end':round(max(0, end-duration),3),
        'evidence_status':'TIME_WITHIN_CURRENT_QUEUE_SLOT_SOURCE_IDENTITY_UNVERIFIED' if valid else 'INCOMPATIBLE_WITH_CURRENT_QUEUE_SLOT_UNRESOLVED_SOURCE_IDENTITY',
        'same_original_video_identity_verified':False,
    }


def audit(citations=SOURCE_CITATIONS,durations=VIDEO_DURATION_SECONDS):
    rules=[];windows=[]
    for rule_id,source_windows in citations.items():
        checked=[inspect_citation(*ref,durations=durations) for ref in source_windows]
        invalid=[v for v in checked if not v['citation_fits_current_queue_video_duration']]
        rules.append({
            'rule_id':rule_id,'citation_count':len(checked),
            'invalid_source_citation_count':len(invalid),
            'source_citation_gate':'BLOCKED_UNTIL_SOURCE_IDENTITY_MAPPED' if invalid else 'TIME_IN_BOUNDS_SOURCE_IDENTITY_NOT_PROVEN',
            'original_teacher_audio_verified':False,
            'method_backtest_permitted':False,
            'citations':checked,
        })
        windows.extend(checked)
    return {
        'schema':'artin_v13_cross_registry_source_identity_gate_v2',
        'provenance':{'registry':REGISTRY_REF,'registry_blob_sha':REGISTRY_BLOB_SHA,'older_engine':ENGINE_REF,'older_engine_blob_sha':LEGACY_ENGINE_BLOB_SHA,'older_source_coverage_blob_sha':LEGACY_COVERAGE_BLOB_SHA},
        'canonical_registered_video_count':len(durations),
        'old_engine_rule_count':len(rules),
        'old_engine_citation_count':len(windows),
        'citations_fit_current_queue_video_duration':sum(v['citation_fits_current_queue_video_duration'] for v in windows),
        'citations_beyond_current_queue_video_duration':sum(not v['citation_fits_current_queue_video_duration'] for v in windows),
        'rules_with_unmatched_time_in_current_queue':sum(r['invalid_source_citation_count']>0 for r in rules),
        'rules_requiring_source_identity_repair': [r['rule_id'] for r in rules if r['invalid_source_citation_count']>0],
        'source_mapping_repair_requires_exact_video_identity':True,
        'source_identity_mapping_verified_count':0,
        'older_and_current_lesson_numbering_may_differ':True,
        'legacy_source21_transcript_chunk_index_reaches_seconds':6000,
        'interpretation_warning':'Mismatch is between two registries; never claim original teacher footage is too short until exact original file hashes match.',
        'no_silent_reassignment_to_another_lesson':True,
        'valid_duration_does_not_imply_teacher_semantics_verified':True,
        'teacher_rules_certified':0,
        'teacher_engine_matches_independently_proven':0,
        'no_real_or_demo_orders':True,
        'replay_trade_and_profit_claims_permitted':False,
        'rules':rules,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    report=audit()
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rules'},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())