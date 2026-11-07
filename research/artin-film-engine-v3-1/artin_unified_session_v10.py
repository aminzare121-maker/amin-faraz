#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified source-verified classroom session: video -> ASR + visuals + OCR + Q&A.

Unlike source_ingest V6, this actually performs ASR and OCR for EVERY original
5-minute part and screenshot. A session is never called processed if a stage
is skipped/failed. Accuracy of transcription/teacher understanding remains
UNVERIFIED pending independent source labels. NO trading or source writes.

The original lesson must be authorized by the user; downloading links and
saving original media are handled by the private runner.
"""
from __future__ import annotations
import argparse
import json
import math
import time
from pathlib import Path

from artin_film_pipeline import file_sha256
from artin_fast_av_v4 import fast_prepare,validate_fast
from artin_real_asr_trial_v5 import read_pcm_array
from artin_teacher_av_review_v5 import review_real_asr
from artin_visual_timeline_v6 import extract_visual_timeline
from artin_persian_full_chat_ocr_v7 import ocr_frames
from artin_ocr_asr_join_v8 import join_original_chat_qa
from artin_fidelity_audit_v7 import audit_original_teacher_evidence


def _write(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".incomplete")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf8")
    temp.replace(path)


def run_session(video,output,*,whisper_model_factory=None,ocr_model_factory=None,
                sample_seconds=30,model_name="large-v3-turbo",
                asr_cpu_threads=4):
    """Actual one-session processing. Output is private, fail-closed and source-linked."""
    video=Path(video).resolve()
    output=Path(output).resolve()
    if not video.is_file() or video.stat().st_size<1024:
        raise ValueError("Source video not present")
    if type(sample_seconds) is not int or not 5<=sample_seconds<=120:
        raise ValueError("Chat/board sampling interval must be 5..120 seconds")
    if type(asr_cpu_threads) is not int or not 1<=asr_cpu_threads<=16:
        raise ValueError("Unsupported ASR thread count")
    if output==video.parent or video.is_relative_to(output):
        raise ValueError("Output must be separate from private source media")
    source_hash=file_sha256(video)
    started=time.monotonic()
    output.mkdir(parents=True,exist_ok=True)
    # First perform the same cryptographic video -> source chunk verification.
    manifest=fast_prepare(video,output/"fast",workers=4,frames_per_part=2)
    validate_fast(output/"fast",manifest,verify_files=True)
    if manifest["video_sha256"]!=source_hash:
        raise ValueError("Source changed during initial audio/video preparation")
    parts=manifest["parts"]
    if not parts:raise ValueError("No source audio parts extracted")
    if whisper_model_factory is None:
        from faster_whisper import WhisperModel
        whisper_model_factory=WhisperModel
    asr_model=whisper_model_factory(model_name,device="cpu",compute_type="int8",
                                   cpu_threads=asr_cpu_threads,num_workers=1)
    shards=[]
    asr_dir=output/"private_asr"
    for part in parts:
        audio=read_pcm_array(output/"fast"/part["audio"])
        segments,_=asr_model.transcribe(
            audio,language="fa",vad_filter=True,beam_size=5,
            condition_on_previous_text=False,word_timestamps=False)
        utterances=[]
        for i,s in enumerate(segments):
            t0=part["cut_start"]+float(s.start)
            t1=min(part["cut_end"],part["cut_start"]+float(s.end))
            if t1<=t0:continue
            text=str(s.text).strip()
            if not text:continue
            utterances.append({
                "id":f"asr_p{part['chunk']:03d}_{i:05d}",
                "start":round(t0,3),"end":round(t1,3),
                "text":text,"speaker":"UNKNOWN","speaker_verified":False,
                "avg_logprob":round(float(s.avg_logprob),4),
                "no_speech_prob":round(float(s.no_speech_prob),4)})
        shard={"schema":"artin_asr_shard_v5","global_chunk":part["chunk"],
            "source_video_sha256":source_hash,
            "source_audio_sha256":part["audio_sha256"],
            "timebase":"absolute_original_video_seconds",
            "model":model_name,"speaker_human_verified":False,
            "teacher_rules_verified":False,"segments":utterances}
        _write(asr_dir/f"chunk_{part['chunk']:04d}_UNVERIFIED.json",shard)
        shards.append(shard)
        print("ARTIN_REAL_ASR_PART="+json.dumps({
           "part":part["chunk"],"total":len(parts),
           "utterances":len(utterances)},ensure_ascii=False),flush=True)
    if len(shards)!=len(parts):
        raise RuntimeError("Full-video ASR was not processed")
    review=review_real_asr(manifest,shards)
    if review.get("parts_with_asr")!=len(parts) or review.get("parts_missing_asr"):
        raise RuntimeError("Full-video speech source coverage incomplete")
    _write(output/"private_original_asr_review.json",review)
    # Actual original classroom frames, not invented student questions.
    visual=extract_visual_timeline(video,output/"visual",manifest,
                                   sample_seconds=sample_seconds,workers=4)
    if visual.get("source_video_sha256")!=source_hash or not visual.get("rows"):
        raise RuntimeError("Original visual source incomplete")
    _write(output/"private_visual_timeline.json",visual)
    # Independent printed Persian OCR. Private textual evidence not printed in logs.
    ocr=ocr_frames(output/"visual",visual,output/"private_ocr",
                   ocr_factory=ocr_model_factory)
    if ocr.get("ocr_failed_frames"):
        # A failed OCR must never be silently converted into "completed".
        # Keep technical error messages in PRIVATE job logs; never print student
        # or teacher text here.
        failures=json.loads((output/"private_ocr"/"full_chat_ocr_candidates_PRIVATE.json").read_text(encoding="utf8"))
        first=next((x for x in failures.get("results",[])
                    if x.get("state")=="OCR_FAILED_REVIEW_REQUIRED"),{})
        raise RuntimeError("OCR failure: "+str(first.get("error_type","unknown"))+
            ": "+str(first.get("private_diagnostic","unavailable"))[:180])
    if ocr.get("frames_attempted")!=len(visual["rows"]):
        raise RuntimeError("OCR image coverage incomplete")
    full_ocr=json.loads((output/"private_ocr"/"full_chat_ocr_candidates_PRIVATE.json").read_text(encoding="utf8"))
    if full_ocr.get("complete") is not True:
        raise RuntimeError("OCR checkpoint incomplete")
    chat_summary,chat_private=join_original_chat_qa(visual,full_ocr,review)
    _write(output/"private_question_audio_REVIEW_ONLY.json",chat_private)
    fidelity_summary,fidelity_private=audit_original_teacher_evidence(review,visual)
    _write(output/"private_unverified_rule_context.json",fidelity_private)
    if chat_summary["verified_teacher_answers"] or fidelity_summary["verified_trading_rules"]:
        raise RuntimeError("Unverified models cannot self-approve teacher answers or trading rules")
    safe={"schema":"artin_unified_complete_session_v10",
        "source_video_sha256":source_hash,
        "original_video_duration_seconds":manifest["duration_seconds"],
        "global_audio_chunks_total":len(parts),
        "global_audio_chunks_asr_completed":len(shards),
        "timestamped_source_asr_utterances":len(review["speech_lines"]),
        "original_source_chat_screenshots":len(visual["rows"]),
        "source_screenshots_ocr_completed":ocr["frames_attempted"],
        "source_screenshots_ocr_errors":ocr["ocr_failed_frames"],
        "screenshots_with_text_candidates":ocr["frames_with_some_ocr_text"],
        "provisional_question_groups":chat_summary["provisional_distinct_question_groups"],
        "rule_fragments_incomplete":fidelity_summary["legacy_rule_candidate_count"],
        "all_source_coverage_stages_ran":True,
        "human_verified_speech_accuracy":None,
        "human_verified_screen_text_accuracy":None,
        "human_verified_teacher_answer_count":0,
        "teacher_chart_meaning_verified":False,
        "source_verified_trading_rules":0,
        "demo_trades_allowed":False,"real_trades_allowed":False,
        "runtime_seconds":round(time.monotonic()-started,2),
        "state":"SOURCE_PIPELINE_DONE_SEMANTIC_TRUTH_NOT_CERTIFIED"}
    _write(output/"safe_session_result.json",safe)
    print("ARTIN_UNIFIED_SESSION_DONE="+json.dumps(safe,ensure_ascii=False),flush=True)
    return safe


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--sample-seconds",type=int,default=30)
    p.add_argument("--model",default="large-v3-turbo")
    a=p.parse_args()
    run_session(a.video,a.out,sample_seconds=a.sample_seconds,model_name=a.model)

if __name__=="__main__":main()
