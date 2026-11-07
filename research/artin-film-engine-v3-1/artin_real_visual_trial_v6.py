#!/usr/bin/env python3
"""Private runner end-to-end proof of chat + lecture-board visual source sampling.

Does not extract teacher rules, does not claim legibility of Persian handwriting.
"""
import argparse
import json
import os
from pathlib import Path
import time
from artin_ephemeral_remote_ingest import download,get_direct_url
from artin_fast_av_v4 import fast_prepare
from artin_visual_timeline_v6 import extract_visual_timeline

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--sample-seconds',type=int,default=30)
    a=p.parse_args()
    page=os.environ.get('TEACHER_VIDEO_PAGE','')
    if not page.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Only user supplied page')
    a.out.mkdir(parents=True,exist_ok=True)
    st=time.monotonic()
    url,_=get_direct_url(page)
    video=a.out/'original_private.mp4'
    n,sha=download(url,video)
    if sha!=a.expected_sha256:
        raise ValueError('Teacher video SHA256 mismatch')
    t_download=time.monotonic()-st
    fast=fast_prepare(video,a.out/'fast',frames_per_part=0,workers=4)
    t_fast=time.monotonic()-st-t_download
    vision=extract_visual_timeline(video,a.out/'visual',fast,
                    sample_seconds=a.sample_seconds,workers=4)
    t_vision=time.monotonic()-st-t_download-t_fast
    summary={'schema':'artin_original_visual_sampling_run_v6',
       'video_sha256':sha,'source_bytes':n,'duration_seconds':fast['duration_seconds'],
       'part_count':len(fast['parts']),'source_images':vision['frame_count'],
       'high_resolution_chat_images':vision['frame_count'],
       'board_images':vision['frame_count'],
       'sample_period_seconds':a.sample_seconds,
       'first_time_seconds':vision['rows'][0]['time_seconds'],
       'last_time_seconds':vision['rows'][-1]['time_seconds'],
       'download_seconds':round(t_download,2),
       'audio_extraction_seconds':round(t_fast,2),
       'visual_extraction_seconds':round(t_vision,2),
       'visual_semantics_verified':False,
       'typed_student_questions_verified':0,
       'teacher_rules_verified':0,
       'mt5_or_trade_actions':0}
    (a.out/'visual_summary_safe.json').write_text(
          json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_REAL_VISUAL_TRIAL='+json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
