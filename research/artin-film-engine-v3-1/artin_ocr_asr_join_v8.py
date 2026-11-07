#!/usr/bin/env python3
"""Integrate source-hashed printed-chat OCR with actual time-linked speech.

All question-answer matches are review candidates; matching time is not
proof that a student asked or that teacher answered. No trades are allowed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from artin_student_chat_review_v6 import validate_visual_model_candidates,reconcile_chat_asr,norm


def join_original_chat_qa(visual_index,full_ocr,asr_review):
    if visual_index.get('schema')!='artin_classroom_visual_v6':
        raise ValueError('Authentic video screenshot timeline required')
    if full_ocr.get('schema')!='artin_full_original_chat_ocr_v7':
        raise ValueError('Authentic original screenshots OCR file required')
    if asr_review.get('schema')!='artin_teacher_av_review_v5':
        raise ValueError('Authentic source ASR required')
    source=visual_index['source_video_sha256']
    if full_ocr.get('source_video_sha256')!=source or asr_review.get('source_video_sha256')!=source:
        raise ValueError('OCR screenshot and original speech source SHA mismatch')
    rows=visual_index['rows']
    observed=full_ocr.get('results')
    if not isinstance(observed,list) or len(observed)!=len(rows):
        raise ValueError('Incomplete original video chat frames - do not claim coverage')
    if full_ocr.get('complete') is not True or full_ocr.get('frames_attempted')!=len(rows):
        raise ValueError('OCR run not fully completed')
    proposals=[]
    failed=[]
    seen=set()
    for frame,ocr in zip(rows,observed):
        if (ocr.get('frame_id')!=frame['frame_id'] or
            ocr.get('source_frame_sha256')!=frame['chat']['sha256'] or
            ocr.get('time_original_video_seconds')!=frame['time_seconds']):
            raise ValueError('OCR source screenshot ID/time/hash was relabeled')
        if frame['frame_id'] in seen:
            raise ValueError('Duplicated chat screen in OCR source')
        seen.add(frame['frame_id'])
        status=ocr.get('state')
        if status in ('OCR_FAILED_REVIEW_REQUIRED','OCR_NO_READABLE_TEXT'):
            failed.append({'frame_id':frame['frame_id'],'status':status})
            continue
        if status!='OCR_TEXT_CANDIDATES':
            raise ValueError('Unknown OCR source state')
        for item in ocr.get('possible_typed_questions',[]):
            text=item.get('possible_question_text')
            if not isinstance(text,str) or not text.strip():
                raise ValueError('OCR question is not source text')
            proposals.append({'frame_id':frame['frame_id'],'channel':'chat',
                'frame_sha256':frame['chat']['sha256'],
                'visible_text_candidate':text,'legibility':'UNKNOWN',
                'student_verified':False,'teacher_verified':False})
    sourced=validate_visual_model_candidates(visual_index,proposals)
    temporal=reconcile_chat_asr(sourced,asr_review)
    result=[]
    prior={}
    for x in temporal['question_candidates']:
        src=next(p for p in sourced['candidates'] if p['id']==x['visual_question_id'])
        sentence=norm(src['visible_text_candidate'])
        last=prior.get(sentence)
        # Multiple screenshot observations of same question within 120 seconds
        # are one review group but STILL not a verified student question.
        at=src['image_observed_at_seconds']
        if last is not None and at-last['last_seen']<=120:
            last['frame_sources'].append({'frame_id':src['frame_id'],
                            'chat_frame_sha256':src['frame_sha256'],
                            'observed_at_seconds':at})
            last['last_seen']=at
        else:
            group={'candidate_text':sentence,'first_seen':at,'last_seen':at,
               'question_post_time_known':False,
               'frames_observed':1,
               'frame_sources':[{'frame_id':src['frame_id'],
                            'chat_frame_sha256':src['frame_sha256'],
                            'observed_at_seconds':at}],
               'provisional_nearby_speech':x['possible_spoken_replies'],
               'speaker_role_verified':False,
               'teacher_answer_verified':False,
               'student_question_verified':False,
               'not_a_trading_rule':True,'status':'REVIEW_REQUIRED'}
            result.append(group)
            prior[sentence]=group
    for item in result:item['frames_observed']=len(item['frame_sources'])
    safe={'schema':'artin_original_typed_chat_speech_reconcile_v8',
         'source_video_sha256':source,
         'original_chat_frames':len(rows),
         'OCR_readable_frames':sum(o.get('state')=='OCR_TEXT_CANDIDATES' for o in observed),
         'OCR_failed_or_blank_frames':len(failed),
         'provisional_question_observations':len(temporal['question_candidates']),
         'provisional_distinct_question_groups':len(result),
         'verified_student_questions':0,
         'verified_teacher_answers':0,'verified_trading_rules':0,
         'can_execute':False,
         'status':'REVIEW_REQUIRED_NOT_FULL_TEACHER_UNDERSTANDING'}
    return safe,{'schema':'artin_private_typed_chat_audio_candidates_v8',
                  'source_video_sha256':source,
                  'question_groups':result,
                  'ocr_missing_or_failed':failed,
                  'all_teacher_answers_unverified':True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--images-index',type=Path,required=True)
    p.add_argument('--full-chat-ocr',type=Path,required=True)
    p.add_argument('--speech-review',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    v=json.loads(a.images_index.read_text(encoding='utf8'))
    o=json.loads(a.full_chat_ocr.read_text(encoding='utf8'))
    t=json.loads(a.speech_review.read_text(encoding='utf8'))
    safe,private=join_original_chat_qa(v,o,t)
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'qa_summary_safe.json').write_text(
       json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf8')
    (a.out/'qa_review_PRIVATE.json').write_text(
       json.dumps(private,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_SOURCE_CHAT_AUDIO_REVIEW='+json.dumps(safe,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
