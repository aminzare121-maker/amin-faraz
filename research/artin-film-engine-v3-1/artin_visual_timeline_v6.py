#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""High-resolution, time-linked visual review of the board AND typed-class chat.

For each 5-minute global part, capture a frame at regular source timestamps.
Keep original frame, centre-board crop and right-side CHAT crop separately.
These are ORIGINAL IMAGE EVIDENCE, not verified chart interpretations, and
not complete coverage of a fast-scrolling chat between sample timestamps.
All media remains local; never commit private frames or teacher/student names.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

from artin_fast_av_v4 import validate_fast
from artin_film_pipeline import file_sha256


def _sha(text: str):
    return hashlib.sha256(text.encode('utf8')).hexdigest()[:24]


def frame_times(parts, sample_s=20):
    """Original-video timebase; stable identity even at 18->19 batch boundary."""
    if type(sample_s) is not int or not 5 <= sample_s <= 120:
        raise ValueError('Sample spacing must be 5..120 seconds')
    if not parts:
        raise ValueError('No source parts')
    result=[]
    for p in parts:
        if p.get('chunk',0)<1 or p['core_end']<=p['core_start']:
            raise ValueError('Invalid source core interval')
        start=float(p['core_start'])
        end=float(p['core_end'])
        duration=end-start
        # Start of every 5-minute section is included even when a final
        # incomplete section is only a few seconds long.
        step_count=max(1,math.ceil(duration/sample_s))
        times=[min(end-.05,start+max(.05, (i+.5)*sample_s)) for i in range(step_count)]
        times=sorted(set(round(x,3) for x in times))
        for pos,t in enumerate(times,1):
            result.append({'global_chunk':p['chunk'],
                           'batch':p['batch'],'slot':p['slot'],
                           'time_seconds':t,'frame_index_in_chunk':pos,
                           'frame_id':f"b{p['batch']:03d}_s{p['slot']:02d}_g{p['chunk']:06d}_t{int(round(t*1000)):010d}"})
    return result


def _extract_one(video, root, row, board_bounds, chat_bounds, upscale):
    from PIL import Image, ImageEnhance, ImageFilter
    stem=row['frame_id']
    frame=root/'frames'/f'{stem}_original.jpg'
    frame.parent.mkdir(parents=True,exist_ok=True)
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
             '-ss',str(row['time_seconds']),'-i',str(video),
             '-map','0:v:0','-frames:v','1','-q:v','3',str(frame)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=70)
    if result.returncode or not frame.is_file() or frame.stat().st_size<200:
        raise RuntimeError('Cannot sample original video at source timestamp: '+result.stderr[-450:])
    with Image.open(frame) as raw:
        img=raw.convert('RGB')
        w,h=img.size
        if w<320 or h<200:
            raise ValueError('Video resolution too small for classroom text')
        def crop(bounds):
            l,t,r,b=bounds
            return img.crop((int(l*w),int(t*h),int(r*w),int(b*h)))
        board=crop(board_bounds)
        chat=crop(chat_bounds)
        # The non-destructive original is saved as evidence; enhanced copies
        # can improve handwriting/chat readability but never overwrite source.
        if upscale>1:
            chat=chat.resize((chat.width*upscale,chat.height*upscale),Image.Resampling.LANCZOS)
            chat=ImageEnhance.Contrast(chat).enhance(1.35)
            chat=chat.filter(ImageFilter.UnsharpMask(radius=1.2,percent=125,threshold=2))
        board_path=root/'board'/f'{stem}_board.png'
        chat_path=root/'chat'/f'{stem}_chat.png'
        board_path.parent.mkdir(parents=True,exist_ok=True)
        chat_path.parent.mkdir(parents=True,exist_ok=True)
        board.save(board_path,format='PNG',optimize=True)
        chat.save(chat_path,format='PNG',optimize=True)
    out={**row,'video_frame':{'path':frame.relative_to(root).as_posix(),'sha256':file_sha256(frame),
                             'original_width':w,'original_height':h},
         'board':{'path':board_path.relative_to(root).as_posix(),'sha256':file_sha256(board_path)},
         'chat':{'path':chat_path.relative_to(root).as_posix(),'sha256':file_sha256(chat_path)},
         'typed_student_question_verified':False,'speaker_role_verified':False,
         'chart_meaning_verified':False,'any_rule_executable':False}
    return out


def validate_visual_index(root, manifest, index, verify_files=True):
    validate_fast(Path(root),manifest,verify_files=False)
    if not isinstance(index,dict) or index.get('schema')!='artin_classroom_visual_v6':
        raise ValueError('Invalid visual evidence index')
    if index.get('source_video_sha256')!=manifest['video_sha256']:
        raise ValueError('Visuals belong to another original film')
    p=index.get('rows')
    expected=frame_times(manifest['parts'],index['sample_seconds'])
    if not isinstance(p,list) or len(p)!=len(expected):
        raise ValueError('Visual timeline has missing or additional frames')
    root=Path(root).resolve()
    for x,y in zip(p,expected):
        for k in ('global_chunk','batch','slot','time_seconds','frame_id'):
            if x.get(k)!=y[k]:
                raise ValueError('Visual evidence time/identity mismatch at '+str(y['frame_id']))
        for channel in ('video_frame','board','chat'):
            o=x.get(channel)
            if not isinstance(o,dict) or not isinstance(o.get('sha256'),str) or len(o['sha256'])!=64:
                raise ValueError('Visual image missing SHA256')
            path=(root/o['path']).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Visual path escapes output folder')
            if verify_files:
                if not path.is_file() or file_sha256(path)!=o['sha256']:
                    raise ValueError('Visual image corrupted or relabeled')
    return True


def extract_visual_timeline(video, root, manifest, sample_seconds=20,
                            workers=4,chat_bounds=(.71,.11,.90,.95),
                            board_bounds=(0,.14,.71,.91),upscale=2):
    if not 1<=int(workers)<=12:
        raise ValueError('Invalid image worker count')
    if upscale not in (1,2,3):
        raise ValueError('Invalid image enhancement scale')
    for bounds in (board_bounds,chat_bounds):
        if len(bounds)!=4 or not (0<=bounds[0]<bounds[2]<=1
                                  and 0<=bounds[1]<bounds[3]<=1):
            raise ValueError('Invalid screen region crop')
    video=Path(video).resolve()
    root=Path(root).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    if root==video.parent or root==video:
        raise ValueError('Output folder must be distinct from original film')
    if manifest.get('video_sha256')!=file_sha256(video):
        raise ValueError('Original video content differs from verified speech source')
    validate_fast(root,manifest,verify_files=False)
    plan=frame_times(manifest['parts'],sample_seconds)
    root.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers,len(plan))) as pool:
        futures={pool.submit(_extract_one,video,root,r,board_bounds,chat_bounds,upscale):r['frame_id']
                 for r in plan}
        indexed={}
        for f in concurrent.futures.as_completed(futures):
            indexed[futures[f]]=f.result()
    ordered=[indexed[x['frame_id']] for x in plan]
    index={'schema':'artin_classroom_visual_v6',
       'source_video_sha256':manifest['video_sha256'],
       'source_duration_seconds':manifest['duration_seconds'],
       'sample_seconds':sample_seconds,
       'frame_count':len(ordered),
       'regions':{'board':list(board_bounds),'typed_chat':list(chat_bounds)},
       'rows':ordered,
       'capture_notice':'SAMPLED_FRAMES_NOT_ALL_CHAT_MESSAGES',
       'vision_model_ran':False,'ocr_model_ran':False,
       'speaker_identity_verified':False,'teacher_rules_verified':0}
    validate_visual_index(root,manifest,index)
    path=root/'visual_timeline_v6.json'
    tmp=path.with_suffix('.pending')
    tmp.write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf8')
    tmp.replace(path)
    return index


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--video',required=True,type=Path)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--sample-seconds',type=int,default=20)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--upscale',type=int,default=2)
    a=p.parse_args()
    m=json.loads(a.manifest.read_text(encoding='utf8'))
    result=extract_visual_timeline(a.video,a.out,m,a.sample_seconds,a.workers,upscale=a.upscale)
    print(json.dumps({'source_duration_seconds':result['source_duration_seconds'],
         'sampled_frames':result['frame_count'],
         'chat_crops':result['frame_count'],'board_crops':result['frame_count'],
         'visual_meaning_verified':False},ensure_ascii=False))


if __name__=='__main__':main()
