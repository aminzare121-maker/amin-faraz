#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable, safe, one-request classroom video ingestion for private GitHub CI.

Input is a typed JSON request in a private branch; changing it triggers a job.
No OpenAI API, broker credentials, teacher/student roles, cloud LLM, or trades.
Use only explicitly supplied Uupload share URLs, never arbitrary arbitrary SSRF URLs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from artin_ephemeral_remote_ingest import download,get_direct_url
from artin_fast_av_v4 import fast_prepare
from artin_visual_timeline_v6 import extract_visual_timeline


def validate_job(raw:dict):
    if not isinstance(raw,dict):
        raise ValueError('Job must be a JSON object')
    required={'schema','job_id','source_url','mode'}
    optional={'expected_sha256','sample_seconds'}
    if not required<=set(raw) or set(raw)-(required|optional):
        raise ValueError('Job has missing or unapproved fields')
    if raw['schema']!='artin_private_video_job_v6':
        raise ValueError('Unknown video request schema')
    if not isinstance(raw['job_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',raw['job_id']):
        raise ValueError('Invalid job ID')
    url=raw['source_url']
    if not isinstance(url,str) or len(url)>300:
        raise ValueError('Invalid video source URL')
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname!='my.uupload.ir' or not re.fullmatch(
             r'/p/[A-Za-z0-9_-]{3,80}/?',p.path
         ) or p.username or p.password or p.query or p.fragment:
        raise ValueError('Only direct user-provided Uupload share pages allowed')
    if raw['mode'] not in ('SOURCE_AND_FAST_AUDIO','SOURCE_AUDIO_AND_CHAT'):
        raise ValueError('Job mode must be a safe evidence-only operation')
    h=raw.get('expected_sha256')
    if h is not None and (not isinstance(h,str) or not re.fullmatch(r'[a-f0-9]{64}',h)):
        raise ValueError('Expected source SHA256 invalid')
    step=raw.get('sample_seconds',30)
    if type(step) is not int or not 5<=step<=120:
        raise ValueError('Invalid visual sample period')
    return {'schema':raw['schema'],'job_id':raw['job_id'],'source_url':url,
            'mode':raw['mode'],'expected_sha256':h,'sample_seconds':step}


def run_job(job:dict,private_root:Path):
    j=validate_job(job)
    root=Path(private_root).resolve()
    root.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    direct,_=get_direct_url(j['source_url'])
    local=root/'ephemeral_original.mp4'
    total,sha=download(direct,local)
    if j['expected_sha256'] and sha!=j['expected_sha256']:
        raise ValueError('Changed video detected - SHA mismatch')
    download_seconds=time.monotonic()-start
    manifest=fast_prepare(local,root/'fast',workers=4,frames_per_part=2)
    fast_seconds=time.monotonic()-start-download_seconds
    visual=None;visual_seconds=None
    if j['mode']=='SOURCE_AUDIO_AND_CHAT':
        visual=extract_visual_timeline(local,root/'visual',manifest,
                 sample_seconds=j['sample_seconds'],workers=4)
        visual_seconds=time.monotonic()-start-download_seconds-fast_seconds
    output={'schema':'artin_source_report_v6','job_id':j['job_id'],
        'mode':j['mode'],
        'original_video_sha256':sha,'original_video_bytes':total,
        'source_video_duration_seconds':manifest['duration_seconds'],
        'global_chunks':len(manifest['parts']),
        'batch_count':len(manifest['batches']),
        'last_part_seconds':round(
            manifest['parts'][-1]['core_end']-manifest['parts'][-1]['core_start'],3),
        'video_sha_verified':True,'audio_clip_hashes_verified':True,
        'fast_sampled_frames':sum(len(p['frames']) for p in manifest['parts']),
        'additional_chat_frames':visual['frame_count'] if visual else 0,
        'additional_board_frames':visual['frame_count'] if visual else 0,
        'duration_download_seconds':round(download_seconds,2),
        'duration_fast_extract_seconds':round(fast_seconds,2),
        'duration_visual_extract_seconds':round(visual_seconds,2) if visual_seconds is not None else None,
        'duration_total_seconds':round(time.monotonic()-start,2),
        'speech_model_ran':False,'text_on_board_verified':False,
        'student_question_verified':0,'teacher_rules_verified':0,
        'trades_authorized':False}
    (root/'safe_result.json').write_text(
         json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_REUSABLE_VIDEO_JOB_RESULT='+json.dumps(output,ensure_ascii=False),flush=True)
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--request',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    request=json.loads(a.request.read_text(encoding='utf8'))
    run_job(request,a.out)


if __name__=='__main__':main()
