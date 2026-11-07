#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export source-once FAST evidence to VIDEO-001 V12's existing private review contract.

The fast pipeline's independent SHA/time verification must have passed first.
No speech, OCR, teacher answer or trading rule is invented or promoted.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

from artin_highres_ocr_merge_v8 import merge as merge_ocr
from artin_ocr_asr_join_v8 import join_original_chat_qa
from artin_question_dedupe_v11 import clustered_review
from artin_fidelity_audit_v7 import audit_original_teacher_evidence

def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def write(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf8")

def export(*,proof_path,source_path,asr_path,ocr_root,chat_index,board_root,
           temporal_index,chat_images,out,audio_workers,ocr_workers):
    proof=read(proof_path)
    source=read(source_path)
    speech=read(asr_path)
    index=read(chat_index)
    board=read(Path(board_root)/"visual_timeline_v6.json")
    timeline=read(temporal_index)
    sha=source["source_video_sha256"]
    if (not proof.get("independent_hash_and_time_evidence_complete") or
        proof["original_source_video_sha256"]!=sha or
        any(obj["source_video_sha256"]!=sha for obj in (speech,index,board,timeline))):
        raise ValueError("V12 FAST provenance fails before export")
    if (audio_workers!=source["source_audio_worker_count"] or
        ocr_workers!=source["original_ocr_workers"] or
        speech["parts_with_asr"]!=source["source_global_audio_chunks"] or
        speech["parts_missing_asr"]!=0):
        raise ValueError("V12 FAST missing source audio")
    results=[]
    for i in range(ocr_workers):
        row=Path(ocr_root)/f"video001-fast-ocr-{i}"/"full_chat_ocr_candidates_PRIVATE.json"
        if not row.is_file():raise ValueError("Missing OCR worker output "+str(i))
        results.append(read(row))
    ocr_summary,full_ocr=merge_ocr(index,results)
    if (ocr_summary["frames_ocr_completed"]!=len(index["rows"]) or
        ocr_summary["frames_ocr_failed"]!=0):
        raise ValueError("V12 FAST missing original chat frame")
    chat_summary,chat_private=join_original_chat_qa(index,full_ocr,speech)
    clusters=clustered_review(chat_private)
    fidelity_summary,fidelity_private=audit_original_teacher_evidence(speech,board)
    if (clusters["source_video_sha256"]!=sha or
        clusters["original_groups_not_lost"] is not True or
        clusters["original_review_groups"]!=chat_summary["provisional_distinct_question_groups"] or
        fidelity_summary["verified_trading_rules"] or
        chat_summary["verified_teacher_answers"]):
        raise ValueError("V12 FAST attempted to omit or certify unreviewed material")
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Refuse to overwrite an existing V12 source review")
    out.mkdir(parents=True,exist_ok=True)
    write(out/"private_original_asr_review.json",speech)
    write(out/"private_visual_timeline.json",board)
    write(out/"private_second_by_second_chat_index.json",timeline)
    write(out/"private_chat_capture_index.json",index)
    write(out/"private_question_audio_REVIEW_ONLY.json",chat_private)
    write(out/"private_question_clusters_REVIEW_ONLY.json",clusters)
    write(out/"private_unverified_rule_context.json",fidelity_private)
    write(out/"private_ocr"/"full_chat_ocr_candidates_PRIVATE.json",full_ocr)
    # Keep original classroom screenshots, not screenshots regenerated from OCR text.
    if not Path(chat_images).is_dir() or not list(Path(chat_images).rglob("*.png")):
        raise ValueError("Original high-resolution chat screenshots missing")
    shutil.copytree(Path(chat_images),out/"visual_change",dirs_exist_ok=True)
    shutil.copytree(Path(board_root),out/"visual",dirs_exist_ok=True)
    # Fail if any source-selected image is missing after transfer.
    for row in index["rows"]:
        p=out/"visual_change"/row["chat"]["path"]
        if not p.is_file():
            raise ValueError("Source chat screenshot missing during V12 compatibility export")
    safe={
       "schema":"artin_unified_complete_session_v10",
       "source_video_sha256":sha,
       "original_video_duration_seconds":source["original_duration_seconds"],
       "global_audio_chunks_total":source["source_global_audio_chunks"],
       "global_audio_chunks_asr_completed":speech["parts_with_asr"],
       "timestamped_source_asr_utterances":len(speech["speech_lines"]),
       "one_second_chat_frames_scanned":source["one_second_frames_scanned"],
       "one_second_chat_changed_frames":timeline["changed_chat_frames"],
       "original_source_board_screenshots":len(board["rows"]),
       "original_source_chat_screenshots":len(index["rows"]),
       "source_screenshots_ocr_completed":ocr_summary["frames_ocr_completed"],
       "source_screenshots_ocr_errors":ocr_summary["frames_ocr_failed"],
       "screenshots_with_text_candidates":ocr_summary["frames_containing_some_ocr_text"],
       "provisional_question_groups":chat_summary["provisional_distinct_question_groups"],
       "conservative_question_review_clusters":clusters["conservative_near_duplicate_clusters"],
       "all_original_question_observations_retained":True,
       "rule_fragments_incomplete":fidelity_summary["legacy_rule_candidate_count"],
       "all_source_coverage_stages_ran":True,
       "human_verified_speech_accuracy":None,
       "human_verified_screen_text_accuracy":None,
       "human_verified_teacher_answer_count":0,
       "teacher_chart_meaning_verified":False,
       "source_verified_trading_rules":0,
       "demo_trades_allowed":False,
       "real_trades_allowed":False,
       "runtime_seconds":None,
       "fast_engine":{"asr_workers":audio_workers,"ocr_workers":ocr_workers,
                      "original_source_sha256":sha,
                      "independent_evidence_verification":True,
                      "legacy_export_status":"COMPLETE"},
       "state":"SOURCE_PIPELINE_DONE_SEMANTIC_TRUTH_NOT_CERTIFIED"
    }
    write(out/"safe_session_result.json",safe)
    print("VIDEO001_V12_FAST_FULL_REVIEW_EXPORT_SUCCESS="+json.dumps({
       "source_sha256":sha,"audio_parts":speech["parts_with_asr"],
       "ocr_frames":ocr_summary["frames_ocr_completed"],
       "board_frames":len(board["rows"]),
       "question_groups":chat_summary["provisional_distinct_question_groups"],
       "rules_verified":0,"legacy_layout_preserved":True
    },ensure_ascii=False),flush=True)
    return safe

def main():
    p=argparse.ArgumentParser()
    for name in ("proof-path","source-path","asr-path","ocr-root",
                 "chat-index","board-root","temporal-index","chat-images","out"):
        p.add_argument("--"+name,required=True,type=Path)
    p.add_argument("--audio-workers",type=int,required=True)
    p.add_argument("--ocr-workers",type=int,required=True)
    a=p.parse_args()
    export(**vars(a))

if __name__=="__main__":
    main()
