#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-preserving Persian OCR question deduplication, not Q&A certification.

This tool consumes REVIEW_ONLY source-hashed evidence. It never deletes observations,
never attributes a candidate answer to an instructor, and never enables trading.
It safely clusters only nearby, very similar Persian chat observations; changing
trading intent or negation is a hard veto regardless of fuzzy text similarity.
"""
from __future__ import annotations
import argparse
from difflib import SequenceMatcher
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

SHA = re.compile(r'^[0-9a-f]{64}$')
SAFETY_WORDS=('خرید','فروش','بخر','نخر','بفروش','نفروش','نخرید','نفروشید',
              'باید','نباید','نکن','نکنید','نه','نیست','است','بالا','پایین',
              'بالاتر','پایینتر','حد ضرر','حد سود','مگر','فقط','بدون')

def normalize(value: str) -> str:
    if not isinstance(value,str): raise ValueError('Text is not a string')
    v=unicodedata.normalize('NFKC',value).replace('ي','ی').replace('ك','ک').replace('\u200c',' ')
    v=''.join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in v)
    v=re.sub(r'\s+',' ',v).strip()
    return v

def semantic_signature(value: str) -> tuple:
    """Exact safety-token presence; uncertain text remains separate rather than fusing."""
    t=normalize(value)
    neg_prefix=bool(re.search(r'(?<!\w)نمی(?=[آ-ی]|\s|$)',t))
    return (neg_prefix,tuple(term for term in SAFETY_WORDS
                 if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',t)))

def comparison_key(value: str) -> str:
    t=normalize(value)
    t=re.sub(r'^\s*\d{1,2}\s*[:：]\s*\d{2}\s*', '',t)
    return ''.join(ch for ch in t.lower() if ch.isalnum())

def clustered_review(review: dict, *, ratio:float=.95, gap_seconds:float=120.0) -> dict:
    if not isinstance(review,dict) or review.get('schema')!='artin_private_typed_chat_audio_candidates_v8':
        raise ValueError('Only original private OCR+ASR source review is accepted')
    sha=review.get('source_video_sha256')
    if not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise ValueError('Missing immutable original-video SHA256')
    groups=review.get('question_groups')
    if not isinstance(groups,list): raise ValueError('Missing original question observations')
    if not .8<=ratio<=1 or not 0<=gap_seconds<=1800:
        raise ValueError('Unsafe similarity settings')
    result=[]
    for original_index,x in sorted(enumerate(groups),key=lambda item:(item[1].get('first_seen',0),item[0])):
        if not isinstance(x,dict): raise ValueError('Invalid source question group')
        candidate=x.get('candidate_text')
        if not isinstance(candidate,str) or not candidate.strip():
            raise ValueError('Missing source OCR candidate text')
        start=x.get('first_seen'); end=x.get('last_seen'); refs=x.get('frame_sources')
        if (type(start) not in (int,float) or type(end) not in (int,float)
                or not math.isfinite(start) or not math.isfinite(end)
                or not 0<=start<=end or not isinstance(refs,list) or not refs):
            raise ValueError('Invalid source timestamps or frame evidence')
        for fr in refs:
            if (not isinstance(fr,dict) or not isinstance(fr.get('frame_id'),str)
                 or not isinstance(fr.get('chat_frame_sha256'),str)
                 or not SHA.fullmatch(fr['chat_frame_sha256'])
                 or type(fr.get('observed_at_seconds')) not in (int,float)
                 or not math.isfinite(fr['observed_at_seconds'])
                 or not 0<=fr['observed_at_seconds']):
                raise ValueError('Untraceable source frame; cannot dedupe')
        if x.get('teacher_answer_verified') is True or x.get('student_question_verified') is True:
            raise ValueError('Unverified OCR cannot assert teacher or student correctness')
        key=comparison_key(candidate)
        signature=semantic_signature(candidate)
        best=None; best_score=0
        for cluster in result:
            if start-cluster['latest_seen_seconds']>gap_seconds:
                continue
            for v in cluster['_variants']:
                if not key or len(key)<12 or len(v['key'])<12:
                    continue
                if signature!=v['safety_signature']:
                    continue
                score=SequenceMatcher(None,key,v['key'],autojunk=False).ratio()
                if score>=ratio and score>best_score:
                    best,best_score=cluster,score
        item={'original_index':original_index,'candidate_text':candidate,
              'first_seen_seconds':start,'last_seen_seconds':end,
              'original_frame_sources':refs,
              'provisional_nearby_speech':x.get('provisional_nearby_speech',[]),
              'teacher_answer_verified':False,'student_question_verified':False}
        if best is None:
            cid='qreview_'+hashlib.sha256((sha+'|'+str(original_index)+'|'+key).encode()).hexdigest()[:20]
            result.append({'review_id':cid,'first_seen_seconds':start,
                          'latest_seen_seconds':end,'member_groups':[item],
                          '_variants':[{'key':key,'safety_signature':signature}],
                          'review_required':True,'teacher_answer_verified':False,
                          'approved_trading_rule':False})
        else:
            best['latest_seen_seconds']=max(best['latest_seen_seconds'],end)
            best['member_groups'].append(item)
            best['_variants'].append({'key':key,'safety_signature':signature})
    for c in result:
        del c['_variants']
        c['member_groups_count']=len(c['member_groups'])
        c['original_chat_frame_observations']=sum(len(x['original_frame_sources']) for x in c['member_groups'])
    if sum(c['member_groups_count'] for c in result)!=len(groups):
        raise RuntimeError('Deduplication dropped source evidence')
    return {'schema':'artin_source_preserving_question_dedupe_v11',
            'source_video_sha256':sha,'original_review_groups':len(groups),
            'conservative_near_duplicate_clusters':len(result),
            'original_groups_not_lost':True,
            'similarity_ratio':ratio,'max_adjacency_gap_seconds':gap_seconds,
            'semantic_gold_accuracy_measured':False,
            'verified_teacher_answers':0,'verified_trading_rules':0,
            'status':'DEDUPLICATED_FOR_REVIEW_ONLY_NOT_TEACHER_VERIFIED',
            'review_clusters':result}

def main():
    p=argparse.ArgumentParser(description='Fail-closed Persian source question deduplication')
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    review=json.loads(a.review.read_text(encoding='utf8'))
    result=clustered_review(review)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    tmp=a.out.with_suffix(a.out.suffix+'.part')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    tmp.replace(a.out)
    print('VIDEO_QUESTION_DEDUP='+json.dumps({k:v for k,v in result.items() if k!='review_clusters'},ensure_ascii=False))

if __name__=='__main__': main()
