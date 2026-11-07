#!/usr/bin/env python3
"""Actual Artin: verified original MP4 -> fast AV -> stronger ASR -> Q&A review.

All generated outputs are UNVERIFIED for teacher meaning and trading decisions.
Private video/audio stay on ephemeral runner; never commit them.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from artin_ephemeral_remote_ingest import get_direct_url, download
from artin_fast_av_v4 import fast_prepare, validate_fast
from artin_real_asr_trial_v5 import read_pcm_array
from artin_teacher_av_review_v5 import review_real_asr


def run(page: str, root: Path, model_name: str, max_parts: int,
        expected_sha256: str | None = None):
    if not page.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Only user-provided Uupload share page is accepted')
    if max_parts<1 or max_parts>500:
        raise ValueError('Invalid maximum number of source parts')
    root.mkdir(parents=True,exist_ok=True)
    direct,_=get_direct_url(page)
    started=time.monotonic()
    video=root/'source_private.mp4'
    n,digest=download(direct,video)
    if expected_sha256 and digest!=expected_sha256:
        raise ValueError('Original video SHA256 changed since previous full-file verification')
    print('ARTIN_V5_ORIGINAL_DOWNLOADED_BYTES='+str(n),flush=True)
    m=fast_prepare(video,root/'fast',workers=4,frames_per_part=2)
    validate_fast(root/'fast',m,verify_files=True)
    print('ARTIN_V5_FAST_EXTRACTED='+json.dumps({'parts':len(m['parts']),
         'frames':sum(len(x['frames']) for x in m['parts']),
         'seconds':m['elapsed_seconds']},ensure_ascii=False),flush=True)
    from faster_whisper import WhisperModel
    model=WhisperModel(model_name,device='cpu',compute_type='int8',
                       cpu_threads=4,num_workers=1)
    docs=[]
    upto=min(max_parts,len(m['parts']))
    for part in m['parts'][:upto]:
        audio=read_pcm_array(root/'fast'/part['audio'])
        start=time.monotonic()
        segments,info=model.transcribe(audio,language='fa',vad_filter=True,beam_size=5,
                        condition_on_previous_text=False,word_timestamps=False)
        entries=[]
        for i,s in enumerate(segments):
            begin=part['cut_start']+float(s.start)
            end=part['cut_start']+float(s.end)
            if end<=begin:continue
            # Avoid accepting decoder spillover beyond the last sample.
            end=min(end,part['cut_end'])
            if end<=begin:continue
            entries.append({'id':f"p{part['chunk']:03d}_{i:04d}",
                'start':round(begin,3),'end':round(end,3),
                'text':s.text.strip(),'speaker':'UNKNOWN',
                'speaker_verified':False,
                'avg_logprob':round(float(s.avg_logprob),4),
                'no_speech_prob':round(float(s.no_speech_prob),4)})
        shard={'schema':'artin_asr_shard_v5','global_chunk':part['chunk'],
               'source_video_sha256':m['video_sha256'],
               'source_audio_sha256':part['audio_sha256'],
               'timebase':'absolute_original_video_seconds',
               'model':model_name,'speaker_human_verified':False,
               'teacher_rules_verified':False,'segments':entries}
        docs.append(shard)
        (root/f"unverified_asr_part_{part['chunk']:03d}.json").write_text(
             json.dumps(shard,ensure_ascii=False,indent=2),encoding='utf8')
        print('ARTIN_V5_REAL_ASR_CHUNK='+json.dumps({'global_chunk':part['chunk'],
              'segments':len(entries),'inference_seconds':round(time.monotonic()-start,2),
              'source_audio_sha256':part['audio_sha256']},ensure_ascii=False),flush=True)
    report=review_real_asr(m,docs)
    if report['rules_executable'] or report['real_orders_allowed']:
        raise RuntimeError('Failsafe: unverified transcripts must not authorize trades')
    private_report=root/'unverified_teacher_evidence.json'
    private_report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    limited={'schema':'artin_v5_real_media_run','video_sha256':digest,
             'duration_seconds':m['duration_seconds'],
             'total_parts':len(m['parts']),'parts_with_transcripts':len(docs),
             'remaining_parts':report['parts_missing_asr'],
             'real_images_sampled':sum(len(x['frames']) for x in m['parts']),
             'possible_question_count':len(report['possible_questions_and_following_utterances']),
             'suspect_asr_lines':len(report['suspect_asr_lines']),
             'rule_candidates_unverified':len(report['rule_candidates']),
             'teacher_answers_verified':0,'rules_executable':0,
             'teacher_voice_identity_verified':False,
             'vision_caption_model_ran':False,
             'elapsed_total_seconds':round(time.monotonic()-started,2),
             'paper_orders_allowed':False,'real_orders_allowed':False,
             'status':'PARTIAL_SPEECH_AND_IMAGE_EVIDENCE_NOT_TEACHER_VERIFIED'}
    (root/'public_safe_report.json').write_text(
        json.dumps(limited,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_V5_REAL_INTEGRATED_REPORT='+json.dumps(limited,ensure_ascii=False),flush=True)
    return limited


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--model',default='large-v3-turbo')
    p.add_argument('--max-parts',type=int,default=1)
    p.add_argument('--expected-sha256')
    a=p.parse_args()
    page=os.environ.get('TEACHER_VIDEO_PAGE','')
    run(page,a.out,a.model,a.max_parts,a.expected_sha256)


if __name__=='__main__':main()
