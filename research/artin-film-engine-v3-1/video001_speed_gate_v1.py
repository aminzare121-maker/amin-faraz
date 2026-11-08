"""Advisory-only faster-mode selector. Never changes V12 or source movie."""
from __future__ import annotations
import re
import statistics

SHA=re.compile(r'^[0-9a-f]{64}$')

def select_speed_mode(baseline,candidate,*,min_runs=3,min_speedup=.05,quality_audit=None):
    safe={'mode':'BASELINE_33_WORKERS','approved':False,
          'reason':'INSUFFICIENT_COMPARABLE_EVIDENCE','speedup_fraction':None}
    # No automatic mode switch based on speed alone. Independent accuracy
    # review MUST lift the consistency auditor's REVIEW_REQUIRED state.
    # The recorded real V1/V2 audit has changed OCR and polarity counts,
    # so this branch currently ALWAYS falls back to the unchanged baseline.
    if not isinstance(quality_audit,dict) or any([
        quality_audit.get('source_integrity_agrees') is not True,
        quality_audit.get('ocr_text_identical') is not True,
        quality_audit.get('all_asr_chunks_above_similarity_threshold') is not True,
        quality_audit.get('polarity_count_changed') is not False,
        quality_audit.get('independent_human_gold_accuracy_pass') is not True,
        quality_audit.get('needs_independent_human_gold_validation') is not False,
    ]):
        return {**safe,'reason':'QUALITY_NOT_INDEPENDENTLY_VERIFIED'}
    if (not isinstance(baseline,list) or not isinstance(candidate,list)
            or len(baseline)<min_runs or len(candidate)<min_runs
            or len(baseline)!=len(candidate) or min_runs<3 or min_speedup<.05):
        return safe
    keys=('source_video_sha256','hardware_id','asr_model','ocr_model',
          'source_evidence_digest','gold_reference_sha256')
    identity=None
    elapsed=[[],[]]
    for group,rows in enumerate((baseline,candidate)):
        for record in rows:
            if not isinstance(record,dict):return safe
            values=tuple(record.get(k) for k in keys)
            if identity is None:identity=values
            if values!=identity or any(not isinstance(x,str) or not x for x in values):
                return safe
            if any(not SHA.fullmatch(record[k]) for k in
                   ('source_video_sha256','source_evidence_digest','gold_reference_sha256')):
                return safe
            if (record.get('coverage_complete') is not True or
                record.get('source_evidence_loss')!=0 or
                record.get('original_video_unchanged') is not True or
                record.get('independently_human_reference_checked') is not True or
                not isinstance(record.get('gold_reference_count'),int) or
                record['gold_reference_count']<30 or
                record.get('gold_reference_count')!=baseline[0].get('gold_reference_count') or
                record.get('critical_semantic_mismatches')!=0):
                return safe
            for metric in ('speech_gold_wer','image_gold_cer'):
                val=record.get(metric)
                if type(val) not in (float,int) or not 0<=val<=1:return safe
                if group==1 and val>max(b[metric] for b in baseline):return safe
            seconds=record.get('total_seconds')
            if type(seconds) not in (int,float) or not 0<seconds<86400:return safe
            elapsed[group].append(seconds)
    original,fast=elapsed
    improvement=(statistics.median(original)-statistics.median(fast))/statistics.median(original)
    if max(fast)>=min(original) or improvement<min_speedup:
        return {**safe,'reason':'NO_REPRODUCIBLE_WALL_CLOCK_GAIN',
                'speedup_fraction':round(improvement,4)}
    return {'mode':'EXPERIMENTAL_FASTER_ELIGIBLE','approved':True,
            'reason':'SAME_SOURCE_PROVENANCE_HUMAN_GOLD_AND_REPEATABLE_SPEED_GAIN',
            'speedup_fraction':round(improvement,4)}
