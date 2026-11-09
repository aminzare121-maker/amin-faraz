#!/usr/bin/env python3
"""Verify candidate teacher examples against ORIGINAL anchored machine rows and PNG bytes.

This proves integrity/proximity only, never correctness of teacher semantics or
motor decisions. Neither hypotheses nor symbolic examples are discarded.
Private data stays in the user's local/Library archives, not public GitHub.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

SHA = re.compile(r'^[0-9a-f]{64}$')

def valid_hash(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None

def image_path(images_root, case):
    requested = (images_root / case['original_image_path']).resolve()
    if not requested.is_relative_to(images_root.resolve()):
        return images_root / '__INVALID_OUTSIDE_IMAGES_ROOT__'
    if requested.is_file():
        return requested
    # Images imported from GitHub Actions retain their SHA, but some have a
    # renamed local basename. Trust only matching original bytes, never basename.
    fallback = images_root / f"session_{case['session']:02d}" / 'original_selected_board.png'
    return fallback if fallback.is_file() else requested

def audit(cases_path, index_root, images_root):
    cases = json.loads(Path(cases_path).read_text(encoding='utf-8'))
    if not isinstance(cases, list):
        raise ValueError('cases must be list')
    evidence_root = Path(index_root)
    images_root = Path(images_root)
    detail = []
    seen = set()
    for c in cases:
        case_id = c.get('case_id')
        n = c.get('session')
        errs=[]
        if case_id in seen or not case_id or type(n) is not int or not 1 <= n <=25:
            errs.append('BAD_OR_DUPLICATE_CASE_ID')
        seen.add(case_id)
        for k in ('source_audio_sha256','original_image_sha256'):
            if not valid_hash(c.get(k)):
                errs.append('INVALID_HASH:'+k)
        rows_path = evidence_root / f'session_{n:02d}_all_machine_speech_review.jsonl' if type(n) is int else evidence_root / 'INVALID'
        selected=[]
        if rows_path.is_file():
            for line in rows_path.read_text(encoding='utf-8').splitlines():
                if not line.strip():continue
                r=json.loads(line)
                if (abs(r.get('start_seconds',-999999)-c.get('speech_start_seconds',-1))<0.065
                        and r.get('machine_text_unverified')==c.get('machine_quote')
                        and r.get('source_audio_sha256')==c.get('source_audio_sha256')
                        and r.get('source_segment_id')==c.get('source_segment_id')):
                    selected.append(r)
        if len(selected)!=1:
            errs.append('NO_UNIQUE_EXACT_TIME_TEXT_AUDIO_SOURCE_MATCH')
        p=image_path(images_root,c) if type(n) is int and 1<=n<=25 else None
        actual = hashlib.sha256(p.read_bytes()).hexdigest() if p and p.is_file() else None
        if actual!=c.get('original_image_sha256'):
            errs.append('ORIGINAL_PNG_MISSING_OR_SHA_MISMATCH')
        linked=bool(selected) and any(v.get('frame_sha256')==c.get('original_image_sha256') for v in selected[0].get('visual_source_nearby',[]))
        if not linked:
            errs.append('FRAME_NOT_IN_NEARBY_SPEECH_VISUAL_REFERENCES')
        detail.append({'case_id':case_id, 'session':n,
                       'machine_speech_source_exact':len(selected)==1,
                       'image_original_bytes_sha256_match':actual==c.get('original_image_sha256'),
                       'same_segment_nearby_visual_hash_match':linked,
                       'source_integrity_issues':errs,
                       'semantic_meaning_verified':False,
                       'teacher_motor_decision_matched':False,
                       'trade_authorized':False,
                       'status':'EVIDENCE_SOURCE_LINKED_UNVERIFIED_MEANING' if not errs else 'EVIDENCE_REVIEW_REQUIRED'})
    return {'schema':'artin_10_candidate_provenance_v1', 'case_count':len(detail),
            'speech_exact_count':sum(x['machine_speech_source_exact'] for x in detail),
            'original_image_match_count':sum(x['image_original_bytes_sha256_match'] for x in detail),
            'same_segment_visual_count':sum(x['same_segment_nearby_visual_hash_match'] for x in detail),
            'source_integrity_unresolved_count':sum(bool(x['source_integrity_issues']) for x in detail),
            'items':detail,'teacher_semantics_certified':False,
            'mt5_trading_allowed':False,
            'meaning_limit':'ASR wording and speaker remain unverified; positional overlap is not teacher motor agreement'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--cases',type=Path,required=True)
    p.add_argument('--index-root',type=Path,required=True)
    p.add_argument('--images-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.cases,a.index_root,a.images_root)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k.endswith('_count')},ensure_ascii=False))
    # Source mismatch should be reported but not treated as erroneous teacher method.
    return 0 if result['speech_exact_count']==result['case_count'] and result['original_image_match_count']==result['case_count'] else 2

if __name__=='__main__':
    raise SystemExit(main())