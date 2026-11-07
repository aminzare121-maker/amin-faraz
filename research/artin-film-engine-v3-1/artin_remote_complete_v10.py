#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remote user-supplied Uupload classroom video -> complete source ASR/OCR/QA pipeline.

No hardcoded Artin teacher/source ID; result remains private and review-only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from artin_ephemeral_remote_ingest import get_direct_url,download
from artin_generic_video_job_v6 import validate_job
from artin_unified_session_v10 import run_session

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--request",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--model",default="large-v3-turbo")
    a=p.parse_args()
    job=validate_job(json.loads(a.request.read_text(encoding="utf8")))
    if job["mode"]!="SOURCE_AUDIO_AND_CHAT":
        raise ValueError("Whole-session source+speech+OCR+QA requires SOURCE_AUDIO_AND_CHAT")
    a.out.mkdir(parents=True,exist_ok=True)
    url,_=get_direct_url(job["source_url"])
    video=a.out/"original_private_do_not_upload.mp4"
    size,src=download(url,video)
    if job.get("expected_sha256") and job["expected_sha256"]!=src:
        raise ValueError("Original video changed; expected SHA256 mismatch")
    private=a.out/"complete_source_private"
    status=run_session(video,private,sample_seconds=job["sample_seconds"],model_name=a.model)
    if status["source_video_sha256"]!=src or status["global_audio_chunks_total"]!=status["global_audio_chunks_asr_completed"]:
        raise RuntimeError("Full session source consistency failed")
    print("ARTIN_COMPLETE_CLASS_EXECUTED="+json.dumps({
      "job_id":job["job_id"],"source_sha256":src,"original_video_bytes":size,
      "audio_parts_completed":status["global_audio_chunks_asr_completed"],
      "visual_frames_ocr_completed":status["source_screenshots_ocr_completed"],
      "source_qa_linked":status["provisional_question_groups"],
      "semantic_accuracy_independently_measured":False,
      "teacher_rules_approved":0,
      "no_trades_sent":True},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
