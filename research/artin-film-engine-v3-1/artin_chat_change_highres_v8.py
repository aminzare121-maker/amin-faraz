#!/usr/bin/env python3
"""Create actual high-res Persian chat crops at the 1-second change-detection timestamps.

The temporal index only contains luma differences. This module fetches frames
from the SHA-verified original video at the exact selected times. No OCR or
teacher role is claimed. Source remains ephemeral; frames stored privately.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import subprocess
from io import BytesIO
from artin_ephemeral_remote_ingest import get_direct_url,download
from artin_chat_temporal_v8 import FRAME_SIZE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def selected_times(timeline):
    if timeline.get('schema')!='artin_source_chat_temporal_index_v8':
        raise ValueError('Original 1-second video-source index required')
    src=timeline.get('source_video_sha256')
    if not isinstance(src,str) or len(src)!=64:
        raise ValueError('Original source SHA256 is absent')
    rows=timeline.get('rows')
    if not isinstance(rows,list) or not rows:
        raise ValueError('No original source timestamps')
    last=-1
    selected=[]
    for row in rows:
        t=row.get('source_time_seconds')
        if type(t) not in (float,int) or not math.isfinite(t) or t<=last:
            raise ValueError('Unordered or corrupt full-video chat timeline')
        last=t
        if row.get('priority_capture') is True:
            n=int(t//300)+1
            b=(n-1)//18+1
            slot=(n-1)%18+1
            selected.append({
                'frame_id':f'b{b:03d}_s{slot:02d}_g{n:06d}_t{int(round(t*1000)):010d}',
                'time_seconds':t,'global_chunk':n,'batch':b,'slot':slot,
                'original_reason':row.get('reason')})
    if not selected:raise ValueError('No selected source images')
    return selected

def one(video,out,req):
    from PIL import Image,ImageEnhance,ImageFilter
    t=req['time_seconds']
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
         '-ss',str(t),'-i',str(video),'-frames:v','1',
         '-vf','crop=iw*0.19:ih*0.84:iw*0.71:ih*0.11',
         '-c:v','png','-f','image2pipe','pipe:1']
    q=subprocess.run(cmd,capture_output=True,timeout=70)
    if q.returncode or len(q.stdout)<1000:
        raise RuntimeError('Cannot obtain full-resolution original chat at '+str(t))
    with Image.open(BytesIO(q.stdout)) as im:
        crop=im.convert('RGB')
        crop=crop.resize((crop.width*2,crop.height*2),Image.Resampling.LANCZOS)
        crop=ImageEnhance.Contrast(crop).enhance(1.35)
        crop=crop.filter(ImageFilter.UnsharpMask(radius=1.2,percent=125,threshold=2))
        dest=out/'chat'/f"{req['frame_id']}_chat.png"
        dest.parent.mkdir(parents=True,exist_ok=True)
        crop.save(dest,optimize=True)
    return {**req,'chat':{'path':dest.relative_to(out).as_posix(),
                         'sha256':sha(dest)},
            'text_verified':False,'question_verified':False,
            'teacher_answer_verified':False}

def collect(video,index,root,*,workers=4,max_selected=600):
    if type(workers) is not int or not 1<=workers<=12:
        raise ValueError('Invalid extraction worker count')
    if type(max_selected) is not int or not 1<=max_selected<=10000:
        raise ValueError('Invalid extraction cap')
    rows=selected_times(index)
    if len(rows)>max_selected:
        raise ValueError('Unexpectedly large number of selected frames')
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if sha(video)!=index['source_video_sha256']:
        raise ValueError('Video SHA does not match timestamp source')
    output={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures={ex.submit(one,video,root,row):row['frame_id'] for row in rows}
        for fut in concurrent.futures.as_completed(futures):
            output[futures[fut]]=fut.result()
    ordered=[output[r['frame_id']] for r in rows]
    m={'schema':'artin_change_selected_chat_v8',
       'source_video_sha256':index['source_video_sha256'],
       'original_video_seconds':index['video_duration_seconds'],
       'low_res_source_frames':len(index['rows']),
       'source_selection_interval_seconds':1,
       'frames_selected':len(ordered),
       'chat_text_human_verified':False,
       'teacher_answers_verified':0,'rules_executable':0,
       'rows':ordered}
    (root/'chat_selected_index.json').write_text(
        json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_1SEC_CHAT_FULL_RES='+json.dumps({
        'source_video_sha256':m['source_video_sha256'],
        'selected_high_resolution_chat_images':len(ordered),
        'source_frames_checked':len(index['rows']),
        'chat_ocr_ran':False,
        'rules_verified':0},ensure_ascii=False),flush=True)
    return m

def main():
    import os
    p=argparse.ArgumentParser()
    p.add_argument('--temporal-index',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--source-page',default='https://my.uupload.ir/p/aGgKYdpL')
    a=p.parse_args()
    index=json.loads(a.temporal_index.read_text(encoding='utf8'))
    if not a.source_page.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Only previously authorized Uupload share URLs')
    a.out.mkdir(parents=True,exist_ok=True)
    direct,_=get_direct_url(a.source_page)
    video=a.out/'source_private.mp4'
    _,h=download(direct,video)
    if h!=index['source_video_sha256']:raise ValueError('Original video changed')
    collect(video,index,a.out)

if __name__=='__main__':main()
