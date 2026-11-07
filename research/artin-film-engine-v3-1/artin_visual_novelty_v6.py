#!/usr/bin/env python3
"""Prioritize changed teacher-board and student-chat screenshots for VLM review.

Never delete/deprecate original screenshots.  A tiny chat message can change
without exceeding a pixel threshold, so periodic anchors and an optional
full review mode remain mandatory for high-assurance use.
"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageChops
from artin_film_pipeline import file_sha256


def score_difference(prev,current):
    if prev is None:return 1.0
    diff=ImageChops.difference(prev,current)
    hist=diff.histogram()
    return round(sum(x*count for x,count in enumerate(hist))/(255*prev.width*prev.height),6)


def novelty_plan(root,visual_index,*,threshold=.01,max_gap_seconds=300,channel='chat',
                 full_review=False):
    if channel not in ('board','chat'):
        raise ValueError('Only source board/chat channels')
    if not (isinstance(threshold,(int,float)) and 0<=threshold<=.25):
        raise ValueError('Threshold out of range')
    if type(max_gap_seconds) is not int or not 30<=max_gap_seconds<=1200:
        raise ValueError('Invalid periodic review gap')
    if not isinstance(visual_index,dict) or visual_index.get('schema')!='artin_classroom_visual_v6':
        raise ValueError('Only original teacher video visual index accepted')
    root=Path(root).resolve()
    rows=visual_index.get('rows')
    if not isinstance(rows,list) or not rows:
        raise ValueError('No sampled visual frames')
    out=[];prior=None;last_selected=None;prior_t=-1
    for r in rows:
        timestamp=r.get('time_seconds')
        if type(timestamp) not in (float,int) or timestamp<=prior_t:
            raise ValueError('Frames must be in original video time order')
        prior_t=timestamp
        img_info=r.get(channel)
        if not isinstance(img_info,dict):raise ValueError('Missing cropped image')
        filename=(root/img_info['path']).resolve()
        if not filename.is_relative_to(root) or not filename.is_file():
            raise ValueError('Unsafe/missing cropped source image')
        if file_sha256(filename)!=img_info['sha256']:
            raise ValueError('Image SHA mismatch')
        with Image.open(filename) as pic:
            current=pic.convert('L').resize((64,160),Image.Resampling.LANCZOS)
        novelty=score_difference(prior,current)
        periodic=(last_selected is None or timestamp-last_selected>=max_gap_seconds)
        select=bool(full_review or prior is None or novelty>=threshold or periodic)
        reason=('FULL_REVIEW' if full_review else
                'INITIAL_FRAME' if prior is None else
                'SCENE_CHANGE' if novelty>=threshold else
                'PERIODIC_ANCHOR' if periodic else
                'DEFERRED_RETAINED')
        out.append({'frame_id':r['frame_id'],'channel':channel,
            'source_image_sha256':img_info['sha256'],
            'image_observed_at_seconds':timestamp,
            'global_chunk':r['global_chunk'],
            'visual_difference_score':novelty,
            'selected_for_priority_review':select,
            'selection_reason':reason,
            'original_image_retained':True,
            'text_verified':False,'teacher_rule_verified':False})
        if select:last_selected=timestamp
        prior=current
    return {'schema':'artin_visual_novelty_v6',
       'source_video_sha256':visual_index['source_video_sha256'],
       'channel':channel,'total_frames':len(out),
       'selected_frames':sum(x['selected_for_priority_review'] for x in out),
       'not_yet_modeled_frames':sum(not x['selected_for_priority_review'] for x in out),
       'full_review_requested':full_review,
       'selection_is_not_proof_of_all_chat_messages':True,
       'nothing_deleted':True,'rows':out}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--visual-root',required=True,type=Path)
    p.add_argument('--index',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--channel',default='chat',choices=['chat','board'])
    p.add_argument('--full-review',action='store_true')
    a=p.parse_args()
    idx=json.loads(a.index.read_text(encoding='utf8'))
    result=novelty_plan(a.visual_root,idx,channel=a.channel,full_review=a.full_review)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'channel':a.channel,
         'total_frames':result['total_frames'],
         'priority_frames':result['selected_frames'],
         'frames_retained':result['total_frames'],
         'verified_rules':0},ensure_ascii=False))


if __name__=='__main__':main()
