#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-bound handwritten-board and typed-student-chat review.

Screenshots do not prove message creation time or who spoke the audio.
All visual-language-model transcriptions remain UNVERIFIED. Candidate
question / teacher answer links are a REVIEW QUEUE, never a trading rule.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import unicodedata

_ALLOWED_CHANNELS={'chat','board'}


def norm(s):
    return ' '.join(unicodedata.normalize('NFKC',s).replace('ي','ی').replace('ك','ک')
                    .replace('\u200c',' ').split())


def probable_question(text):
    text=norm(text)
    if '؟' in text or '?' in text:
        return True
    return bool(re.search(r'(?<!\w)(?:آیا|چرا|چطور|چگونه|کدام|چه زمانی|کی|چیه)(?!\w)',text))


def validate_visual_model_candidates(visual_index: dict, proposals: list[dict]):
    """Prevent ungrounded image labels and any false teacher/student attribution."""
    if not isinstance(visual_index,dict) or visual_index.get('schema')!='artin_classroom_visual_v6':
        raise ValueError('Visual timeline index missing')
    if not isinstance(proposals,list):
        raise ValueError('Model response must be list of observations')
    known={r['frame_id']:r for r in visual_index.get('rows',[])}
    seen=set();accepted=[]
    for i,p in enumerate(proposals):
        if not isinstance(p,dict):
            raise ValueError('Expected JSON object for visual candidate')
        frame_id=p.get('frame_id')
        channel=p.get('channel')
        if frame_id not in known or channel not in _ALLOWED_CHANNELS:
            raise ValueError('Candidate references unknown frame or channel')
        src=known[frame_id]
        if p.get('frame_sha256')!=src[channel]['sha256']:
            raise ValueError('Candidate references another or altered source image')
        if p.get('teacher_verified') is True or p.get('student_verified') is True:
            raise ValueError('Visual model cannot verify participant identity')
        if p.get('trade_ready') is True or p.get('rule_authorized') is True:
            raise ValueError('Visual model cannot authorize trade rules')
        text=p.get('visible_text_candidate')
        if not isinstance(text,str) or not text.strip() or len(text)>1200:
            raise ValueError('Visual candidate must be short text')
        confidence=p.get('legibility','UNKNOWN')
        if confidence not in ('LOW','MEDIUM','HIGH','UNKNOWN'):
            raise ValueError('Unknown image legibility')
        k=(frame_id,channel,norm(text))
        if k in seen:continue
        seen.add(k)
        key=f"{visual_index['source_video_sha256']}|{frame_id}|{channel}|{src[channel]['sha256']}|{norm(text)}"
        accepted.append({'id':'visual_'+hashlib.sha256(key.encode('utf8')).hexdigest()[:24],
            'frame_id':frame_id,'channel':channel,
            'frame_sha256':src[channel]['sha256'],
            'global_chunk':src['global_chunk'],
            'batch':src['batch'],'slot':src['slot'],
            'image_observed_at_seconds':src['time_seconds'],
            'message_sent_at_seconds':None,
            'visible_text_candidate':norm(text),
            'question_candidate':channel=='chat' and probable_question(text),
            'legibility_candidate':confidence,
            'speaker':'UNKNOWN','speaker_verified':False,
            'typed_account_identity_verified':False,
            'image_text_human_verified':False,
            'source_fully_read':False,
            'can_change_artin_engine':False})
    accepted.sort(key=lambda x:(x['image_observed_at_seconds'],x['id']))
    return {'schema':'artin_visual_chat_candidates_v6',
            'source_video_sha256':visual_index['source_video_sha256'],
            'candidate_count':len(accepted),
            'visual_language_model_results_verified':False,
            'speaker_identified':False,'trades_authorized':0,
            'candidates':accepted}


def reconcile_chat_asr(chat_candidates:dict, review:dict, max_after_seconds=300):
    """Pair screenshots with nearby speech for review, NEVER a proven Q&A."""
    if chat_candidates.get('schema')!='artin_visual_chat_candidates_v6' or \
            review.get('schema')!='artin_teacher_av_review_v5':
        raise ValueError('Both original source indexes are required')
    if chat_candidates.get('source_video_sha256')!=review.get('source_video_sha256'):
        raise ValueError('Visual and audio evidence belong to different videos')
    if type(max_after_seconds) is not int or not 15<=max_after_seconds<=600:
        raise ValueError('Invalid question/answer review window')
    audio=sorted(review.get('speech_lines',[]),key=lambda u:u['start'])
    questions=[]
    for q in chat_candidates.get('candidates',[]):
        if not q.get('question_candidate'):
            continue
        t=q['image_observed_at_seconds']
        # Timestamp is frame observation time, NOT chat-message send timestamp.
        # A message may already have been on-screen for minutes.
        nearby=[]
        for speech in audio:
            at=speech.get('start')
            if type(at) not in (int,float) or not math.isfinite(at):
                raise ValueError('Invalid audio time')
            if t-90 <= at <= t+max_after_seconds:
                nearby.append(speech)
        # Observation time is NOT message sent time. Taking the FIRST ten
        # statements from t-90 biases all candidates to old discussion.
        # Prefer temporally closest speech (regardless of whether just before
        # or after screenshot); retain chronological display of these ten.
        nearby.sort(key=lambda u:(abs(u['start']-t),u['start']<t,u['start']))
        chosen=sorted(nearby[:10],key=lambda u:u['start'])
        candidates=[{'speech_line_id':u['id'],
                  'spoken_at_seconds':u['start'],
                  'speaker_verified':False,
                  'candidate_answer_verified':False} for u in chosen]
        questions.append({'visual_question_id':q['id'],
            'question_image_sha256':q['frame_sha256'],
            'question_frame_observed_at_seconds':t,
            'actual_question_post_time_known':False,
            'possible_spoken_replies':candidates,
            'teacher_role_verified':False,
            'question_text_verified':False,
            'answer_verified':False,
            'requires_original_video_review':True,
            'can_change_artin_engine':False})
    return {'schema':'artin_multimodal_chat_audio_review_v6',
            'source_video_sha256':review['source_video_sha256'],
            'question_candidates':questions,
            'authoritative_teacher_answers':0,
            'executable_rules':0,
            'requires_human_source_review':True}
