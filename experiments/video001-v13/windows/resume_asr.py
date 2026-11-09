#!/usr/bin/env python3
"""Source-SHA checked, resumable LOCAL 18-piece ASR for the V13 Windows pilot.

Keeps checkpoints only in a private local output directory. All original audio
segments are transcribed in source order with one CPU model, not 17 models.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

MODEL = "large-v3-turbo"


def _atomic_json(path, obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix + ".pending")
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(temp,path)


def _check_checkpoint(doc, part, movie_sha):
    if not isinstance(doc,dict) or doc.get("schema")!="artin_asr_shard_v5":
        raise ValueError("Invalid pre-existing ASR checkpoint")
    if (doc.get("global_chunk") != part["chunk"] or
        doc.get("source_video_sha256")!=movie_sha or
        doc.get("source_audio_sha256")!=part["audio_sha256"] or
        doc.get("model")!=MODEL or
        doc.get("timebase")!="absolute_original_video_seconds" or
        doc.get("teacher_rules_verified") is not False or
        doc.get("speaker_human_verified") is not False):
        raise ValueError("Previously saved ASR checkpoint differs from original film")
    segments=doc.get("segments")
    if not isinstance(segments,list):
        raise ValueError("ASR checkpoint has no segments list")
    for i,s in enumerate(segments):
        if (not isinstance(s,dict) or
            s.get("id")!=f"asr_p{part['chunk']:03d}_{i:05d}" or
            type(s.get("start")) not in (int,float) or
            type(s.get("end")) not in (int,float) or
            s["start"]>s["end"] or
            s["start"]<part["cut_start"]-.01 or
            s["end"]>part["cut_end"]+.01 or
            not isinstance(s.get("text"),str) or
            s.get("speaker")!="UNKNOWN" or
            s.get("speaker_verified") is not False):
            raise ValueError("ASR checkpoint segments/timeline/roles changed")
    return True


def run(engine, audio_shard, output, movie_sha, expected_parts=18):
    engine=Path(engine).resolve()
    audio_shard=Path(audio_shard).resolve()
    output=Path(output).resolve()
    sys.path.insert(0,str(engine))
    from artin_fast_av_v4 import validate_fast
    from artin_film_pipeline import file_sha256
    from artin_real_asr_trial_v5 import read_pcm_array
    from artin_parallel_asr_worker_v5 import verified_global_source_chunk_count

    mfile=audio_shard/"fast_av_manifest.json"
    manifest=json.loads(mfile.read_text(encoding="utf-8"))
    if manifest.get("video_sha256")!=movie_sha:
        raise ValueError("Original movie SHA differs from the input")
    validate_fast(audio_shard,manifest,verify_files=False)
    if verified_global_source_chunk_count(manifest)!=expected_parts:
        raise ValueError("Source parts do not cover entire original movie")
    output.mkdir(parents=True,exist_ok=True)
    # Ownership is one local worker responsible for all source parts.
    remaining=[];skipped=0
    for part in manifest["parts"]:
        wav=(audio_shard/part["audio"]).resolve()
        if not wav.is_relative_to(audio_shard) or not wav.is_file() or file_sha256(wav)!=part["audio_sha256"]:
            raise ValueError("Prepared original WAV missing or SHA changed")
        existing=output/f"part_{part['chunk']:03d}_unverified.json"
        if existing.exists():
            _check_checkpoint(json.loads(existing.read_text(encoding="utf-8")),part,movie_sha)
            skipped+=1
        else:
            remaining.append(part)
    manifest_out=dict(manifest)
    manifest_out.pop("video_path_private",None)
    _atomic_json(output/"manifest_redacted.json",manifest_out)
    started=time.monotonic()
    if remaining:
        from faster_whisper import WhisperModel
        model=WhisperModel(MODEL,device="cpu",compute_type="int8",
                           cpu_threads=4,num_workers=1)
        for part in remaining:
            audio=read_pcm_array(audio_shard/part["audio"])
            start=time.monotonic()
            segments,_=model.transcribe(audio,language="fa",vad_filter=True,
                          beam_size=5,condition_on_previous_text=False,
                          word_timestamps=False)
            statements=[]
            for seg in segments:
                begin=part["cut_start"]+float(seg.start)
                end=min(part["cut_end"],part["cut_start"]+float(seg.end))
                if end<=begin:
                    continue
                statements.append({
                    "id":f"asr_p{part['chunk']:03d}_{len(statements):05d}",
                    "start":round(begin,3),"end":round(end,3),
                    "text":seg.text.strip(),"speaker":"UNKNOWN",
                    "speaker_verified":False,
                    "avg_logprob":round(float(seg.avg_logprob),4),
                    "no_speech_prob":round(float(seg.no_speech_prob),4)})
            doc={"schema":"artin_asr_shard_v5","global_chunk":part["chunk"],
              "source_video_sha256":movie_sha,"source_audio_sha256":part["audio_sha256"],
              "timebase":"absolute_original_video_seconds",
              "model":MODEL,"speaker_human_verified":False,
              "teacher_rules_verified":False,"segments":statements}
            _check_checkpoint(doc,part,movie_sha)
            _atomic_json(output/f"part_{part['chunk']:03d}_unverified.json",doc)
            print("V13_LOCAL_ASR_CHECKPOINT="+json.dumps(
                {"part":part["chunk"],"segment_candidates":len(statements),
                 "seconds":round(time.monotonic()-start,2)},ensure_ascii=False),flush=True)
    completed=list(range(1,expected_parts+1))
    for part in manifest["parts"]:
        row=json.loads((output/f"part_{part['chunk']:03d}_unverified.json").read_text(encoding="utf-8"))
        _check_checkpoint(row,part,movie_sha)
    status={"schema":"artin_asr_partition_v5",
      "shard_index":0,"partition_count":1,
      "source_video_sha256":movie_sha,
      "expected_global_parts":completed,
      "completed_global_parts":completed,
      "source_part_count":expected_parts,
      "elapsed_seconds":round(time.monotonic()-started,2),
      "all_speakers_verified":False,
      "rules_executable":0,"full_course_ready":False}
    _atomic_json(output/"partition_0_status.json",status)
    return {"parts_verified":expected_parts,"parts_reused":skipped,
            "parts_newly_transcribed":len(remaining),
            "seconds":status["elapsed_seconds"],
            "semantic_teacher_accuracy_verified":False}
