#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed recombination of four independent, source-hashed V8 OCR workers.

Every source chat screenshot must be processed exactly once, by its assigned
worker, in original movie order. No content is trusted as a verified message,
teacher answer, or trade rule.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from artin_persian_full_chat_ocr_v7 import write_atomic


def merge(index, reports):
    if index.get("schema")!="artin_change_selected_chat_v8":
        raise ValueError("Expected original change-selected high-resolution chat index")
    source=index.get("source_video_sha256")
    rows=index.get("rows")
    if not isinstance(source,str) or len(source)!=64 or not isinstance(rows,list) or not rows:
        raise ValueError("Missing original video identity or selected source frames")
    if not isinstance(reports,list) or not reports:
        raise ValueError("OCR worker reports required")
    count=len(reports)
    seen_workers=set();found={}
    for part in reports:
        if part.get("schema")!="artin_full_original_chat_ocr_v7":
            raise ValueError("Unrecognized OCR worker output")
        idx=part.get("partition_index")
        if type(idx) is not int or not 0<=idx<count or idx in seen_workers:
            raise ValueError("Duplicate, missing or mismatched OCR worker")
        seen_workers.add(idx)
        if part.get("partition_count")!=count or part.get("source_video_sha256")!=source:
            raise ValueError("Wrong original-video SHA or worker split count")
        if part.get("complete") is not True or part.get("frames_attempted")!=part.get("frames_targeted"):
            raise ValueError("Worker did not complete every assigned source screenshot")
        assigned=[row for i,row in enumerate(rows) if i%count==idx]
        observations=part.get("results")
        if part.get("frames_total")!=len(rows) or part.get("frames_targeted")!=len(assigned) or not isinstance(observations,list) or len(observations)!=len(assigned):
            raise ValueError("OCR worker did not produce complete assigned frame results")
        for original,result in zip(assigned,observations):
            fid=original["frame_id"]
            if (result.get("frame_id")!=fid or
                result.get("source_frame_sha256")!=original["chat"]["sha256"] or
                result.get("time_original_video_seconds")!=original["time_seconds"] or
                result.get("global_chunk")!=original["global_chunk"] or
                fid in found):
                raise ValueError("OCR output did not match source frame identity, time or SHA")
            if result.get("state") not in ("OCR_FAILED_REVIEW_REQUIRED","OCR_NO_READABLE_TEXT","OCR_TEXT_CANDIDATES"):
                raise ValueError("Invented OCR state")
            if result.get("source_text_verified") is True or result.get("teacher_answer_verified") is True:
                raise ValueError("Machine OCR cannot self-certify source text or teacher answer")
            found[fid]=result
    if seen_workers!=set(range(count)) or len(found)!=len(rows):
        raise ValueError("Incomplete worker set")
    full=[found[row["frame_id"]] for row in rows]
    failed=sum(x["state"]=="OCR_FAILED_REVIEW_REQUIRED" for x in full)
    summary={"schema":"artin_verified_source_join_ocr_v8",
      "source_video_sha256":source,
      "full_original_chat_frames_selected":len(rows),
      "frames_ocr_completed":len(full),
      "frames_containing_some_ocr_text":sum(x["state"]=="OCR_TEXT_CANDIDATES" for x in full),
      "frames_no_text":sum(x["state"]=="OCR_NO_READABLE_TEXT" for x in full),
      "frames_ocr_failed":failed,
      "frames_with_question_mark_candidates":sum(bool(x.get("possible_typed_questions")) for x in full),
      "partition_count":count,
      "text_human_verified":0,
      "teacher_answers_verified":0,
      "teacher_rules_executable":0,
      "covers_each_video_frame":False,
      "accurate_ocr_was_measured_against_gold_reference":False,
      "status":"REVIEW_REQUIRED" if failed else "SOURCE_VALIDATED_OCR_CANDIDATES"}
    private={"schema":"artin_full_original_chat_ocr_v7",
       "source_video_sha256":source,
       "frames_total":len(rows),"frames_targeted":len(rows),
       "frames_attempted":len(rows),"complete":True,
       "human_verified_chat_messages":0,"teacher_answers_verified":0,
       "rules_executable":0,"results":full}
    return summary,private


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selected-index",type=Path,required=True)
    p.add_argument("--parts-root",type=Path,required=True)
    p.add_argument("--partitions",type=int,default=4)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    source=json.loads(a.selected_index.read_text(encoding="utf8"))
    reports=[]
    for n in range(a.partitions):
        file=a.parts_root/f"shard_{n}"/"full_chat_ocr_candidates_PRIVATE.json"
        reports.append(json.loads(file.read_text(encoding="utf8")))
    summary,full=merge(source,reports)
    a.out.mkdir(parents=True,exist_ok=True)
    write_atomic(a.out/"merged_source_chat_ocr_summary_safe.json",summary)
    write_atomic(a.out/"merged_source_chat_ocr_PRIVATE.json",full)
    print("ARTIN_V8_HIGHRES_OCR_MERGE="+json.dumps(summary,ensure_ascii=False),flush=True)
    if summary["frames_ocr_failed"]:
        raise SystemExit(2)

if __name__=="__main__":main()
