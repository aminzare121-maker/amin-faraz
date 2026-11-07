#!/usr/bin/env python3
"""Fast, source-verified full-film chat-change timeline at 1 image/sec.

Purpose: find brief typed messages that 30s source snapshots may miss.
This does NOT read messages or guarantee that every frame/message is visible.
Only source time, original source hash and pixel-change metrics leave runner;
original student screenshots, audio, and video are never committed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from artin_ephemeral_remote_ingest import download, get_direct_url

WIDTH=64
HEIGHT=160
FRAME_SIZE=WIDTH*HEIGHT

def score(prev,current):
    if prev is None:return 1.0
    if len(prev)!=FRAME_SIZE or len(current)!=FRAME_SIZE:
        raise ValueError("Invalid low-resolution chat luma buffer")
    return sum(abs(x-y) for x,y in zip(prev,current))/(255*FRAME_SIZE)

def collect_index(frames, *, step=1, threshold=.02, anchor_every=30,
                  source_sha256, duration_seconds):
    if type(step) is not int or not 1<=step<=10:
        raise ValueError("Invalid source sampling step")
    if not 0<=threshold<=.5 or type(anchor_every) is not int or anchor_every<10:
        raise ValueError("Invalid chat detection settings")
    if not isinstance(source_sha256,str) or len(source_sha256)!=64:
        raise ValueError("Source hash required")
    if not isinstance(duration_seconds,(float,int)) or duration_seconds<=0:
        raise ValueError("Video duration required")
    rows=[];last=None;last_selected=-anchor_every;count=0
    for frame in frames:
        if not isinstance(frame,bytes) or len(frame)!=FRAME_SIZE:
            raise ValueError("Partial or corrupted source frame")
        t=round(count*step,3)
        if t>duration_seconds+.5:raise ValueError("Samples outside source movie")
        change=score(last,frame)
        is_change=change>=threshold
        scheduled=t-last_selected>=anchor_every
        pick=last is None or is_change or scheduled
        if pick:last_selected=t
        # This is only a sampled video frame; no human can claim all chat
        # messages were observed, especially messages shorter than step.
        rows.append({'source_time_seconds':t,'global_part':int(t//300)+1,
                     'frame_ordinal':count,'change_score':round(change,6),
                     'priority_capture':pick,
                     'reason':'FIRST' if last is None else
                         'CHAT_CHANGED' if is_change else
                         'PERIODIC_ANCHOR' if scheduled else 'NOT_SELECTED',
                     'chat_text_verified':False,'question_verified':False})
        count+=1;last=frame
    if not rows:raise ValueError("No visible frames decoded")
    return {'schema':'artin_source_chat_temporal_index_v8',
       'source_video_sha256':source_sha256,
       'video_duration_seconds':duration_seconds,
       'sample_interval_seconds':step,
       'chat_region':'[0.71,0.11,0.90,0.95] normalized source video',
       'sampled_source_frames':len(rows),
       'selected_frames_for_high_resolution_recheck':sum(r['priority_capture'] for r in rows),
       'changed_chat_frames':sum(r['reason']=='CHAT_CHANGED' for r in rows),
       'first_frame_seconds':rows[0]['source_time_seconds'],
       'last_frame_seconds':rows[-1]['source_time_seconds'],
       'ground_truth_all_chat_messages_found':False,
       'printed_persian_chat_recognized':False,
       'teacher_answers_verified':0,'rules_executable':0,
       'rows':rows}

def raw_gray_frames(source_video):
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
         '-i',str(source_video),
         '-vf','fps=1,crop=iw*0.19:ih*0.84:iw*0.71:ih*0.11,scale=64:160:flags=fast_bilinear,format=gray',
         '-an','-sn','-f','rawvideo','-pix_fmt','gray','pipe:1']
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    count=0
    try:
        while True:
            chunk=p.stdout.read(FRAME_SIZE)
            if not chunk:break
            if len(chunk)!=FRAME_SIZE:raise ValueError('Video ended in incomplete chat frame')
            count+=1
            yield chunk
    finally:
        if p.poll() is None and count==0:p.kill()
        err=p.communicate()[1]
        if p.returncode:
            raise RuntimeError('Original video chat sampling failed: '+err.decode('utf8','replace')[-400:])

def run_video(video,out,source_sha256,duration_seconds):
    start=time.monotonic()
    video=Path(video)
    h=hashlib.sha256()
    with video.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    if h.hexdigest()!=source_sha256:
        raise ValueError('Source MP4 SHA does not match original lesson')
    result=collect_index(raw_gray_frames(video),step=1,threshold=.02,
              anchor_every=30,source_sha256=source_sha256,
              duration_seconds=duration_seconds)
    elapsed=time.monotonic()-start
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'full_second_by_second_chat_TIMES_ONLY.json').write_text(
         json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    safe={k:v for k,v in result.items() if k!='rows'}
    safe['runtime_seconds']=round(elapsed,2)
    safe['old_thirty_second_source_samples']=math.ceil(duration_seconds/30)
    safe['source_frames_not_original_images']=True
    (out/'chat_change_summary_safe.json').write_text(
        json.dumps(safe,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_REAL_1SEC_CHAT_CHANGE='+json.dumps(safe,ensure_ascii=False),flush=True)
    return safe

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--duration-seconds',type=float,required=True)
    a=p.parse_args()
    share=os.environ.get('TEACHER_VIDEO_PAGE','')
    if not share.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Source share page not user provided')
    a.out.mkdir(parents=True,exist_ok=True)
    direct,_=get_direct_url(share)
    video=a.out/'source_private.mp4'
    size,sha=download(direct,video)
    if sha!=a.expected_sha256:raise ValueError('Source changed')
    run_video(video,a.out,sha,a.duration_seconds)

if __name__=='__main__':main()
