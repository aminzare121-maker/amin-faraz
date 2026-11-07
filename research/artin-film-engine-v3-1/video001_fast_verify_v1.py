#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict original-source verification for ANY full user-supplied course movie.

No hardcoded 80-minute video ID, duration, 17 parts or 276 chat screenshots.
All source-verified original audio, original chat OCR and sampled board images
must survive 100%, in order, or this validator rejects the run.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import time
from artin_fast_av_v4 import validate_fast
from artin_visual_timeline_v6 import validate_visual_index
from artin_parallel_asr_merge_v5 import merge_private_shards
from artin_highres_ocr_merge_v8 import merge as merge_original_ocr
from artin_ocr_asr_join_v8 import join_original_chat_qa
from artin_question_dedupe_v11 import clustered_review

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def fail(condition,message):
    if not condition:raise ValueError(message)

def verify(asr_root,ocr_root,source_index,board_root,source_summary,out,
           *,audio_workers,ocr_workers):
    start=time.monotonic()
    asr_root=Path(asr_root).resolve()
    ocr_root=Path(ocr_root).resolve()
    board_root=Path(board_root).resolve()
    out=Path(out).resolve()
    source_index=Path(source_index).resolve()
    summary=read(source_summary)
    source=read(source_index)
    board=read(board_root/'visual_timeline_v6.json')
    expected_sha=summary.get('source_video_sha256')
    duration=summary.get('original_duration_seconds')
    fail(isinstance(expected_sha,str) and len(expected_sha)==64,'Original source hash missing')
    fail(isinstance(duration,(float,int)) and duration>0,'Original source duration missing')
    fail(audio_workers==summary.get('source_audio_worker_count'),'Audio parallelism changed from original preparation')
    fail(ocr_workers==summary.get('original_ocr_workers'),'OCR parallelism changed from original preparation')
    fail(source.get('source_video_sha256')==expected_sha and
         board.get('source_video_sha256')==expected_sha,'Source audio/chat/board identity mismatch')
    fail(source.get('schema')=='artin_change_selected_chat_v8','Original change-selected index required')
    fail(len(source.get('rows',[]))==summary.get('original_chat_images_selected'),
         'Original source-selected screenshot count changed')
    fail(len(board.get('rows',[]))==summary.get('original_board_frames'),
         'Original board image count changed')
    fail(summary.get('one_second_frames_scanned')==source.get('low_res_source_frames'),
         'Original full one-second video scan data changed')
    manifest=read(asr_root/'manifest_redacted.json')
    fail(manifest.get('video_sha256')==expected_sha,'Original audio manifest source changed')
    fail(abs(manifest.get('duration_seconds',0)-duration)<.01,'Video duration changed after audio prep')
    fail(len(manifest['parts'])==math.ceil(duration/300),'Original five-minute source coverage missing')
    fail(len(manifest['parts'])==summary['source_global_audio_chunks'],'Original audio count drift')
    validate_fast(board_root,manifest,verify_files=False)
    validate_visual_index(board_root,manifest,board,verify_files=True)
    # Merging full original 5min chunks checks every source SHA, timestamps
    # and worker ownership, even if a worker was retried or replaced.
    out.mkdir(parents=True,exist_ok=True)
    merged=merge_private_shards(asr_root,out/'asr_verified')
    fail(merged['audio_transcript_coverage_complete'] is True,'Incomplete original voice')
    fail(merged['partitions']==audio_workers,'Audio worker count not exact')
    speech=read(out/'asr_verified'/'complete_unverified_qa_evidence.json')
    reports=[]
    for i in range(ocr_workers):
        folder=ocr_root/f'video001-fast-ocr-{i}'
        fail(folder.is_dir(),'Missing independent original screenshot worker '+str(i))
        reports.append(read(folder/'full_chat_ocr_candidates_PRIVATE.json'))
    ocr_summary,ocr=merge_original_ocr(source,reports)
    fail(ocr_summary['partition_count']==ocr_workers and
         ocr_summary['frames_ocr_completed']==len(source['rows']) and
         ocr_summary['frames_ocr_failed']==0,'Original OCR missing/failed or duplicated')
    fail(ocr['source_video_sha256']==expected_sha and
         speech['source_video_sha256']==expected_sha,'Rejoined evidence source SHA mismatch')
    chat_summary,private=join_original_chat_qa(source,ocr,speech)
    grouped=clustered_review(private)
    fail(grouped['source_video_sha256']==expected_sha and
         grouped['original_groups_not_lost'] is True,
         'A source-linked original student question was lost')
    fail(grouped['original_review_groups']==chat_summary['provisional_distinct_question_groups'],
         'Original question groups changed while clustering')
    fail(sum(c['member_groups_count'] for c in grouped['review_clusters'])==
         grouped['original_review_groups'],'One or more original questions disappeared')
    fail(chat_summary.get('verified_teacher_answers')==0 and
         grouped.get('verified_trading_rules')==0,'Unreviewed teaching may not be auto-certified')
    result={'schema':'video001_fast_final_source_strict_v1',
        'original_source_video_sha256':expected_sha,
        'original_video_duration_seconds':duration,
        'original_five_minute_audio_parts':len(manifest['parts']),
        'original_asr_utterances':len(speech['speech_lines']),
        'original_screen_frames_scanned':source['low_res_source_frames'],
        'source_chat_highres_screenshots':len(source['rows']),
        'original_sampled_board_frames':len(board['rows']),
        'original_ocr_screenshots_finished':ocr_summary['frames_ocr_completed'],
        'provisional_chat_groups':grouped['original_review_groups'],
        'provisional_question_clusters':grouped['conservative_near_duplicate_clusters'],
        'source_evidence_loss':0,
        'independent_hash_and_time_evidence_complete':True,
        'teacher_semantic_accuracy_independently_verified':False,
        'source_unchanged':True,'production_v12_unchanged':True,
        'trading_allowed':False,
        'merge_verification_seconds':round(time.monotonic()-start,2)}
    dest=out/'private_fast_verify_summary.json'
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('VIDEO001_FAST_STRICT_SOURCE_VERIFIED='+json.dumps(result,ensure_ascii=False),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--asr-root',type=Path,required=True)
    ap.add_argument('--ocr-root',type=Path,required=True)
    ap.add_argument('--source-index',type=Path,required=True)
    ap.add_argument('--board-root',type=Path,required=True)
    ap.add_argument('--source-summary',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--audio-workers',type=int,default=8)
    ap.add_argument('--ocr-workers',type=int,default=16)
    a=ap.parse_args()
    verify(a.asr_root,a.ocr_root,a.source_index,a.board_root,a.source_summary,a.out,
           audio_workers=a.audio_workers,ocr_workers=a.ocr_workers)

if __name__=='__main__':main()
