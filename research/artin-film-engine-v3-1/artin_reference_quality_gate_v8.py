#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent reference-based Persian text and critical-term quality gate.

A model's confidence is NOT independent accuracy. Only human-checked
source-media references may count. No trading/paper integration here.
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path

# Reversible material terms: mistranscribing them reverses market instructions.
CRITICAL_TERMS={'خرید','فروش','بای','سل','لانگ','شورت','استاپ','حد ضرر',
                'حد سود','نکن','نمی','باید','نباید','بالاتر','پایین‌تر',
                'بالاتر از','کمتر از','بیشتر از','برعکس','استثنا','صعودی','نزولی'}

def normal(text):
    if not isinstance(text,str):raise ValueError('Expected Persian textual evidence')
    v=unicodedata.normalize('NFKC',text)
    v=v.replace('ي','ی').replace('ك','ک').replace('\u200c',' ')
    v=re.sub(r'\s+',' ',v).strip()
    return v

def edit_distance(a,b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        cur=[i]
        for j,y in enumerate(b,1):
            cur.append(min(cur[j-1]+1,prev[j]+1,prev[j-1]+(x!=y)))
        prev=cur
    return prev[-1]

def measure_reference(refs,*,min_cases=30,max_cer=.02,max_wer=.05):
    if not isinstance(refs,list):raise ValueError('Reference batch must be list')
    if type(min_cases) is not int or min_cases<1:
        raise ValueError('Minimum cases must be positive')
    if not 0<=max_cer<=1 or not 0<=max_wer<=1:
        raise ValueError('Invalid quality thresholds')
    unique=set();chars=cherrs=words=werrs=0;terms_wrong=0;valid=0
    missing=[];details=[]
    for i,r in enumerate(refs):
        if not isinstance(r,dict):raise ValueError('Reference entry is not object')
        key=(r.get('source_video_sha256'),r.get('source_media_sha256'),
             r.get('source_timestamp_seconds'),r.get('channel'))
        if key in unique:raise ValueError('Duplicate reference media evidence')
        unique.add(key)
        for sha in key[:2]:
            if not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{64}',sha):
                raise ValueError('Source reference SHA256 is missing')
        if not isinstance(key[2],(float,int)) or key[2]<0:
            raise ValueError('Source reference time missing')
        if not isinstance(key[3],str) or key[3] not in ('chat','teacher_board','speech'):
            raise ValueError('Reference channel invalid')
        if (r.get('reference_checked_against_original') is not True or
            r.get('original_source_accessible') is not True or
            not isinstance(r.get('reviewer_id'),str) or
            not r.get('reviewer_id').strip()):
            missing.append(i)
            continue
        reference=normal(r.get('human_reference_text'))
        predicted=normal(r.get('predicted_text'))
        if not reference:raise ValueError('Empty human reference is not a gold label')
        if key[3]=='speech' and r.get('speaker_role_human_verified') is not True:
            missing.append(i)
            continue
        ed=edit_distance(reference,predicted)
        rt=reference.split()
        pt=predicted.split()
        wd=edit_distance(rt,pt)
        important=[t for t in CRITICAL_TERMS if t in reference or t in predicted]
        risky=any((t in reference)!=(t in predicted) for t in important)
        if risky:terms_wrong+=1
        chars+=len(reference);cherrs+=ed;words+=len(rt);werrs+=wd;valid+=1
        details.append({'id':i,'char_errors':ed,'word_errors':wd,
          'critical_semantic_term_disagreement':risky,
          'source_reference_checked':True})
    cer=cherrs/chars if chars else None
    wer=werrs/words if words else None
    ready=(valid>=min_cases and not missing and chars>0 and words>0 and
           cer<=max_cer and wer<=max_wer and terms_wrong==0)
    return {'schema':'artin_human_gold_quality_gate_v8',
        'total_entries':len(refs),'human_verified_source_items':valid,
        'unverified_items':len(missing),
        'min_required_human_verified_items':min_cases,
        'character_error_rate':round(cer,6) if cer is not None else None,
        'word_error_rate':round(wer,6) if wer is not None else None,
        'critical_term_mismatches':terms_wrong,
        'sample_passes_quality_gate':ready,
        'all_original_video_messages_verified':False,
        'all_teacher_strategy_rules_verified':False,
        'permission_to_trade':False,
        'status':'QUALITY_SAMPLE_PASS_ONLY_NOT_TRADE_APPROVAL' if ready else 'INSUFFICIENT_QUALITY_EVIDENCE',
        'per_item_private_details':details}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--references',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--minimum',type=int,default=30)
    args=a.parse_args()
    x=json.loads(args.references.read_text(encoding='utf8'))
    result=measure_reference(x,min_cases=args.minimum)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    (args.out/'reference_quality_PRIVATE.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    safe={k:v for k,v in result.items() if k!='per_item_private_details'}
    print('ARTIN_REFERENCE_QUALITY='+json.dumps(safe,ensure_ascii=False),flush=True)
    if not result['sample_passes_quality_gate']:
        raise SystemExit(2)

if __name__=='__main__':main()
