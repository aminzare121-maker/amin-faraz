#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VIDEO-001 V13 ACTIVE single-pass source preparation. Original movie and V12 are untouched.

Prepare full original five-minute-overlap audio, every one-second chat-change
index, all source-selected high-resolution chat images, and complete regularly
sampled classroom board+frame evidence. Partition only DELIVERY, not sampling.
No OCR, ASR or trading-rule inference occurs in preparation.

V13 uses the tested one-decode visual scanner. Speech ASR, visual OCR and teacher verification remain separate.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from artin_film_pipeline import file_sha256
from video001_v13_visual_bridge import scan_chat_and_board_once, create_compatible_board_index
from artin_fast_av_v4 import fast_prepare,validate_fast
from artin_chat_temporal_v8 import collect_index,raw_gray_frames
from artin_chat_change_highres_v8 import collect as capture_chat
from artin_visual_timeline_v6 import extract_visual_timeline,validate_visual_index

def write_json(dest, payload):
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix('.pending')
    temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(temp,dest)

def _copy_sha_file(src,dst,digest):
    src=Path(src).resolve();dst=Path(dst).resolve()
    if not src.is_file() or file_sha256(src)!=digest:
        raise ValueError('Original evidence file absent or hash changed')
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    if file_sha256(dst)!=digest:
        raise ValueError('Copied evidence file not byte-identical')

def _inside(root,relative):
    root=Path(root).resolve()
    dest=(root/relative).resolve()
    if not dest.is_relative_to(root):
        raise ValueError('Original evidence path attempted directory escape')
    return dest

def prepare(video,out,*,audio_workers=17,ocr_workers=16,
            sample_seconds=30,expected_sha=None,chat_max_selected=10000):
    start=time.monotonic()
    video=Path(video).resolve()
    out=Path(out).resolve()
    if not video.is_file() or video.stat().st_size<1024:
        raise ValueError('Actual original video file required')
    if out==video or out==video.parent or video.is_relative_to(out):
        raise ValueError('Output must not overwrite original movie')
    if type(audio_workers) is not int or not 1<=audio_workers<=17:
        raise ValueError('Audio worker count must be 1..17 on this 80m benchmark')
    if type(ocr_workers) is not int or not 1<=ocr_workers<=16:
        raise ValueError('OCR worker count must be 1..16')
    if type(sample_seconds) is not int or not 5<=sample_seconds<=120:
        raise ValueError('Preserve original visual sample interval')
    sha=file_sha256(video)
    if expected_sha and sha!=expected_sha:
        raise ValueError('Original user movie SHA-256 mismatch')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError('V13_REQUIRES_EMPTY_NEW_DESTINATION_NOT_AN_ARCHIVE')
    out.mkdir(parents=True,exist_ok=True)
    # V13 active accelerated path: one verified video decode now handles both
    # chat-change scanning and scheduled board frames, overlapping independent
    # unchanged audio extraction. New output path, NEVER an existing V12 archive.
    def audio_task():
        return fast_prepare(video,out/'full_audio',workers=4,frames_per_part=2)
    from artin_film_pipeline import probe_video
    duration_probe=probe_video(video)
    def visual_task():
        return scan_chat_and_board_once(
            video,out/'v13_one_pass',sha,float(duration_probe[0]))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        audio_future=pool.submit(audio_task)
        visual_future=pool.submit(visual_task)
        manifest=audio_future.result()
        timeline,visual_metrics=visual_future.result()
    validate_fast(out/'full_audio',manifest,verify_files=True)
    if manifest['video_sha256']!=sha:
        raise ValueError('V13_AUDIO_SOURCE_IDENTITY_CHANGED')
    if timeline['source_video_sha256']!=sha:
        raise ValueError('V13_CHAT_SOURCE_IDENTITY_CHANGED')
    write_json(out/'original_second_by_second_chat_index.json',timeline)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        board_future=pool.submit(create_compatible_board_index,
            out/'v13_one_pass',out/'full_board',manifest,visual_metrics)
        chat_future=pool.submit(capture_chat,video,timeline,
            out/'full_chat',workers=4,max_selected=chat_max_selected)
        board=board_future.result()
        chat=chat_future.result()
    if file_sha256(video)!=sha:
        raise ValueError('Original video was modified during source preparation')
    validate_visual_index(out/'full_board',manifest,board,verify_files=True)
    if chat['source_video_sha256']!=sha or board['source_video_sha256']!=sha:
        raise ValueError('Original board/chat SHA does not equal speech video')
    # Scheduler adapts only worker count for short lessons; NEVER changes
    # original five-minute source parts or drops even one selected chat image.
    audio_workers=min(audio_workers,len(manifest['parts']))
    ocr_workers=min(ocr_workers,len(chat['rows']))
    if audio_workers<1 or ocr_workers<1:
        raise ValueError('Original lesson contains no valid worker assignments')
    # One sanitized full manifest; only original audio payload files are
    # partitioned by global source-chunk index. Each separate worker gets ONE
    # small shard, never downloads the full movie or unrelated source audio.
    manifest=json.loads(json.dumps(manifest))
    manifest.pop('video_path_private',None)
    manifest['verified_original_movie_bytes']=video.stat().st_size
    for i in range(audio_workers):
        folder=out/'asr_shards'/f'worker_{i:02d}'
        write_json(folder/'fast_av_manifest.json',manifest)
        target=[p for p in manifest['parts'] if (p['chunk']-1)%audio_workers==i]
        if not target:raise ValueError('Empty audio worker shard')
        for part in target:
            src=_inside(out/'full_audio',part['audio'])
            dst=_inside(folder,part['audio'])
            _copy_sha_file(src,dst,part['audio_sha256'])
    for i in range(ocr_workers):
        folder=out/'ocr_shards'/f'worker_{i:02d}'
        write_json(folder/'chat_selected_index.json',chat)
        target=[r for n,r in enumerate(chat['rows']) if n%ocr_workers==i]
        if not target:raise ValueError('Empty OCR worker shard')
        for r in target:
            src=_inside(out/'full_chat',r['chat']['path'])
            dst=_inside(folder,r['chat']['path'])
            _copy_sha_file(src,dst,r['chat']['sha256'])
    write_json(out/'board_review'/'visual_timeline_v6.json',board)
    for row in board['rows']:
        for mode in ('video_frame','board','chat'):
            obj=row[mode]
            _copy_sha_file(_inside(out/'full_board',obj['path']),
                           _inside(out/'board_review',obj['path']),
                           obj['sha256'])
    # An isolated provenance index for the final join. No raw class speech or
    # personal chat text is put in public logs.
    summary={'schema':'video001_fast_source_once_v1',
      'source_video_sha256':sha,'original_movie_bytes':video.stat().st_size,
      'original_duration_seconds':manifest['duration_seconds'],
      'source_global_audio_chunks':len(manifest['parts']),
      'v13_one_pass_visual_enabled':True,
      'v13_real_one_pass_visual_seconds':visual_metrics['elapsed_seconds'],
      'v13_legacy_archives_overwritten':False,
      'source_audio_worker_count':audio_workers,
      'one_second_frames_scanned':timeline['sampled_source_frames'],
      'original_chat_images_selected':len(chat['rows']),
      'original_board_frames':len(board['rows']),
      'original_ocr_workers':ocr_workers,
      'source_integrity_verified':True,
      'original_movie_transcoded':False,
      'source_speech_modified':False,
      'source_screen_text_generated':False,
      'teacher_semantics_verified':False,
      'all_original_audio_parts_assigned_once':sum(
          sum((p['chunk']-1)%audio_workers==i for p in manifest['parts'])
          for i in range(audio_workers))==len(manifest['parts']),
      'all_original_chat_images_assigned_once':sum(
          sum(n%ocr_workers==i for n in range(len(chat['rows'])))
          for i in range(ocr_workers))==len(chat['rows']),
      'elapsed_seconds':round(time.monotonic()-start,2)}
    write_json(out/'safe_source_prep_summary.json',summary)
    print('VIDEO001_FAST_SOURCE_ONCE_PREPARED='+json.dumps(summary,ensure_ascii=False),flush=True)
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected-sha256',default=None)
    p.add_argument('--audio-workers',type=int,default=17)
    p.add_argument('--ocr-workers',type=int,default=16)
    p.add_argument('--sample-seconds',type=int,default=30)
    a=p.parse_args()
    prepare(a.video,a.out,expected_sha=a.expected_sha256,
        audio_workers=a.audio_workers,ocr_workers=a.ocr_workers,
        sample_seconds=a.sample_seconds)

if __name__=='__main__':main()
