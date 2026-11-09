#!/usr/bin/env python3
"""Independent, fail-closed source-window coverage audit of 13 prior Artin entry IDs.

Purely measures whether archived ASR excerpts overlap the old engine's cited
classroom timestamps. It does NOT verify spoken meaning, determine speakers,
approve an entry method, place an order, or interpret the time of broker bars.
The original JSONL archives are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# Exact SOURCES mapping from research/artin-independent-engine/entry_engine.py
# on branch review/artin-m15-shadow-20261107, inspected 2026-11-10.
SOURCE_CITATIONS = {
    'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE': [(22, 1888.1, 1952.66)],
    'PULLBACK_STANDARD': [(16,615,854),(16,1003,1109)],
    'REVERSAL_CLASSIC': [(20,2188.86,2306.84),(20,2660.22,3255.4)],
    'REVERSAL_THREE': [(20,2660.22,3255.4),(20,3440.82,4048.72)],
    'REVERSAL_STAR': [(20,3440.82,4048.72),(20,4117.72,4483.72)],
    'BREAK_STRONG': [(21,2105.04,2261),(21,2274,2649.38)],
    'BREAK_WEAK_PIVOT': [(21,2770.48,3153.16)],
    'BREAK_WEAK_FULLBODY_EXCEPTION': [(21,2770.48,3153.16)],
    'BREAK_VERY_STRONG_RETEST': [(21,3162.56,3473.88)],
    'STOPPUNCH_SAME_COLOUR': [(21,3947,3975),(21,4201.30,4208.84),(21,4597,4661)],
    'STOPPUNCH_DOJI_AHEAD': [(21,3984.88,4068.98),(21,4210.14,4214.52)],
    'STOPPUNCH_DOJI_TIED': [(21,3984.88,4068.98),(21,4210.14,4214.52)],
    'STOPPUNCH_OPPOSITE_CONFIRMATION': [(21,4100,4133),(21,4214.52,4223.26),(23,4694,4728)],
}


def load_source(root: Path):
    sessions={}
    for n in range(1,26):
        path=root/f'session_{n:02d}_all_machine_speech_review.jsonl'
        if not path.is_file(): raise FileNotFoundError(str(path))
        rows=[]
        with path.open(encoding='utf-8') as h:
            for line in h:
                if line.strip():
                    r=json.loads(line)
                    if r.get('session') != n: raise ValueError(f'wrong session {n}')
                    a,b=r.get('start_seconds'),r.get('end_seconds')
                    if type(a) not in (int,float) or type(b) not in (int,float) or not 0<=a<=b:raise ValueError(f'bad time in {n}')
                    rows.append(r)
        if not rows: raise ValueError(f'empty speech inventory {n}')
        sessions[n]={'rows':rows,'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'first_observed_seconds':min(x['start_seconds'] for x in rows),
                     'last_observed_seconds':max(x['end_seconds'] for x in rows)}
    return sessions


def spans_union_duration(spans, lower, upper):
    intervals=sorted((max(lower,a),min(upper,b)) for a,b in spans if b>=lower and a<=upper)
    used=0.0;start=end=None
    for a,b in intervals:
        if start is None:start,end=a,b
        elif a<=end:end=max(end,b)
        else:used+=end-start;start,end=a,b
    return round(used+(end-start if start is not None else 0.0),3)


def inspect_window(sessions, lesson, start, end, include_private=False):
    if lesson not in sessions or not start<end:raise ValueError('invalid window')
    pack=sessions[lesson]
    rows=pack['rows']
    matches=[r for r in rows if r['end_seconds']>=start and r['start_seconds']<=end]
    boundaries=[x['start_seconds'] for x in rows]+[x['end_seconds'] for x in rows]
    nearest=min(rows,key=lambda r: min(abs(r['start_seconds']-start),abs(r['end_seconds']-end)))
    board=set();types={};verified_speaker=0;verified_meaning=0
    for r in matches:
        verified_speaker+=int(r.get('independent_speaker_and_wording_review_passed') is True)
        verified_meaning+=int(r.get('teacher_meaning_verified') is True)
        for v in r.get('visual_source_nearby',[]):
            if not isinstance(v,dict):continue
            kind=v.get('kind','unknown')
            types[kind]=types.get(kind,0)+1
            if kind=='board':board.add(v.get('frame_sha256'))
    covered=spans_union_duration([(r['start_seconds'],r['end_seconds']) for r in matches],start,end)
    frame_types={k:types[k] for k in sorted(types)}
    status=('BEYOND_LAST_SAMPLED_ASR' if start>pack['last_observed_seconds'] else
            'NO_ASR_IN_CITED_WINDOW' if not matches else
            'ASR_EXCERPTS_PRESENT_INCOMPLETE_REVIEW')
    result={
        'session':lesson,'start_seconds':start,'end_seconds':end,'window_seconds':round(end-start,3),
        'machine_transcript_overlap_rows':len(matches),
        'machine_transcript_union_seconds':covered,
        'machine_transcript_time_coverage_fraction':round(covered/(end-start),5),
        'visual_reference_kinds':frame_types,
        'unique_board_sha_references':len(board),
        'independent_speaker_wording_verified_rows':verified_speaker,
        'teacher_meaning_verified_rows':verified_meaning,
        'evidence_status':status,
        'teacher_semantics_certified':False,
        'source_file_sha256':pack['file_sha256'],
        'source_sampling_first_seconds':pack['first_observed_seconds'],
        'source_sampling_last_seconds':pack['last_observed_seconds'],
        'missing_asr_not_proof_of_missing_original_audio':True,
    }
    if include_private:
        result['matched_machine_asr_excerpts']=[{
            'record_id':r['record_id'],'start_seconds':r['start_seconds'],
            'end_seconds':r['end_seconds'],
            'machine_text_unverified':r['machine_text_unverified'],
            'source_segment_id':r.get('source_segment_id'),
            'audio_sha256_claim':r.get('source_audio_sha256')
        } for r in matches]
        if not matches:
            result['nearest_machine_asr_excerpt']={'start_seconds':nearest['start_seconds'],
                'end_seconds':nearest['end_seconds'],'text_unverified':nearest['machine_text_unverified']}
    return result


def audit(sessions, include_private=False):
    all_windows=[];rules=[]
    for rule,refs in SOURCE_CITATIONS.items():
        windows=[inspect_window(sessions,*ref,include_private=include_private) for ref in refs]
        present=sum(w['machine_transcript_overlap_rows']>0 for w in windows)
        verified=sum(w['teacher_meaning_verified_rows'] for w in windows)
        rules.append({'rule_id':rule,'citations':len(refs),'windows_with_asr_excerpt':present,
            'windows_without_asr_excerpt':len(refs)-present,
            'semantic_teacher_verified':False,
            'trade_ready':False,
            'source_windows':windows})
        all_windows+=windows
    return {'schema':'artin_original_teacher_13_entry_source_window_audit_v1',
        'derived_from':'entry_engine.SOURCES on review/artin-m15-shadow-20261107 and the private 25-session machine-ASR inventory',
        'entry_rule_ids':len(rules),
        'citation_windows_total':len(all_windows),
        'citation_windows_with_asr_excerpt':sum(w['machine_transcript_overlap_rows']>0 for w in all_windows),
        'citation_windows_without_asr_excerpt':sum(w['machine_transcript_overlap_rows']==0 for w in all_windows),
        'citation_windows_outside_last_speech_excerpt':sum(w['evidence_status']=='BEYOND_LAST_SAMPLED_ASR' for w in all_windows),
        'speaker_and_wording_independently_verified_source_windows':0,
        'teacher_trade_rules_semantically_certified':0,
        'motor_teacher_decisions_independently_compared':0,
        'real_m15_candles_available_separately':True,
        'm15_data_does_not_verify_teacher_entry_predicates':True,
        'trading_permitted':False,
        'source_rules':rules}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--private',action='store_true')
    a=parser.parse_args()
    report=audit(load_source(a.input),include_private=a.private)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_rules',)},ensure_ascii=False))
if __name__=='__main__':main()