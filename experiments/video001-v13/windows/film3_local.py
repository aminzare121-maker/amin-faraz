#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the exact archived Artin queue film #3 LOCALLY on Windows, not hosted Actions.

Runs source-once, 18 original parts, 1 CPU ASR worker, 1 OCR worker, and
source-based non-semantic verification. Original MP4 remains byte-identical.
All potentially private content stays in the separately selected local folder.
Never places an order, alters MT5, or marks a teacher rule as verified.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

MOVIE_SHA = "a2721fb01575f9ad4859f594e5c6fa6852e31dce353e31f70eed1a8edb3bbfbb"
MOVIE_URL = "https://my.uupload.ir/p/dxvmY5Gv"
MOVIE_BYTES = 218647703
MOVIE_SECONDS = 5157.198367
MOVIE_PARTS = 18
ID = "video-q-0003-artin-clip-01"
ENGINE = Path(__file__).resolve().parents[3] / "research" / "artin-film-engine-v3-1"


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".pending")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_valid(video: Path):
    if not video.is_file() or video.stat().st_size != MOVIE_BYTES:
        raise ValueError("SOURCE_UNAVAILABLE_OR_WRONG_BYTES: film 3 original differs from registered film")
    if hash_file(video) != MOVIE_SHA:
        raise ValueError("SOURCE_SHA_MISMATCH: refuse substitution or changed video")


def preflight(out: Path, require_models=False):
    if not ENGINE.is_dir() or not (ENGINE / "video001_fast_source_once_v2.py").is_file():
        raise ValueError("V13_ENGINE_MISSING: run from checked-out V13 repository")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFMPEG_FFPROBE_REQUIRED")
    if not out.is_absolute():
        raise ValueError("ABSOLUTE_PRIVATE_OUTPUT_DIRECTORY_REQUIRED")
    if ENGINE.is_relative_to(out) or out.is_relative_to(ENGINE):
        raise ValueError("Do not store private media in Git checkout/engine folder")
    deps = ["PIL", "numpy"] + (["faster_whisper", "paddleocr"] if require_models else [])
    missing = [x for x in deps if importlib.util.find_spec(x) is None]
    if missing:
        raise RuntimeError("REQUIRED_PACKAGES_MISSING: " + ", ".join(missing))
    return {"schema":"video001_v13_windows_preflight_v1",
            "queue_id":ID,"source_sha256":MOVIE_SHA,
            "ffmpeg":True, "model_packages_checked":require_models,
            "runner":"WINDOWS_LOCAL_BOUNDED_CPU",
            "trading_allowed":False}


def download_or_reuse(out: Path):
    local = out / "private_source" / "film3_original_source.mp4"
    if local.exists():
        source_valid(local)
        return local, "VERIFIED_ALREADY_PRESENT"
    sys.path.insert(0, str(ENGINE))
    from video001_fast_remote_prep_v2 import download_once
    from artin_ephemeral_remote_ingest import get_direct_url
    local.parent.mkdir(parents=True, exist_ok=True)
    tmp = local.with_suffix(".download")
    if tmp.exists():
        raise RuntimeError("PREVIOUS_PARTIAL_DOWNLOAD_REQUIRES_INSPECTION")
    direct,_ = get_direct_url(MOVIE_URL)
    try:
        size, digest = download_once(direct, tmp)
        if size != MOVIE_BYTES or digest != MOVIE_SHA:
            raise ValueError("Downloaded movie SHA/size differs from the original film 3")
        os.replace(tmp, local)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    source_valid(local)
    return local, "NEW_SOURCE_SHA_VERIFIED"


def get_prepared(out: Path):
    sys.path.insert(0,str(ENGINE))
    from artin_fast_av_v4 import validate_fast
    from artin_visual_timeline_v6 import validate_visual_index
    root = out / "prepared"
    summary = read_json(root / "safe_source_prep_summary.json")
    if (summary.get("source_video_sha256") != MOVIE_SHA or
        abs(summary.get("original_duration_seconds", 0) - MOVIE_SECONDS) > .01 or
        summary.get("source_global_audio_chunks") != MOVIE_PARTS or
        summary.get("source_audio_worker_count") != 1 or
        summary.get("original_ocr_workers") != 1 or
        not summary.get("source_integrity_verified")):
        raise ValueError("Prepared film 3 provenance or full 18-part coverage invalid")
    m = read_json(root / "full_audio" / "fast_av_manifest.json")
    validate_fast(root / "full_audio",m,verify_files=True)
    if [p["chunk"] for p in m["parts"]] != list(range(1,MOVIE_PARTS+1)):
        raise ValueError("18 source chunks not complete or not ordered")
    visual = read_json(root / "full_board" / "visual_timeline_v6.json")
    validate_visual_index(root / "full_board",m,visual,verify_files=True)
    chat = read_json(root / "full_chat" / "chat_selected_index.json")
    if (chat.get("source_video_sha256") != MOVIE_SHA or
        not isinstance(chat.get("rows"),list) or not chat["rows"]):
        raise ValueError("Original selected chat evidence absent")
    return root, summary, chat


def prepare(out: Path):
    root = out / "prepared"
    if (root / "safe_source_prep_summary.json").is_file():
        get_prepared(out)
        return "VERIFIED_PREPARED_CHECKPOINT"
    if root.exists() and any(root.iterdir()):
        raise RuntimeError("PARTIAL_SOURCE_PREPARATION_REQUIRES_INSPECTION; preserve original files")
    video, status = download_or_reuse(out)
    sys.path.insert(0, str(ENGINE))
    from video001_fast_source_once_v2 import prepare as prep
    prep(video,root,audio_workers=1,ocr_workers=1,sample_seconds=30,expected_sha=MOVIE_SHA)
    source_valid(video)
    get_prepared(out)
    return status + "_AND_PREPARED"


def transcribe(out: Path):
    root, _, _ = get_prepared(out)
    dst = out / "asr" / "asr_evidence"
    manifest_path = dst / "manifest_redacted.json"
    statuses = list(dst.glob("partition_*_status.json"))
    parts = list(dst.glob("part_*_unverified.json"))
    if manifest_path.is_file() and len(statuses)==1 and len(parts)==MOVIE_PARTS:
        if all(read_json(p).get("source_video_sha256")==MOVIE_SHA for p in parts):
            return "ASR_PARTS_ALREADY_PRESENT_REVERIFY_ON_MERGE"
    sys.path.insert(0, str(ENGINE))
    from artin_parallel_asr_worker_v5 import process_shard
    # Existing audited worker: CPU/int8, four CPU threads, one model; original
    # 18 x 5min chunks remain original; no 17 simultaneous CPU models.
    process_shard("",out / "asr",0,1,MOVIE_SHA,
                  model_name="large-v3-turbo",
                  prepped_root=root / "asr_shards" / "worker_00")
    return "ASR_PROCESSED_18_SOURCE_CHUNKS"


def recognize_chat(out: Path):
    root, _, index = get_prepared(out)
    sys.path.insert(0,str(ENGINE))
    from artin_persian_full_chat_ocr_v7 import ocr_frames
    result = ocr_frames(root / "full_chat",index,out/"ocr",
                        partition_index=0,partition_count=1)
    if result["ocr_failed_frames"]:
        raise RuntimeError("OCR_FRAME_FAILURES_NEED_REVIEW")
    return "OCR_COMPLETED_CANDIDATES_NOT_VERIFIED"


def verify(out: Path):
    root, prep, index = get_prepared(out)
    sys.path.insert(0,str(ENGINE))
    from artin_parallel_asr_merge_v5 import merge_private_shards
    from artin_highres_ocr_merge_v8 import merge as merge_ocr
    from artin_ocr_asr_join_v8 import join_original_chat_qa
    from artin_question_dedupe_v11 import clustered_review
    asr=merge_private_shards(out/"asr"/"asr_evidence",out/"private_review"/"speech")
    if asr.get("global_parts")!=MOVIE_PARTS or not asr.get("audio_transcript_coverage_complete"):
        raise RuntimeError("Speech incomplete; no complete film receipt")
    ocr_json=read_json(out/"ocr"/"full_chat_ocr_candidates_PRIVATE.json")
    ocr_summary,full_ocr=merge_ocr(index,[ocr_json])
    if (ocr_summary.get("frames_ocr_failed")!=0 or
        ocr_summary.get("frames_ocr_completed")!=len(index["rows"])):
        raise RuntimeError("OCR incomplete; no complete film receipt")
    speech=read_json(out/"private_review"/"speech"/"complete_unverified_qa_evidence.json")
    qasafe,qa=join_original_chat_qa(index,full_ocr,speech)
    grouped=clustered_review(qa)
    if grouped["source_video_sha256"]!=MOVIE_SHA or not grouped["original_groups_not_lost"]:
        raise RuntimeError("Question evidence lost; no complete film receipt")
    private=out/"private_review"
    write_json(private/"ocr_PRIVATE.json",full_ocr)
    write_json(private/"qa_PRIVATE.json",qa)
    write_json(private/"qa_clusters_PRIVATE.json",grouped)
    summary={"schema":"video001_v13_windows_film3_local_source_receipt_v1",
        "queue_id":ID,"source_video_sha256":MOVIE_SHA,
        "original_duration_seconds":prep["original_duration_seconds"],
        "original_video_unmodified":True,
        "original_audio_parts":MOVIE_PARTS,
        "asr_coverage_complete":True,
        "source_selected_chat_frames":len(index["rows"]),
        "ocr_frame_coverage_complete":True,
        "possible_chat_question_groups":qasafe["provisional_distinct_question_groups"],
        "source_evidence_loss":0,
        "semantic_teacher_accuracy_verified":False,
        "verified_teacher_rules":0,"trading_allowed":False,
        "four_optional_v13_models_ran":False,
        "status":"SOURCE_EVIDENCE_COMPLETE_SEMANTIC_REVIEW_REQUIRED"}
    write_json(out/"safe_result.json",summary)
    return summary


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True,
                    help="Absolute path to a private folder OUTSIDE repo, e.g. C:\\\\AMIN_PRIVATE\\\\V13\\\\film3")
    ap.add_argument("--phase",choices=("preflight","prepare","asr","ocr","verify","all"),
                    default="preflight")
    args=ap.parse_args()
    out=args.out.expanduser().resolve()
    if out == ENGINE or ENGINE.is_relative_to(out) or out.is_relative_to(ENGINE):
        raise ValueError("Private media must not be inside source code or vice versa")
    start=time.monotonic()
    result=preflight(out,require_models=args.phase in ("asr","ocr","all"))
    if args.phase in ("prepare","all"):
        result["source_step"]=prepare(out)
    if args.phase in ("asr","all"):
        result["asr_step"]=transcribe(out)
    if args.phase in ("ocr","all"):
        result["ocr_step"]=recognize_chat(out)
    if args.phase in ("verify","all"):
        result["verify_result"]=verify(out)
    result["wall_seconds"]=round(time.monotonic()-start,2)
    result["phase"]=args.phase
    print("V13_WINDOWS_LOCAL_SAFE_STATUS="+json.dumps(
        {k:v for k,v in result.items() if k!="verify_result"},ensure_ascii=False))
    if "verify_result" in result:
        print("V13_LOCAL_SOURCE_RECEIPT="+json.dumps(result["verify_result"],ensure_ascii=False))


if __name__ == "__main__":
    main()
