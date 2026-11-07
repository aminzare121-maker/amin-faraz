"""Auditable *sampled* video-frame inspection with a locally installed vision model.

Frames are genuinely extracted from the original video. The model is asked to
identify screen content but its interpretations are explicitly unverified. This
is NOT a complete frame-by-frame examination of every video frame, nor an MT5
strategy/teacher-approval mechanism.
"""
from __future__ import annotations

import concurrent.futures
import json
import math
from pathlib import Path
from artin_batch_slots import artifact_path, batch_frames_dir
from artin_film_pipeline import (atomic_json, file_sha256, load_manifest,
                                 ollama_json, run_cmd)

SCENE_TYPES = frozenset({'CHART', 'SLIDE', 'CAMERA', 'NON_LESSON', 'UNKNOWN'})
VISION_SYSTEM = '''You are examining sampled screenshots of a Persian trading-class video.
Return JSON only: {"observations":[{"frame_id":"exact known id", "scene_type":"CHART|SLIDE|CAMERA|NON_LESSON|UNKNOWN", "visible_text_candidate":"", "visual_description_candidate":"", "related_to_trading_candidate":false}]}
Every observation must refer to an exact supplied frame_id. Do not hallucinate invisible candle prices, indicators, timestamps or support/resistance values. No speaker identity, teacher approval, trading signals, or trade decisions. Every observation is UNVERIFIED and may be incomplete because images are sparsely sampled.'''


def extract_sampled_frames(video, root, chunk, step_seconds=20, max_frames_per_chunk=60):
    """Use one ffmpeg process to sample a core window, not 30 independent seeks."""
    video,root=Path(video),Path(root)
    if not video.is_file():
        raise FileNotFoundError(video)
    if not (1 <= step_seconds <= 300) or not (1 <= max_frames_per_chunk <= 300):
        raise ValueError('Invalid vision sampling settings')
    start,end=chunk['core_start'],chunk['core_end']
    if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or not 0 <= start < end:
        raise ValueError('Invalid core window')
    folder=root/batch_frames_dir(chunk)
    folder.mkdir(parents=True,exist_ok=True)
    # Never trust stale output on reruns with another film/parameter.
    for old in folder.glob('frame_*.jpg'):
        old.unlink()
    length=float(end)-float(start)
    expected=min(max_frames_per_chunk, max(1,math.ceil(length/step_seconds)))
    pattern=folder/'frame_%04d.jpg'
    run_cmd(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
             '-ss',str(start),'-i',str(video),'-t',str(length),
             '-vf',f'fps=1/{step_seconds},scale=min(960\\,iw):-2',
             '-frames:v',str(expected),'-q:v','4',str(pattern)])
    imgs=sorted(folder.glob('frame_*.jpg'))
    if not imgs:
        raise RuntimeError('FFmpeg produced no frames; no visual understanding can be claimed')
    entries=[]
    for i,path in enumerate(imgs):
        # FFmpeg fps sampling times depend on input timestamps and rounding; these
        # are approximate lookup positions, not exact original source PTS.
        at=min(end, start+(i+0.5)*step_seconds)
        entries.append({'frame_id':f'f{chunk["chunk"]:02d}_{i:04d}',
                        'chunk':chunk['chunk'], 'time_approx_seconds':round(at,3),
                        'time_is_exact_video_pts':False,
                        'path':str(path.relative_to(root)), 'sha256':file_sha256(path)})
    return entries


def validate_vision_response(raw,frames):
    if not isinstance(raw,dict) or not isinstance(raw.get('observations'),list):
        raise ValueError('Vision model must return observations array')
    known={f['frame_id']:f for f in frames}
    results=[];rejected=[];seen=set()
    for i,r in enumerate(raw['observations'][:200]):
        if not isinstance(r,dict) or r.get('frame_id') not in known or r['frame_id'] in seen:
            rejected.append({'item':i,'reason':'UNKNOWN_OR_DUPLICATE_FRAME_ID'});continue
        if r.get('scene_type') not in SCENE_TYPES:
            rejected.append({'item':i,'reason':'INVALID_SCENE_TYPE'});continue
        if type(r.get('related_to_trading_candidate')) is not bool:
            rejected.append({'item':i,'reason':'INVALID_CANDIDATE_BOOLEAN'});continue
        if any(type(r.get(k,'')) is not str for k in ('visible_text_candidate','visual_description_candidate')):
            rejected.append({'item':i,'reason':'INVALID_TEXT'});continue
        seen.add(r['frame_id']); src=known[r['frame_id']]
        results.append({'frame_id':src['frame_id'],'frame_sha256':src['sha256'],
                        'time_approx_seconds':src['time_approx_seconds'],
                        'time_is_exact_video_pts':False,
                        'scene_type_candidate':r['scene_type'],
                        'visible_text_candidate':r.get('visible_text_candidate','')[:1500],
                        'visual_description_candidate':r.get('visual_description_candidate','')[:2500],
                        'related_to_trading_candidate':r['related_to_trading_candidate'],
                        'interpretation_independently_verified':False,
                        'teacher_rule_verified':False,
                        'can_change_artin_engine':False})
    for f in frames:
        if f['frame_id'] not in seen:
            rejected.append({'frame_id':f['frame_id'],'reason':'FRAME_NOT_DESCRIBED'})
    return results,rejected


def scan_vision(root,model,workers=2,step_seconds=20,max_images_per_request=4,
                endpoint='http://127.0.0.1:11434'):
    root=Path(root).resolve();manifest=load_manifest(root)
    src=Path(manifest['video_path_private'])
    if not src.is_file() or file_sha256(src)!=manifest['video_sha256']:
        raise ValueError('Original video is missing or changed')
    if type(model) is not str or not model.strip():
        raise ValueError('An installed local vision model is required')
    if not 1 <= int(max_images_per_request) <= 8:
        raise ValueError('Use at most 8 images per model request')

    def one(chunk):
        frames=extract_sampled_frames(src,root,chunk,step_seconds)
        observations=[];rejected=[]
        for n in range(0,len(frames),max_images_per_request):
            batch=frames[n:n+max_images_per_request]
            prompt=json.dumps({'task':'Describe the visible evidence in EACH of these exact time-sampled frames',
                               'chunk':chunk['chunk'],'frames':[{'frame_id':f['frame_id'],
                               'source_time_approximately_seconds':f['time_approx_seconds']} for f in batch],
                               'do_not_claim_teacher_verification':True},ensure_ascii=False)
            raw=ollama_json(model,prompt,frames=[str(root/f['path']) for f in batch],
                            endpoint=endpoint,system_prompt=VISION_SYSTEM)
            ok,bad=validate_vision_response(raw,batch)
            observations.extend(ok);rejected.extend(bad)
        result={'schema':'artin_sampled_visual_scan_v1','chunk':chunk['chunk'],
                'source_video_sha256':manifest['video_sha256'],
                'sample_every_seconds':step_seconds,'sample_count':len(frames),
                'images_covered_fraction_of_all_video_frames':None,
                'full_video_visual_content_verified':False,
                'visual_model':model,'frames':frames,
                'observations':observations,'rejected_observations':rejected,
                'teacher_rules_verified':0,'can_trade':False}
        atomic_json(root/artifact_path("visual_scans",chunk),result)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(int(workers),len(manifest['chunks'])))) as ex:
        outputs=list(ex.map(one,manifest['chunks']))
    atomic_json(root/'visual_scan_summary.json',{'schema':'artin_visual_scan_summary_v1',
        'source_video_sha256':manifest['video_sha256'],
        'chunks_scanned':len(outputs),
        'frames_extracted':sum(len(d['frames']) for d in outputs),
        'candidate_observations':sum(len(d['observations']) for d in outputs),
        'rejections':sum(len(d['rejected_observations']) for d in outputs),
        'full_teacher_video_understood_and_verified':False,
        'can_change_artin_engine':False})
    return outputs
