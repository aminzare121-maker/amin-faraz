#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fast, evidence-only first pass for arbitrary-length classroom recordings.

Avoid transcoding video. Preserve original source as the authoritative timeline;
extract accurate audio windows and sampled image frames for analysis.
Audio/video understanding is NOT provided by this step.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import subprocess
import tempfile
import time
from pathlib import Path

from artin_batch_slots import annotate_plan, batch_summary
from artin_film_pipeline import chunk_plan, file_sha256, probe_video


class SourceEvidenceError(ValueError):
    pass


def _exec(command):
    p = subprocess.run(command, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(f'{command[0]} exited {p.returncode}: {p.stderr[-700:]}')
    return p.stdout


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf8', dir=path.parent,
                                     prefix='.pending-', suffix='.json', delete=False) as temp:
        json.dump(data, temp, ensure_ascii=False, indent=2)
        temp.write('\n')
        temp_path = Path(temp.name)
    os.replace(temp_path, path)


def _key(part):
    return f"b{part['batch']:03d}_s{part['slot']:02d}_g{part['chunk']:06d}"


def plan_fast(duration: float, frames_per_part: int = 2, overlap: int = 12):
    if type(frames_per_part) is not int or not 0 <= frames_per_part <= 30:
        raise SourceEvidenceError('Invalid frame count')
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise SourceEvidenceError('Invalid duration')
    plan = chunk_plan(float(duration), 300, overlap)
    for chunk in plan:
        chunk['audio'] = f"audio/batch_{chunk['batch']:03d}/part_{chunk['slot']:02d}.wav"
        chunk['frames'] = []
        size = chunk['core_end'] - chunk['core_start']
        for j in range(frames_per_part):
            at = chunk['core_start'] + size * (j + .5) / frames_per_part
            chunk['frames'].append({'time_approx':round(at,3),
                'path': f"frames/batch_{chunk['batch']:03d}/{_key(chunk)}_f{j+1:02d}.jpg"})
    return plan


def _one(video: Path, root: Path, item: dict):
    out = json.loads(json.dumps(item))
    audio = root / out['audio']
    audio.parent.mkdir(parents=True, exist_ok=True)
    dur = out['cut_end'] - out['cut_start']
    _exec(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
           '-ss', str(out['cut_start']),'-i',str(video),'-t',str(dur),
           '-map','0:a:0','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le', str(audio)])
    out['audio_sha256']=file_sha256(audio)
    audio_seconds = float(json.loads(_exec(['ffprobe','-v','error','-show_entries',
                'format=duration','-of','json',str(audio)]))['format']['duration'])
    if abs(audio_seconds - dur) > 1.0:
        raise SourceEvidenceError('Audio segment duration diverges from source timeline')
    out['audio_duration_seconds']=round(audio_seconds,3)
    for fr in out['frames']:
        path=root/fr['path']
        path.parent.mkdir(parents=True,exist_ok=True)
        _exec(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
               '-ss',str(fr['time_approx']),'-i',str(video),'-frames:v','1',
               '-vf','scale=min(960\\,iw):-2','-q:v','5',str(path)])
        if not path.is_file() or path.stat().st_size < 80:
            raise SourceEvidenceError('A sampled visual frame is missing or empty')
        fr['sha256']=file_sha256(path)
        fr['visual_interpretation_verified']=False
    return out


def validate_fast(root: Path, manifest: dict, verify_files: bool = True):
    chunks = manifest.get('parts')
    if not isinstance(chunks,list) or not chunks:
        raise SourceEvidenceError('No fast media parts')
    expected = plan_fast(manifest['duration_seconds'],manifest['frames_per_part'],manifest['overlap_s'])
    if len(expected)!=len(chunks):
        raise SourceEvidenceError('Missing or extra five-minute parts')
    if manifest.get('batches')!=batch_summary(chunks):
        raise SourceEvidenceError('Wrong batch index')
    for i, (planned, current) in enumerate(zip(expected,chunks),1):
        for key in ('chunk','batch','slot','unique_id','cut_start','cut_end','core_start','core_end','audio'):
            if current.get(key)!=planned.get(key):
                raise SourceEvidenceError(f'Part {i} failed identity or time check: {key}')
        if len(current.get('frames',[]))!=len(planned['frames']):
            raise SourceEvidenceError(f'Part {i} is missing sampled frames')
        paths=[(current['audio'],current.get('audio_sha256'))]
        for fr, reference in zip(current['frames'],planned['frames']):
            if fr.get('path')!=reference['path'] or fr.get('time_approx')!=reference['time_approx']:
                raise SourceEvidenceError(f'Part {i} visual frame was relabeled')
            paths.append((fr['path'],fr.get('sha256')))
        if verify_files:
            for filename, sha in paths:
                path=(Path(root)/filename).resolve()
                if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
                    raise SourceEvidenceError(f'Part {i} file missing: {filename}')
                if sha!=file_sha256(path):
                    raise SourceEvidenceError(f'Part {i} content hash mismatch: {filename}')
    return True


def fast_prepare(video: Path, root: Path, *, workers: int = 4,
                 frames_per_part: int = 2, overlap: int = 12):
    video=Path(video).resolve()
    root=Path(root).resolve()
    if not video.is_file():raise FileNotFoundError(video)
    if root==video.parent or root==video:
        raise SourceEvidenceError('Output folder must be separate from source directory')
    if not 1 <= int(workers) <= 32:raise SourceEvidenceError('Workers must be between 1 and 32')
    root.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    duration, streams=probe_video(video)
    if 'audio' not in streams:
        raise SourceEvidenceError('Real speech analysis requires an audio track')
    video_sha=file_sha256(video)
    manifest_path=root/'fast_av_manifest.json'
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text(encoding='utf8'))
        if old.get('video_sha256')!=video_sha:
            raise SourceEvidenceError('Output directory belongs to a different source video')
    parts=plan_fast(duration,frames_per_part,overlap)
    _save_json(root/'fast_plan_pending.json',{
         'status':'NOT_YET_EXTRACTED','video_sha256':video_sha,
         'sequence':[{'id':x['unique_id'],'core_start':x['core_start'],
                     'core_end':x['core_end']} for x in parts]})
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(int(workers),len(parts))) as pool:
        fs={pool.submit(_one,video,root,p):p['chunk'] for p in parts}
        completed={}
        for future in concurrent.futures.as_completed(fs):
            completed[fs[future]]=future.result()
    ordered=[completed[i] for i in range(1,len(parts)+1)]
    result={'schema':'artin_fast_av_v4','mode':'AUDIO_PLUS_VISUAL_EVIDENCE_NO_MP4_REENCODE',
            'video_sha256':video_sha,'video_path_private':str(video),
            'duration_seconds':duration,'source_streams':streams,
            'overlap_s':overlap,'frames_per_part':frames_per_part,
            'parts_ready':len(ordered),'batches':batch_summary(ordered),
            'parts':ordered,'elapsed_seconds':round(time.monotonic()-start,3),
            'audio_transcribed':False,'images_understood':False,'teacher_rules_verified':0,
            'artin_trading_engine_changed':False}
    validate_fast(root,result)
    _save_json(manifest_path,result)
    (root/'fast_plan_pending.json').unlink(missing_ok=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--frames-per-part',type=int,default=2)
    a=p.parse_args()
    m=fast_prepare(a.video,a.out,workers=a.workers,frames_per_part=a.frames_per_part)
    print(json.dumps({'schema':m['schema'],'duration':m['duration_seconds'],
          'parts_ready':m['parts_ready'],'batches':len(m['batches']),
          'elapsed_seconds':m['elapsed_seconds'],
          'last_part_seconds':m['parts'][-1]['core_end']-m['parts'][-1]['core_start'],
          'video_transcoded':False,'teacher_rules_verified':0},ensure_ascii=False))


if __name__=='__main__':main()