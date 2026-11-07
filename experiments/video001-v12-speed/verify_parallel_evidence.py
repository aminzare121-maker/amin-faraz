#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-preserving independent verification of 8x8 experimental outputs.

Use only real SHA-linked original ASR/OCR evidence. Never infer speech or
invent corrections. Does not mutate the production VIDEO-001 registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
ENGINE=ROOT/'research'/'artin-film-engine-v3-1'
sys.path.insert(0,str(ENGINE))
from artin_parallel_asr_merge_v5 import merge_private_shards
from artin_highres_ocr_merge_v8 import merge as merge_ocr
from artin_ocr_asr_join_v8 import join_original_chat_qa
from artin_question_dedupe_v11 import clustered_review

EXPECTED='b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def verify(asr_root:Path,ocr_root:Path,source_index:Path,out:Path,*,asr_workers:int=8,ocr_workers:int=8):
    start=time.monotonic()
    out.mkdir(parents=True,exist_ok=True)
    # GitHub download-artifact names the subfolders by ARTIFACT name.
    # The original OCR merger requires shard_0..shard_7. Instead of changing
    # original code, create stable links to original immutable output folders.
    if asr_workers not in (8,17) or ocr_workers not in (8,16):
        raise ValueError('Only explicitly tested 8+8 / 17+16 splits allowed')
    for shard in range(ocr_workers):
        original=ocr_root/f'speed-V12-OCR-{ocr_workers}-{shard}'
        expected=ocr_root/f'shard_{shard}'
        if not original.is_dir():
            raise FileNotFoundError('Missing original OCR worker folder '+str(shard))
        if expected.exists() or expected.is_symlink():
            raise ValueError('Unexpected pre-existing OCR worker alias')
        expected.symlink_to(original, target_is_directory=True)
    source=read(source_index)
    if source.get('source_video_sha256')!=EXPECTED:
        raise ValueError('Original source SHA mismatch before any merge')
    if len(source.get('rows',[]))!=276:
        raise ValueError('Expected original 276 selected high-resolution frames')
    a=merge_private_shards(asr_root,out/'merged_asr')
    reports=[read(ocr_root/f'shard_{n}'/'full_chat_ocr_candidates_PRIVATE.json') for n in range(ocr_workers)]
    summary,ocr=merge_ocr(source,reports)
    if summary['frames_ocr_failed'] or summary['frames_ocr_completed']!=276:
        raise RuntimeError('Missing/failed OCR original image')
    speech=read(out/'merged_asr'/'complete_unverified_qa_evidence.json')
    if speech['source_video_sha256']!=EXPECTED or ocr['source_video_sha256']!=EXPECTED:
        raise ValueError('Merged output original source identity differs')
    if speech['parts_with_asr']!=17 or speech['parts_missing_asr']:
        raise ValueError('Not all original audio segments processed')
    qa,private=join_original_chat_qa(source,ocr,speech)
    groups=clustered_review(private)
    if (groups['original_review_groups']!=len(private['question_groups'])
        or sum(x['member_groups_count'] for x in groups['review_clusters'])
           !=groups['original_review_groups']
        or not groups['original_groups_not_lost']):
        raise ValueError('Source observations were dropped during grouping')
    if qa['verified_teacher_answers'] or groups['verified_trading_rules']:
        raise ValueError('No model can certify teacher or trading rules')
    result={
        'schema':'video001_8way_real_source_benchmark_complete_v1',
        'source_video_sha256':EXPECTED,'original_film_duration_s':4820.5452,
        'speech_workers':asr_workers,'image_ocr_workers':ocr_workers,
        'original_asr_parts':17,'original_chat_frames_selected':276,
        'asr_utterances':len(speech['speech_lines']),
        'provisional_question_groups':len(private['question_groups']),
        'review_clusters':groups['conservative_near_duplicate_clusters'],
        'original_groups_lost':0,'source_integrity_checked':True,
        'semantic_meaning_accuracy_independently_measured':False,
        'production_video001_v12_mutated':False,
        'trade_permissions_granted':False,'verification_runtime_s':round(time.monotonic()-start,2)
    }
    (out/'safe_speed_validation.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('VIDEO001_PARALLEL_REAL_SOURCE_VERIFIED='+json.dumps(result,ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--asr-root',type=Path,required=True)
    p.add_argument('--ocr-root',type=Path,required=True)
    p.add_argument('--source-index',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--asr-workers',type=int,default=8)
    p.add_argument('--ocr-workers',type=int,default=8)
    args=p.parse_args()
    verify(args.asr_root,args.ocr_root,args.source_index,args.out,
           asr_workers=args.asr_workers,ocr_workers=args.ocr_workers)


if __name__=='__main__':main()
