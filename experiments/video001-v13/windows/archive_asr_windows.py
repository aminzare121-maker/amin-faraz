#!/usr/bin/env python3
"""Resume actual Artin film 3 ASR from SHA-verified archived original audio.

No re-download of movie, no hosted Actions, no MT5/trades. Supports 17 extracted
GitHub artifacts under archives/worker_00..worker_16. Each worker holds one or
two immutable five-minute original audio chunks. --phase verify works without
external dependencies and performs SHA checks on 18/18 original WAVs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

MOVIE_SHA = "a2721fb01575f9ad4859f594e5c6fa6852e31dce353e31f70eed1a8edb3bbfbb"
FILM_ID = "video-q-0003-artin-clip-01"
GLOBAL_PARTS = 18
ARCHIVE_WORKERS = 17
MODEL = "large-v3-turbo"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".pending")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_archives(archives):
    archives = Path(archives).resolve()
    reference = None
    originals = {}
    for worker in range(ARCHIVE_WORKERS):
        wdir = archives / ("worker_%02d" % worker)
        if not wdir.is_dir():
            raise ValueError("MISSING_ARCHIVE_WORKER_%02d" % worker)
        man = wdir / "fast_av_manifest.json"
        if not man.is_file():
            raise ValueError("MISSING_SOURCE_MANIFEST_WORKER_%02d" % worker)
        current = load(man)
        if (current.get("video_sha256") != MOVIE_SHA
                or len(current.get("parts", [])) != GLOBAL_PARTS
                or not math.isfinite(float(current.get("duration_seconds", 0)))
                or abs(float(current["duration_seconds"]) - 5157.198367) > .02):
            raise ValueError("FILM3_MANIFEST_PROVENANCE_MISMATCH")
        ids = [p.get("chunk") for p in current["parts"]]
        if ids != list(range(1, GLOBAL_PARTS + 1)):
            raise ValueError("INCOMPLETE_18_PART_SOURCE_MANIFEST")
        if reference is None:
            reference = current
        elif json.dumps(current, sort_keys=True) != json.dumps(reference, sort_keys=True):
            raise ValueError("ORIGINAL_MANIFEST_DIFFERS_BETWEEN_WORKERS")
        assigned = [p for p in current["parts"] if (p["chunk"] - 1) % ARCHIVE_WORKERS == worker]
        if not assigned:
            raise ValueError("EMPTY_ARCHIVE_WORKER")
        for p in assigned:
            path = (wdir / p["audio"]).resolve()
            if not path.is_relative_to(wdir.resolve()) or not path.is_file():
                raise ValueError("MISSING_OR_ESCAPED_AUDIO_CHUNK_%02d" % p["chunk"])
            if digest(path) != p["audio_sha256"]:
                raise ValueError("AUDIO_CHUNK_SHA_MISMATCH_%02d" % p["chunk"])
            if p["chunk"] in originals:
                raise ValueError("DUPLICATE_AUDIO_CHUNK")
            originals[p["chunk"]] = (p, path)
    if sorted(originals) != list(range(1, GLOBAL_PARTS+1)):
        raise ValueError("MISSING_SOURCE_AUDIO_CHUNK")
    return reference, originals


def _validate_saved(saved, p):
    if (not isinstance(saved, dict)
            or saved.get("schema") != "video001_v13_film3_archived_asr_chunk_v1"
            or saved.get("source_video_sha256") != MOVIE_SHA
            or saved.get("global_chunk") != p["chunk"]
            or saved.get("source_audio_sha256") != p["audio_sha256"]
            or saved.get("model") != MODEL
            or saved.get("human_verified") is not False
            or not isinstance(saved.get("segments"), list)):
        raise ValueError("ASR_CHECKPOINT_PROVENANCE_MISMATCH")
    for i, s in enumerate(saved["segments"]):
        if (s.get("id") != "asr_film3_p%02d_%04d" % (p["chunk"], i)
                or not isinstance(s.get("text"), str)
                or not isinstance(s.get("start_seconds"), (float, int))
                or not isinstance(s.get("end_seconds"), (float, int))
                or s["start_seconds"] < p["cut_start"] - .02
                or s["end_seconds"] > p["cut_end"] + .02
                or s["end_seconds"] < s["start_seconds"]):
            raise ValueError("ASR_CHECKPOINT_TIME_OR_SEGMENT_MISMATCH")


def run(archives, out, phase="verify", model=MODEL):
    if model != MODEL:
        raise ValueError("MODEL_CHANGE_REQUIRES_SEPARATE_OUTPUT_DIRECTORY")
    manifest, sources = validate_archives(archives)
    out = Path(out).resolve()
    if out.is_relative_to(Path(archives).resolve()) or Path(archives).resolve().is_relative_to(out):
        raise ValueError("OUTPUT_AND_SOURCE_MUST_BE_SEPARATE")
    preflight = {
        "schema": "video001_v13_windows_film3_archived_asr_v1",
        "movie_id": FILM_ID, "source_video_sha256": MOVIE_SHA,
        "original_video_duration_seconds": float(manifest["duration_seconds"]),
        "source_audio_parts_sha_verified": GLOBAL_PARTS,
        "source_audio_workers_sha_verified": ARCHIVE_WORKERS,
        "full_transcription_completed": False,
        "rules_verified": 0,
        "speaker_identity_verified": False,
        "trading_allowed": False,
    }
    if phase == "verify":
        return preflight
    if phase != "run":
        raise ValueError("Unknown phase")
    try:
        from faster_whisper import WhisperModel
    except ImportError as ex:
        raise RuntimeError("FASTER_WHISPER_NOT_INSTALLED_IN_WINDOWS_VENV") from ex

    out.mkdir(parents=True, exist_ok=True)
    remaining = []
    for idx in range(1, GLOBAL_PARTS+1):
        p, original_path = sources[idx]
        existing = out / ("part_%02d_asr.json" % idx)
        if existing.is_file():
            _validate_saved(load(existing), p)
        else:
            remaining.append(idx)
    started = time.monotonic()
    if remaining:
        # One CPU model avoids 17 simultaneous model copies on a laptop.
        whisper = WhisperModel(model, device="cpu", compute_type="int8",
                               cpu_threads=4, num_workers=1)
        for idx in remaining:
            p, source_path = sources[idx]
            sections, info = whisper.transcribe(str(source_path), language="fa",
                              vad_filter=True, beam_size=5,
                              condition_on_previous_text=False)
            rows = []
            for s in sections:
                absolute_start = float(p["cut_start"]) + float(s.start)
                absolute_end = min(float(p["cut_end"]), float(p["cut_start"]) + float(s.end))
                if absolute_end <= absolute_start:
                    continue
                rows.append({
                    "id": "asr_film3_p%02d_%04d" % (idx,len(rows)),
                    "start_seconds": round(absolute_start, 3),
                    "end_seconds": round(absolute_end, 3),
                    "in_primary_five_minute_window":
                        (absolute_start + absolute_end)/2 >= float(p["core_start"])
                        and (absolute_start + absolute_end)/2 < float(p["core_end"]),
                    "text": s.text.strip(), "speaker": "UNKNOWN",
                    "human_verified": False,
                    "avg_logprob": round(float(s.avg_logprob), 4),
                    "no_speech_prob": round(float(s.no_speech_prob), 4),
                })
            doc = {
                "schema":"video001_v13_film3_archived_asr_chunk_v1",
                "global_chunk":idx, "source_video_sha256":MOVIE_SHA,
                "source_audio_sha256":p["audio_sha256"], "model":model,
                "human_verified":False, "speaker_verified":False,
                "teacher_rules_verified":False, "segments":rows,
            }
            _validate_saved(doc,p)
            atomic_json(out / ("part_%02d_asr.json" % idx), doc)
            print("V13_ASR_CHUNK_DONE="+json.dumps(
                  {"chunk":idx,"segments":len(rows),"elapsed_seconds":round(time.monotonic()-started,2)}),
                  flush=True)
    parts = [load(out/("part_%02d_asr.json" % i)) for i in range(1,GLOBAL_PARTS+1)]
    for i,doc in enumerate(parts,1):
        _validate_saved(doc,sources[i][0])
    summary = dict(preflight)
    summary.update({
        "full_transcription_completed": True,
        "segments_raw_including_overlap": sum(len(p["segments"]) for p in parts),
        "segments_primary_window": sum(sum(x["in_primary_five_minute_window"]
              for x in p["segments"]) for p in parts),
        "parts_completed": GLOBAL_PARTS,
        "parts_reused_from_verified_checkpoints": GLOBAL_PARTS-len(remaining),
        "newly_transcribed_parts": len(remaining),
        "elapsed_seconds_this_run": round(time.monotonic()-started, 2),
        "semantic_accuracy_verified": False,
        "status": "ASR_FULL_AUDIO_COVERAGE_UNVERIFIED_TEACHER_MEANING",
    })
    atomic_json(out/"safe_asr_summary.json",summary)
    return summary


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--archives",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--phase",choices=("verify","run"),default="verify")
    args = a.parse_args()
    result = run(args.archives, args.out, args.phase)
    print("V13_WINDOWS_FILM3_ARCHIVE_ASR="+json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
