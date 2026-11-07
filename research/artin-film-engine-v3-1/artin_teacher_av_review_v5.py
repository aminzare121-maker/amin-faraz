#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a conservative, source-linked review pack from REAL ASR and image evidence.

Never infer teacher/student identity, teacher authority, an executable trading
rule, or a chart claim solely from speech recognition or model captions.
This module deliberately emits candidates and review queues, not trade orders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from artin_fast_av_v4 import validate_fast
from artin_teacher_evidence_v4 import linked_qa_candidates, TRADING_MARKERS
from artin_semantic_context import noise_risk

_CORRECTION_WORDS=('اصلاح','اشتباه گفتم','اشتباه کرد','درستش','برعکس',
                   'در واقع','منظورم','باید بگم','گفتم که نه')
_HEX_SHA=re.compile(r'^[a-f0-9]{64}$')
_TRADE_ACTION=('خرید','فروش','ورود','خروج','حد ضرر','حد سود','استاپ',
               'تارگت','سیگنال','پوزیشن','معامله نکن','بای','سل')
_RULE_CONTEXT=('اگر','وقتی','باید','نباید','به شرط','زمانی که',
               'بعد از','قبل از','در صورتی','تنها اگر','بر اساس','نمی گیریم')


def _exact_hash(s):
    return isinstance(s,str) and bool(_HEX_SHA.fullmatch(s))


def _normalize(s):
    return ' '.join(s.replace('ي','ی').replace('ك','ک').replace('\u200c',' ').split())


def review_real_asr(manifest: dict, shards: list[dict],
                    visual_notes: list[dict] | None = None):
    """Check every timestamp/hash against extracted media; unverified source only.

    Transcript shards must carry exact source-video AND extracted-audio hashes,
    global seconds (not local chunk seconds), and global part numbers.
    """
    if not isinstance(manifest,dict) or manifest.get('schema')!='artin_fast_av_v4':
        raise ValueError('Requires actual fast AV extraction manifest')
    if not _exact_hash(manifest.get('video_sha256')):
        raise ValueError('Missing original video SHA256')
    validate_fast(Path('/'),manifest,verify_files=False)
    parts=manifest['parts']
    by_id={p['chunk']:p for p in parts}
    if not isinstance(shards,list) or not shards:
        raise ValueError('Must provide at least one real ASR shard')
    if not isinstance(visual_notes,list) and visual_notes is not None:
        raise ValueError('Invalid visual evidence notes')
    seen_parts=set()
    raw=[]
    for shard in shards:
        if not isinstance(shard,dict) or shard.get('schema')!='artin_asr_shard_v5':
            raise ValueError('Invalid ASR shard')
        n=shard.get('global_chunk')
        if type(n) is not int or n not in by_id or n in seen_parts:
            raise ValueError('Missing, duplicate or unknown global chunk')
        seen_parts.add(n)
        part=by_id[n]
        if shard.get('source_video_sha256')!=manifest['video_sha256']:
            raise ValueError('ASR shard comes from a different video')
        if shard.get('source_audio_sha256')!=part.get('audio_sha256'):
            raise ValueError('ASR shard comes from different or unchecked audio')
        if not _exact_hash(part.get('audio_sha256')):
            raise ValueError('No audio hash in source manifest')
        if shard.get('timebase')!='absolute_original_video_seconds':
            raise ValueError('ASR timebase is not source-global')
        if shard.get('speaker_human_verified') is True or shard.get('teacher_rules_verified') is True:
            raise ValueError('An ASR model cannot verify teacher identity or rules')
        if not isinstance(shard.get('segments'),list):
            raise ValueError('Missing ASR segments')
        for pos,u in enumerate(shard['segments']):
            if not isinstance(u,dict):
                raise ValueError('Invalid speech segment')
            s,e=u.get('start'),u.get('end')
            if type(s) not in (float,int) or type(e) not in (float,int) or not (
                math.isfinite(s) and math.isfinite(e) and
                part['cut_start']-.1<=s<e<=part['cut_end']+1):
                raise ValueError(f'ASR speech outside original film part {n}')
            if u.get('speaker_verified') is True or u.get('verified_teacher_statement') is True:
                raise ValueError('Unreviewed ASR cannot claim a verified speaker')
            if not isinstance(u.get('text'),str) or not u['text'].strip():
                raise ValueError('Missing ASR text')
            mid=(s+e)/2
            # The core owner, not completion order, determines deduplication at overlap.
            owner=min(len(parts),int(mid//300)+1)
            if owner!=n:
                continue
            txt=_normalize(u['text'])
            quality_flags=[]
            if e-s>22:quality_flags.append('ASR_SEGMENT_UNUSUALLY_LONG_CHECK_SILENCE')
            prob=u.get('avg_logprob')
            if prob is not None:
                if type(prob) not in (int,float) or not math.isfinite(prob):
                    raise ValueError('Nonfinite ASR log probability')
                if prob < -0.9:quality_flags.append('LOW_ASR_LOGPROB')
            tokens=txt.split()
            if len(tokens)>=6 and len(set(tokens))<=max(2,len(tokens)//4):
                quality_flags.append('ASR_REPETITIVE_TEXT')
            source=f"{manifest['video_sha256']}|{n}|{pos}|{s:.3f}|{e:.3f}|{txt}"
            raw.append({'id':'asr_'+hashlib.sha256(source.encode('utf8')).hexdigest()[:24],
                        'start':round(s,3),'end':round(e,3),
                        'text':txt,'part_global':n,
                        'batch':part['batch'],'slot':part['slot'],
                        'source_audio_sha256':part['audio_sha256'],
                        'speaker':'UNKNOWN','speaker_verified':False,
                        'original_audio_reviewed':False,
                        'asr_model':shard.get('model','UNKNOWN'),
                        'noise_risk':noise_risk(txt),
                        'human_verified':False,
                        'asr_quality_flags':quality_flags,
                        'can_change_artin_engine':False})
    raw.sort(key=lambda u:(u['start'],u['part_global'],u['id']))
    if len({s['id'] for s in raw})!=len(raw):
        raise ValueError('ASR source-line identity collision')
    # Only exact supported frames can appear in the audiovisual references.
    frames={}
    for part in parts:
        for frame in part.get('frames',[]):
            if not isinstance(frame,dict) or not _exact_hash(frame.get('sha256')):
                raise ValueError('Frame missing extracted source SHA256')
            frames[frame['path']]=dict(frame,part_global=part['chunk'])
    candidates=[]
    for note in visual_notes or []:
        if not isinstance(note,dict) or note.get('path') not in frames:
            raise ValueError('Image interpretation references a non-existent frame')
        fr=frames[note['path']]
        if note.get('frame_sha256')!=fr['sha256']:
            raise ValueError('Image source SHA mismatch')
        if not isinstance(note.get('description'),str):
            raise ValueError('Visual caption must be text')
        candidates.append({'frame_path':fr['path'],'frame_sha256':fr['sha256'],
                           'time_approx':fr['time_approx'],
                           'description_candidate':note['description'][:1500],
                           'human_verified':False,'chart_rule_verified':False,
                           'can_change_artin_engine':False})
    qas=linked_qa_candidates(manifest['video_sha256'],raw)
    review_rules=[]
    teaching_topics=[]
    corrections=[]
    off_topic=[]
    for u in raw:
        if u['noise_risk']!='NOT_IDENTIFIED':
            off_topic.append({'source_id':u['id'],'time':u['start'],
                              'reason':u['noise_risk'],
                              'do_not_delete_original':True,
                              'requires_review_if_mixed':True})
        if any(w in u['text'] for w in _CORRECTION_WORDS):
            corrections.append({'candidate_source_id':u['id'],
                                'time':u['start'],
                                'possible_later_correction':True,
                                'superseded_rule_id':None,
                                'requires_original_audio_review':True})
        mentions_trading=any(w in u['text'] for w in TRADING_MARKERS)
        mentions_action=any(w in u['text'] for w in _TRADE_ACTION)
        mentions_condition=any(w in u['text'] for w in _RULE_CONTEXT)
        possible_rule=(mentions_action and mentions_condition) or (
            any(w in u['text'] for w in ('حد ضرر','حد سود')) and mentions_action)
        if (mentions_trading and not possible_rule and not u['asr_quality_flags']
                and u['noise_risk']=='NOT_IDENTIFIED'):
            teaching_topics.append({'source_utterance_id':u['id'],
                'time':u['start'],'category':'TRADING_TOPIC_NOT_EXECUTABLE_RULE',
                'can_change_artin_engine':False})
        if (not u['asr_quality_flags'] and u['noise_risk']=='NOT_IDENTIFIED'
                and possible_rule):
            nearby=sorted(frames.values(),key=lambda f:abs(f['time_approx']-u['start']))
            review_rules.append({'candidate_id':'candidate_'+u['id'],
                 'source_utterance_id':u['id'],
                 'start':u['start'],'end':u['end'],
                 'nearest_sampled_frames':[{'path':f['path'],'sha256':f['sha256']}
                        for f in nearby[:2]],
                 'decision':'UNKNOWN','conditions':None,
                 'teacher_identity_verified':False,
                 'questions_answered_verified':False,
                 'later_corrections_resolved':False,
                 'implementation_status':'REVIEW',
                 'can_change_artin_engine':False})
    processed=len(seen_parts)
    return {'schema':'artin_teacher_av_review_v5',
            'source_video_sha256':manifest['video_sha256'],
            'duration_seconds':manifest['duration_seconds'],
            'parts_total':len(parts),'parts_with_asr':processed,
            'complete_original_video_review':False,
            'parts_missing_asr':sorted(set(by_id)-seen_parts),
            'speech_lines':raw,
            'suspect_asr_lines':[{'id':u['id'],'time':u['start'],
                  'flags':u['asr_quality_flags']} for u in raw if u['asr_quality_flags']],
            'possible_questions_and_following_utterances':qas['question_candidates'],
            'possible_later_corrections':corrections,
            'classroom_noise_or_mixed_review':off_topic,
            'sampled_frames_count':len(frames),
            'unverified_vision_candidates':candidates,
            'rule_candidates':review_rules,
            'teaching_topics_not_rules':teaching_topics,
            'teacher_answers_human_verified':0,
            'rules_executable':0,'real_orders_allowed':False,
            'paper_orders_allowed':False,
            'requires_human_original_audio_and_chart_review':True}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--transcripts',type=Path,nargs='+',required=True)
    p.add_argument('--visual-notes',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    m=json.loads(a.manifest.read_text(encoding='utf8'))
    t=[json.loads(file.read_text(encoding='utf8')) for file in a.transcripts]
    v=json.loads(a.visual_notes.read_text(encoding='utf8')) if a.visual_notes else None
    out=review_real_asr(m,t,v)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'parts_total':out['parts_total'],
         'parts_with_asr':out['parts_with_asr'],
         'possible_question_count':len(out['possible_questions_and_following_utterances']),
         'rule_candidates_unverified':len(out['rule_candidates']),
         'rules_executable':0,'real_orders_allowed':False},ensure_ascii=False))


if __name__=='__main__':main()
