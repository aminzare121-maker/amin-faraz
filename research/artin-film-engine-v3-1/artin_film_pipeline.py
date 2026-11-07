#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Artin's offline, auditable 18-chunk classroom video research pipeline.

A language model's candidate interpretations and speech recognition are *not*
verified teacher rules. Never sends orders or updates the live Artin engine.
No cloud upload; optional Ollama requests are localhost only.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from artin_semantic_context import (
    validate_capsule, adjacent_context, quarantine_events, noise_risk
)
from artin_batch_slots import annotate_plan, artifact_path, batch_slot, batch_summary

CHUNK_S = 300
OVERLAP_S = 12
VALID_KINDS = frozenset({"QUESTION", "ANSWER", "CORRECTION", "RULE", "EXCEPTION", "EXAMPLE", "OTHER", "CLASSROOM_NOISE"})
VALID_DECISIONS = frozenset({"BUY", "SELL", "NO_TRADE", "UNKNOWN"})
SOURCE_FLAGS = "UNVERIFIED_MODEL_INTERPRETATION_REQUIRES_AUDIO_VIDEO_REVIEW"


def atomic_json(path: Path, obj: object):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".artin-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def run_cmd(args: list[str]):
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"Command failure {args[0]}: {(proc.stderr or proc.stdout)[-1200:]}")
    return proc.stdout


def probe_video(video: Path):
    info = json.loads(run_cmd(["ffprobe", "-v", "error", "-show_entries",
                               "format=duration:stream=codec_type", "-of", "json", str(video)]))
    duration = float(info["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video has invalid duration")
    streams = {s["codec_type"] for s in info.get("streams", [])}
    if "video" not in streams:
        raise ValueError("Source needs a video track")
    return duration, sorted(streams)


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def chunk_plan(duration: float, chunk_s: int=CHUNK_S, overlap_s: int=OVERLAP_S):
    if chunk_s < 5 or overlap_s < 0 or overlap_s >= chunk_s/2:
        raise ValueError("Invalid chunk or overlap duration")
    if duration <= 0:
        raise ValueError("Duration must be positive")
    results=[]
    # MP4 duration metadata can exceed a precise 5-minute boundary by tiny
    # encoder padding (e.g. 5400.04s). Retain the padding in the LAST chunk
    # rather than inventing a 19th almost-empty clip. Never drop source time.
    nearest=round(duration/chunk_s)
    if nearest>0 and abs(duration-nearest*chunk_s)<=0.25:
        count=nearest
    else:
        count=math.ceil(duration/chunk_s)
    for i in range(count):
        core_start = i*chunk_s
        core_end = duration if i==count-1 else min(duration,(i+1)*chunk_s)
        # The overlap is for ASR context; the original video is NEVER concatenated
        # from overlapping clips or counted twice in the timeline.
        cut_start = max(0,core_start-overlap_s)
        cut_end = min(duration,core_end+overlap_s)
        results.append({"chunk": i+1, "core_start":round(core_start,3), "core_end":round(core_end,3),
                        "cut_start":round(cut_start,3), "cut_end":round(cut_end,3),
                        "clip":f"clips/part_{i+1:02d}.mp4",
                        "transcript":f"transcripts/part_{i+1:02d}.json",
                        "analysis":f"analyses/part_{i+1:02d}.json"})
    return annotate_plan(results)


def canonical_chunk_order(completed: list[dict], expected: list[dict]):
    """Order PARALLEL extraction results by planned piece number, never finish time.

    Reject duplicates, missing numbers, unexpected numbers, crossed boundaries,
    or a clip path that claims to belong to a different 5-minute segment.
    This checks bookkeeping; it does not verify spoken lesson meaning.
    """
    if not expected:
        raise ValueError("No expected chunk numbering")
    target={x["chunk"]:x for x in expected}
    if sorted(target)!=list(range(1,len(expected)+1)) or len(target)!=len(expected):
        raise ValueError("Expected chunk numbers must be unique and contiguous from 1")
    found={}
    for part in completed:
        n=part.get("chunk")
        if type(n) is not int or n not in target:
            raise ValueError("Unknown or invalid five-minute chunk number")
        if n in found:
            raise ValueError(f"Duplicate five-minute chunk number: {n}")
        for key in ("core_start","core_end","cut_start","cut_end"):
            value=part.get(key)
            if type(value) not in (float,int) or not math.isfinite(value) or abs(value-target[n][key])>0.02:
                raise ValueError(f"Chunk {n:02d} has wrong source-time interval: {key}")
        for key in ("clip","transcript","analysis"):
            if part.get(key)!=target[n][key]:
                raise ValueError(f"Chunk {n:02d} has wrong numbered file: {key}")
        if len(expected)>18 or any(k in part for k in ("batch","slot","global_index","unique_id")):
            for key in ("batch","slot","global_index","unique_id"):
                if part.get(key)!=target[n][key]:
                    raise ValueError(f"Chunk {n:02d} has invalid batch/slot identity: {key}")
        found[n]=part
    missing=sorted(set(target)-set(found))
    if missing:
        raise ValueError(f"Missing five-minute chunk number(s): {missing}")
    return [found[n] for n in range(1,len(expected)+1)]


def validate_manifest_order(m: dict):
    """Require a published manifest to be in chronological numbered order.

    Older synthetic fixtures without full time ranges are tolerated only as
    fixtures; real prepare() always writes a strict, complete plan.
    """
    chunks=m.get("chunks")
    if not isinstance(chunks,list) or not chunks:
        raise ValueError("No numbered chunks in manifest")
    ids=[c.get("chunk") if isinstance(c,dict) else None for c in chunks]
    if ids!=list(range(1,len(chunks)+1)):
        raise ValueError("Manifest chunk order is missing, duplicated or scrambled")
    complete=all(all(key in c for key in
                    ("core_start","core_end","cut_start","cut_end","clip","transcript","analysis"))
                 for c in chunks)
    if not complete:
        if m.get("strict_chunk_order"):
            raise ValueError("Strict manifest is missing chunk source-time metadata")
        return chunks
    duration=m.get("source_duration")
    if type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0:
        raise ValueError("Missing valid source video duration")
    size=m.get("chunk_seconds",300)
    overlap=m.get("overlap_seconds",OVERLAP_S)
    expected=chunk_plan(duration,int(size),int(overlap))
    return canonical_chunk_order(chunks,expected)


def check_saved_clips(root: Path, m: dict):
    """Fail if a clip is absent or was changed after the numbered split."""
    validate_manifest_order(m)
    root=Path(root).resolve()
    for c in m["chunks"]:
        clip=(root/c["clip"]).resolve()
        if not clip.is_relative_to(root) or not clip.is_file():
            raise ValueError(f"Numbered clip {c['chunk']:02d} is missing/unsafe")
        if c.get("clip_sha256")!=file_sha256(clip):
            raise ValueError(f"Numbered clip {c['chunk']:02d} SHA256 mismatch")
    return True


def _extract_one(video: Path, root: Path, part: dict, frames_per_chunk: int):
    clip=root/part["clip"]
    clip.parent.mkdir(parents=True,exist_ok=True)
    length=part["cut_end"]-part["cut_start"]
    # Encoding short chunks is more accurate than stream-copy when source has
    # sparse keyframes. Seek to cut_start, encode only this local intermediate.
    run_cmd(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-ss",str(part["cut_start"]),"-i",str(video),"-t",str(length),
             "-map","0:v:0", "-map","0:a:0?", "-c:v","libx264", "-preset","ultrafast",
             "-crf","28", "-c:a","aac", "-b:a","64k", "-movflags","+faststart",str(clip)])
    # Multi-modal inspection frames from core region, not just a single image.
    imgs=[]
    samples=max(0,frames_per_chunk)
    if samples:
        for j in range(samples):
            at=part["core_start"]+(j+0.5)*(part["core_end"]-part["core_start"])/samples
            image_name=(f"part_{part['slot']:02d}_{j+1:02d}.jpg" if part['batch']==1
                        else f"{part['unique_id']}_{j+1:02d}.jpg")
            image_path=root/"frames"/image_name
            image_path.parent.mkdir(parents=True,exist_ok=True)
            run_cmd(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                     "-ss",str(round(at,3)),"-i",str(video),"-frames:v","1",
                     "-vf","scale='min(960,iw)':-2","-q:v","5",str(image_path)])
            imgs.append({"time":round(at,3),"path":str(image_path.relative_to(root)),
                         "sha256":file_sha256(image_path)})
    return {**part,"clip_sha256":file_sha256(clip),"frames":imgs}


def prepare(video: Path, root: Path, workers=3, frames_per_chunk=3, chunk_s=CHUNK_S):
    video=Path(video).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    root=Path(root).resolve()
    if root==video.parent or root==video:
        raise ValueError("Do not use the source video's folder as the output folder")
    root.mkdir(parents=True,exist_ok=True)
    duration,streams=probe_video(video)
    effective_overlap=min(OVERLAP_S, max(0,(chunk_s-1)//3))
    plan=chunk_plan(duration,chunk_s,effective_overlap)
    # Reject attempts to put a different video into an existing output tree:
    # otherwise old ASR/analysis could be mistaken for this film.
    video_digest=file_sha256(video)
    existing=root/"manifest.json"
    if existing.exists():
        former=json.loads(existing.read_text(encoding="utf8"))
        if former.get("video_sha256")!=video_digest:
            raise ValueError("Output contains a different source video; use a new output folder")
    # Publish the expected 01..18 schedule BEFORE launching parallel FFmpeg.
    # A planning file is NOT a successful extraction manifest.
    atomic_json(root/"chunk_plan_pending.json",{
        "status":"PLANNED_NOT_FINISHED","video_sha256":video_digest,
        "source_duration":duration,"parts_expected":len(plan),
        "batches":batch_summary(plan),
        "sequence":[{"number":p["chunk"],"batch":p["batch"],"slot":p["slot"],
                     "unique_id":p["unique_id"],"core_start":p["core_start"],
                     "core_end":p["core_end"],"clip":p["clip"]} for p in plan]})
    workers=min(max(1,int(workers)),len(plan))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        tasks=[ex.submit(_extract_one,video,root,p,frames_per_chunk) for p in plan]
        completed=[f.result() for f in concurrent.futures.as_completed(tasks)]
    # CRITICAL: completion order can be 12,3,18,1,...; official order is
    # ALWAYS 01,02,...,18 (not completion time, filesystem order or timestamp).
    parts=canonical_chunk_order(completed,plan)
    manifest={"schema":"artin_video_manifest_v1","video_path_private":str(video),
              "video_sha256":video_digest,"source_duration":duration,
              "source_streams":streams,"chunk_seconds":chunk_s,"overlap_seconds":effective_overlap,
              "strict_chunk_order":True,"batch_schema":"EIGHTEEN_SLOTS_WITH_GLOBAL_ID_V1",
              "batches":batch_summary(parts),"batch_count":len(batch_summary(parts)),
              "chunk_order_source":"GLOBAL_SOURCE_INDEX_AND_BATCH_SLOT_NOT_FINISH_TIME",
              "chunk_numbers_in_order":[p["chunk"] for p in parts],
              "preprocessing":"LOCAL_FFMPEG_NOT_SEMANTIC_UNDERSTANDING",
              "chunks":parts,"parts_ready":len(parts),"speech_transcribed":False,"teacher_rules_verified":0}
    check_saved_clips(root,manifest)
    atomic_json(root/"manifest.json",manifest)
    atomic_json(root/"chunk_order_verified.json",{
        "status":"ALL_CHUNKS_NUMBERED_AND_ORDER_VERIFIED",
        "video_sha256":video_digest,"source_duration":duration,
        "expected_count":len(plan),"actual_count":len(parts),
        "chunk_numbers_in_source_order":[p["chunk"] for p in parts],
        "batch_count":len(batch_summary(parts)),"batches":batch_summary(parts),
        "unique_ids_in_source_order":[p["unique_id"] for p in parts],
        "no_missing_or_duplicate_numbers":True,
        "no_gap_or_overlap_in_original_five_minute_core_timeline":True,
        "analysis_overlap_is_context_only":True,
        "parts":[{"number":c["chunk"],"batch":c["batch"],
                  "slot":c["slot"],"unique_id":c["unique_id"],"clip":c["clip"],
                  "clip_sha256":c["clip_sha256"],"start":c["core_start"],
                  "end":c["core_end"],
                  "previous":c["chunk"]-1 if c["chunk"]>1 else None,
                  "next":c["chunk"]+1 if c["chunk"]<len(parts) else None}
                 for c in parts],
        "teacher_method_verified":False})
    (root/"chunk_plan_pending.json").unlink(missing_ok=True)
    return manifest


def load_manifest(root: Path):
    manifest=json.loads((Path(root)/"manifest.json").read_text(encoding="utf8"))
    if manifest.get("schema")!="artin_video_manifest_v1":
        raise ValueError("Invalid Artin manifest schema")
    validate_manifest_order(manifest)
    return manifest


def _local_whisper_one(root: Path, chunk: dict, model_location: str, device="cpu"):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Missing faster-whisper; install separately. No model is downloaded automatically") from exc
    # No implicit download: the user must explicitly install a local model.
    if not Path(model_location).is_dir():
        raise ValueError("ASR model must be a previously installed LOCAL directory")
    model=WhisperModel(model_location,device=device,
                       compute_type="int8" if device=="cpu" else "auto",
                       local_files_only=True)
    segments,info=model.transcribe(str(root/chunk["clip"]), language="fa", vad_filter=True,
                                   word_timestamps=False,beam_size=3)
    entries=[]
    for i,seg in enumerate(segments):
        s=chunk["cut_start"]+float(seg.start)
        e=chunk["cut_start"]+float(seg.end)
        if e<=s or s>chunk["cut_end"]+1:continue
        entries.append({"id":f"c{chunk['chunk']:02d}_u{i:04d}","start":round(s,3),
                        "end":round(e,3),"text":seg.text.strip(),
                        "speaker":"UNKNOWN","speaker_verified":False,
                        "transcription_confidence_verified":False})
    result={"schema":"artin_chunk_transcript_v1","chunk":chunk["chunk"],
            "source_clip_sha256":chunk["clip_sha256"],"asr":"LOCAL_FASTER_WHISPER_UNVERIFIED",
            "segments":entries,"original_audio_reviewed":False}
    atomic_json(root/chunk["transcript"],result)
    return result


def transcribe(root: Path, model_location: str, workers=1, device="cpu"):
    root=Path(root).resolve(); manifest=load_manifest(root)
    workers=max(1,min(int(workers),len(manifest["chunks"])))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        future=[ex.submit(_local_whisper_one,root,c,model_location,device)
                for c in manifest["chunks"]]
        outputs=[f.result() for f in concurrent.futures.as_completed(future)]
    return sorted(outputs,key=lambda x:x["chunk"])


def validate_transcript(chunk:dict, doc:dict):
    if doc.get("schema")!="artin_chunk_transcript_v1" or doc.get("chunk")!=chunk["chunk"]:
        raise ValueError("Transcript chunk/schema mismatch")
    if doc.get("source_clip_sha256")!=chunk["clip_sha256"]:
        raise ValueError("Transcript does not match clip SHA256")
    out=[]
    for u in doc.get("segments",[]):
        if type(u.get("text")) is not str or not u["text"].strip():
            raise ValueError("Invalid transcript text")
        s,e=u.get("start"),u.get("end")
        if type(s) not in (int,float) or type(e) not in (int,float) or not (
            chunk["cut_start"]-0.1<=s<e<=chunk["cut_end"]+1.0
        ):
            raise ValueError("Transcript timestamps outside clip")
        if u.get("speaker_verified") is True:
            # Do not accept a boolean in imported Whisper JSON to claim verified
            # speakers; confirmation requires video/audio review outside this program.
            raise ValueError("No unsupervised module may claim verified speakers")
        out.append({"id":u["id"],"start":float(s),"end":float(e),"text":u["text"].strip(),
                    "chunk":chunk["chunk"],"speaker":"UNKNOWN","speaker_verified":False})
    return out


def normalize_text(s):
    s=unicodedata.normalize("NFKC",s).translate(str.maketrans("يكى","یکی"))
    return " ".join(re.sub(r"[^\w\s]"," ",s.casefold()).split())


def deduplicate_segments(segments:list[dict],tolerance=2.5):
    """Remove overlap duplication without deleting distinct repeated speech."""
    ordered=sorted(segments,key=lambda u:(u["start"],u["end"],u["id"]))
    unique=[];aliases={}
    for seg in ordered:
        duplicate=None
        norm=normalize_text(seg["text"])
        for other in reversed(unique):
            if seg["start"]-other["start"]>tolerance+30:break
            if (norm and norm==normalize_text(other["text"]) and
                abs(seg["start"]-other["start"])<=tolerance and
                abs(seg["end"]-other["end"])<=tolerance):
                duplicate=other
                break
        if duplicate is not None:
            # Favor the segment emitted by the chunk whose core interval owns the
            # utterance midpoint, when that information is available.
            aliases[seg["id"]]=duplicate["id"]
        else:unique.append(seg)
    return unique,aliases


def text_context(segments,chunk,margin_s=36):
    return [s for s in segments if
            s["start"]>=chunk["core_start"]-margin_s and
            s["start"]<chunk["core_end"]+margin_s]


OLLAMA_SYSTEM = """You are an extremely conservative analyst of Persian trading classes.
Return JSON only with {\"events\": [ ... ]}. Each event MUST have:
kind one of QUESTION, ANSWER, CORRECTION, RULE, EXCEPTION, EXAMPLE, OTHER, CLASSROOM_NOISE;
source_ids array of exact provided segment ids; exact_quote contiguous from one
segment text; rule_label string or empty; decision BUY/SELL/NO_TRADE/UNKNOWN;
conditions list of strings; is_discussion_not_instruction boolean.
Only quote verbatim text in source_ids. Do not invent teacher/student identity.
Video frames are samples, not a complete visual record; never claim a diagram
or chart is verified. Identify uncertainty. You may report questions but NEVER
assume the immediately following utterance is the answer. You may report a
correction candidate but NEVER silently replace earlier rules. Classroom logistics, microphone/camera problems, internet interruptions and
unrelated personal talk should be CLASSROOM_NOISE, NOT a trading strategy.
A quote mixing an actual trading rule and a technical problem is AMBIGUOUS:
never silently discard the trading portion. Neighbors' content helps interpret
this chunk but is NOT owned by it and must not become an invented source quote.
Never declare a strategy ready to trade, even if the lesson appears complete.
"""


def ollama_json(model:str, user_prompt:str, frames:list[str]|None=None,
                endpoint="http://127.0.0.1:11434", timeout=240,
                system_prompt=OLLAMA_SYSTEM):
    p=urllib.parse.urlsplit(endpoint)
    if p.scheme!="http" or p.hostname not in ("localhost","127.0.0.1","::1") or p.username or p.password:
        raise ValueError("Only explicit LOCAL Ollama HTTP service is permitted")
    images=[base64.b64encode(Path(q).read_bytes()).decode("ascii") for q in (frames or [])]
    request={"model":model,"stream":False,"format":"json","options":{"temperature":0},
             "messages":[{"role":"system","content":system_prompt},
                         {"role":"user","content":user_prompt,"images":images}]}
    url=endpoint.rstrip("/")+"/api/chat"
    req=urllib.request.Request(url,json.dumps(request,ensure_ascii=False).encode("utf8"),
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        data=json.load(response)
    content=data.get("message",{}).get("content","")
    return json.loads(content)


CAPSULE_SYSTEM = """You analyze EXACTLY ONE 5-minute Persian trading class transcript.
Return ONLY JSON: {"anchors": [{"source_id": "exact provided segment id",
"exact_quote": "verbatim substring of same segment", "kind": "QUESTION|ANSWER|CORRECTION|RULE|EXCEPTION|EXAMPLE|CLASSROOM_NOISE"}]}.
Find source-linked candidate rules, open questions, later corrections and class
technical noise. Include enough contextual anchors to preserve continuity across
neighboring 5-minute sections. Never invent quotes, student/teacher attribution,
chart values, or a trade instruction; this is UNVERIFIED candidate metadata.
"""


def build_context_capsules(root:Path, model:str, workers=2,
                           endpoint="http://127.0.0.1:11434"):
    """Stage 1: process 18 complete 5-minute core transcripts concurrently.

    Each output contains only quoted, time-bound anchors.  The next phase
    independently sees both adjacent chunks' capsules before classifying its
    own chunk. There is NO guessed teacher approval or trading execution.
    """
    root=Path(root).resolve();manifest=load_manifest(root)
    all_segments=[]
    for chunk in manifest["chunks"]:
        path=root/chunk["transcript"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing ASR for context capsule {chunk['chunk']}")
        all_segments.extend(validate_transcript(chunk,
            json.loads(path.read_text(encoding="utf8"))))
    utterances,_=deduplicate_segments(all_segments)
    def one(chunk):
        core=[u for u in utterances if chunk["core_start"]<=u["start"]<chunk["core_end"]]
        prompt=json.dumps({"task":"Candidate anchors across the entire five-minute core",
            "chunk":chunk["chunk"],"core_start":chunk["core_start"],
            "core_end":chunk["core_end"],"segments":core},ensure_ascii=False)
        raw=ollama_json(model,prompt,endpoint=endpoint,system_prompt=CAPSULE_SYSTEM)
        doc,rejected=validate_capsule(raw,core,chunk)
        doc["source_video_sha256"]=manifest["video_sha256"]
        doc["source_core_segment_ids"]=[u["id"] for u in core]
        doc["rejected_candidates"]=rejected
        doc["model_name"]=model
        atomic_json(root/artifact_path("context_capsules",chunk),doc)
        return doc
    max_workers=min(max(1,int(workers)),len(manifest["chunks"]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        results=list(ex.map(one,manifest["chunks"]))
    return sorted(results,key=lambda x:x["chunk"])


def _event_id(chunk_number,seq,source_ids,quote):
    sig=f"{chunk_number}|{seq}|{','.join(source_ids)}|{quote}"
    return "e_"+hashlib.sha256(sig.encode("utf8")).hexdigest()[:18]


def validate_model_events(raw,source:list[dict],part:dict,neighbor_anchor_ids=None,visual_evidence=None):
    if not isinstance(raw,dict) or not isinstance(raw.get("events"),list):
        raise ValueError("LLM must return an events array")
    known={s["id"]:s for s in source}
    neighbor_anchor_ids=set(neighbor_anchor_ids or ())
    visual_evidence=visual_evidence or {}
    ret=[];rejected=[]
    for i,event in enumerate(raw["events"][:150]):
        if not isinstance(event,dict):
            rejected.append({"item":i,"reason":"INVALID_OBJECT"});continue
        kind=event.get("kind");ids=event.get("source_ids")
        quote=event.get("exact_quote")
        if kind not in VALID_KINDS or not isinstance(ids,list) or not ids or not all(
            isinstance(k,str) and k in known for k in ids
        ) or type(quote) is not str or not quote.strip():
            rejected.append({"item":i,"reason":"MISSING_OR_INVALID_GROUNDED_QUOTE"});continue
        if not normalize_text(quote) or not any(normalize_text(quote) in normalize_text(known[s]["text"]) for s in ids):
            rejected.append({"item":i,"reason":"QUOTE_NOT_FOUND_IN_SOURCE"});continue
        sources=[known[s] for s in ids]
        start=min(s["start"] for s in sources);end=max(s["end"] for s in sources)
        # Only accept an event whose evidence starts in THIS chunk's core area;
        # adjacent clip context is for reasoning, never duplicate ownership.
        if not (part["core_start"]<=start<part["core_end"]):
            rejected.append({"item":i,"reason":"CROSS_CHUNK_CONTEXT_NOT_OWNED"});continue
        decision=event.get("decision","UNKNOWN")
        if decision not in VALID_DECISIONS:decision="UNKNOWN"
        label=event.get("rule_label","")
        cond=event.get("conditions",[])
        if type(label) is not str:label=""
        if not isinstance(cond,list) or not all(type(c) is str for c in cond):cond=[]
        adjacent_ids=event.get("related_context_ids",[])
        if (not isinstance(adjacent_ids,list) or
            any(type(x) is not str or x not in neighbor_anchor_ids for x in adjacent_ids)):
            rejected.append({"item":i,"reason":"UNAUTHENTICATED_NEIGHBOR_CONTEXT_REFERENCE"});continue
        related_visual=event.get("related_visual_frame_ids",[])
        if (not isinstance(related_visual,list) or any(
                type(fid) is not str or fid not in visual_evidence for fid in related_visual)):
            rejected.append({"item":i,"reason":"UNKNOWN_OR_UNVERIFIED_VISUAL_FRAME_REFERENCE"});continue
        # Source-filename/hash and a model's image description are evidence pointers,
        # not independently confirmed measurements of any candle or indicator.
        referenced_visual=[{ "frame_id":fid,
            "frame_sha256":visual_evidence[fid]["frame_sha256"],
            "time_approx_seconds":visual_evidence[fid]["time_approx_seconds"],
            "model_interpretation_unverified":True} for fid in dict.fromkeys(related_visual)]
        # Off-topic classroom disruptions must not be promoted to rule candidates.
        # When technical and trading content coexist, quarantine for human review.
        domain_risk=noise_risk(quote)
        if domain_risk=="CLEAR_OFFTOPIC":
            kind="CLASSROOM_NOISE"
        if kind=="CLASSROOM_NOISE" or domain_risk=="MIXED_CONTEXT_REVIEW":
            label="";cond=[];decision="UNKNOWN"
        ret.append({"id":_event_id(part["chunk"],i,ids,quote),
                    "kind":kind,"source_ids":ids,"quote":quote,
                    "start":round(start,3),"end":round(end,3),"chunk":part["chunk"],
                    "rule_label_candidate":label.strip(),"decision_candidate":decision,
                    "condition_candidates":cond,
                    "related_context_ids":list(dict.fromkeys(adjacent_ids)),
                    "related_visual_frame_evidence":referenced_visual,
                    "model_kind_original":event.get("kind"),
                    "classroom_noise_risk":domain_risk,
                    "speaker":"UNKNOWN", "speaker_verified":False,
                    "frame_evidence_not_verified":True,
                    "confidence_not_proof":event.get("confidence",None),
                    "status":SOURCE_FLAGS,"can_trade":False})
    return ret,rejected


def analyze(root:Path,model:str,workers=2,with_frames=False,
            endpoint="http://127.0.0.1:11434",require_capsules=False):
    root=Path(root).resolve();manifest=load_manifest(root)
    all_segments=[]
    for c in manifest["chunks"]:
        path=root/c["transcript"]
        if not path.is_file():raise FileNotFoundError(f"Missing ASR for chunk {c['chunk']}: {path}")
        all_segments.extend(validate_transcript(c,json.loads(path.read_text(encoding="utf8"))))
    all_segments,aliases=deduplicate_segments(all_segments)
    capsules={}
    for c in manifest["chunks"]:
        path=root/artifact_path("context_capsules",c)
        if not path.exists():
            if require_capsules:
                raise FileNotFoundError(f"Missing first-pass context capsule for chunk {c['chunk']}")
            continue
        doc=json.loads(path.read_text(encoding="utf8"))
        if (doc.get("schema")!="artin_grounded_context_capsule_v1" or
            doc.get("chunk")!=c["chunk"] or
            doc.get("source_video_sha256")!=manifest["video_sha256"] or
            doc.get("teacher_meaning_understood_and_verified") is not False or
            doc.get("trade_ready") is not False):
            raise ValueError(f"Unsafe or stale context capsule for chunk {c['chunk']}")
        # Reloaded capsules are re-grounded to the original transcript. A local
        # file edited after stage 1 must not fabricate context across chunks.
        core=[u for u in all_segments if c["core_start"]<=u["start"]<c["core_end"]]
        candidates=[{"source_id":x.get("source_id"),
                     "exact_quote":x.get("exact_quote"),
                     "kind":x.get("kind_candidate")} for x in doc.get("anchors",[])]
        checked,rejected=validate_capsule({"anchors":candidates},core,c)
        if rejected or len(checked["anchors"])!=len(doc.get("anchors",[])) or any(
            x["id"]!=y.get("id") for x,y in zip(checked["anchors"],doc["anchors"])):
            raise ValueError(f"Untrusted context capsule evidence for chunk {c['chunk']}")
        capsules[c["chunk"]]=doc
    def one(c):
        local=text_context(all_segments,c)
        neighbors=adjacent_context(c["chunk"],capsules)
        neighbor_ids={a["id"] for v in neighbors.values() for a in v["anchors"]}
        visual_path=root/artifact_path("visual_scans",c)
        visual_observations=[];vision_by_id={}
        if visual_path.exists():
            visual_doc=json.loads(visual_path.read_text(encoding="utf8"))
            if (visual_doc.get('schema')!='artin_sampled_visual_scan_v1' or
                visual_doc.get('chunk')!=c['chunk'] or
                visual_doc.get('source_video_sha256')!=manifest['video_sha256'] or
                visual_doc.get('full_video_visual_content_verified') is not False or
                visual_doc.get('can_trade') is not False):
                raise ValueError('Unsafe or stale visual model output')
            frames={f['frame_id']:f for f in visual_doc.get('frames',[])}
            for v in visual_doc.get('observations',[]):
                frame=frames.get(v.get('frame_id'))
                if frame is None or v.get('frame_sha256')!=frame.get('sha256') or not (
                    c['core_start']<=frame['time_approx_seconds']<=c['core_end']):
                    raise ValueError('Visual observation has no matching video-frame evidence')
                frame_path=(root/frame['path']).resolve()
                if not frame_path.is_relative_to(root) or not frame_path.is_file() or file_sha256(frame_path)!=frame['sha256']:
                    raise ValueError('Visual frame missing, modified or path escapes working directory')
                vision_by_id[v['frame_id']]=v
                visual_observations.append({k:v[k] for k in (
                    'frame_id','time_approx_seconds','scene_type_candidate',
                    'visible_text_candidate','visual_description_candidate')})
        prompt=json.dumps({"chunk":c["chunk"],"core_start":c["core_start"],
                           "core_end":c["core_end"],
                           "transcript":local,"adjacent_five_minute_context":neighbors,
                           "sampled_visual_observations_unverified":visual_observations,
                           "instructions":("Use both neighboring 5-minute capsules to "
                             "understand questions continued from previous chunk and "
                             "answers/corrections clarified in next chunk. Ground every "
                             "event quote only to THIS chunk's owned source segments; "
                             "related_context_ids may only use adjacent anchor IDs. "
                             "related_visual_frame_ids may refer ONLY to supplied frame_id values. "
                             "Samples miss unsampled frames; visual descriptions are model guesses. "
                             "Never promote classroom troubleshooting to a trading rule. "
                             "No speaker or teacher-rule verification.")},ensure_ascii=False)
        frame_paths=[]
        if with_frames:
            frame_paths=[str(root/x["path"]) for x in c.get("frames",[])][:3]
        raw=ollama_json(model,prompt,frame_paths,endpoint)
        entries,rejected=validate_model_events(raw,local,c,neighbor_anchor_ids=neighbor_ids,
                                               visual_evidence=vision_by_id)
        # Collect an exact-time visual review frame for every grounded event.
        # This is visual EVIDENCE TO REVIEW, not automated chart interpretation.
        if with_frames:
            source_video=Path(manifest["video_path_private"])
            if not source_video.exists() or file_sha256(source_video)!=manifest["video_sha256"]:
                raise ValueError("Original video unavailable or different: cannot attach chart frames")
            for e in entries:
                when=min(manifest["source_duration"]-0.01, (e["start"]+e["end"])/2)
                frame=root/"evidence_frames"/(e["id"]+".jpg")
                frame.parent.mkdir(parents=True,exist_ok=True)
                run_cmd(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                         "-ss",str(round(when,3)),"-i",str(source_video),
                         "-frames:v","1","-vf","scale='min(960,iw)':-2",
                         "-q:v","5",str(frame)])
                e["near_speech_chart_frame"]={"at":round(when,3),
                    "path":str(frame.relative_to(root)),"sha256":file_sha256(frame),
                    "visual_interpretation_verified":False}
        doc={"schema":"artin_chunk_analysis_v1","chunk":c["chunk"],
             "transcript_ids":sorted({x["id"] for x in local}),
             "neighbor_capsules_used":{
                 "previous":neighbors["previous"]["chunk"],
                 "next":neighbors["next"]["chunk"]},
             "neighbor_context_is_grounds_for_review_not_rule":True,
             "sampled_visual_observations_available":len(visual_observations),
             "visual_interpretation_is_teacher_verified":False,
             "model_name":model,"interpretation_verified":False,
             "frame_count":len(frame_paths),"events":entries,"rejections":rejected}
        atomic_json(root/c["analysis"],doc)
        return doc
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(int(workers),len(manifest["chunks"]))) as ex:
        futures=[ex.submit(one,c) for c in manifest["chunks"]]
        out=[f.result() for f in concurrent.futures.as_completed(futures)]
    return sorted(out,key=lambda d:d["chunk"])


def _write_vtt(path:Path,utterances:list[dict]):
    def fmt(seconds):
        millis=max(0,round(seconds*1000))
        hrs,ms=divmod(millis,3600000);minutes,ms=divmod(ms,60000);secs,ms=divmod(ms,1000)
        return f"{hrs:02}:{minutes:02}:{secs:02}.{ms:03}"
    rows=["WEBVTT",""]
    for u in utterances:
        rows.append(f"{fmt(u['start'])} --> {fmt(u['end'])}")
        rows.append(u["text"].replace("-->","→").replace("\n"," "))
        rows.append("")
    path.write_text("\n".join(rows),encoding="utf8")


def _rule_graph(events):
    """Candidate graph, never a computed teacher-approved rule specification."""
    groups=defaultdict(list);links=[]
    for e in events:
        if e["kind"] in ("RULE","CORRECTION","EXCEPTION","EXAMPLE"):
            label=normalize_text(e["rule_label_candidate"])
            if label:
                groups[label].append(e)
    rules=[]
    for label,rows in sorted(groups.items()):
        rows.sort(key=lambda x:(x["start"],x["id"]))
        rules.append({"candidate_name":rows[-1]["rule_label_candidate"],
                      "normalized_name":label,"event_ids":[e["id"] for e in rows],
                      "candidate_decisions":sorted({e["decision_candidate"] for e in rows}),
                      "needs_teacher_qa_review":True,"source_video_verified":False,
                      "algorithmic_conditions_approved":False,
                      "artin_engine_rule_ready":False})
        for correction in (r for r in rows if r["kind"]=="CORRECTION"):
            prior=[r for r in rows if r["start"]<correction["start"] and r["id"]!=correction["id"]]
            if prior:
                links.append({"type":"POSSIBLE_CORRECTION_OF","from":correction["id"],
                              "to":prior[-1]["id"],"status":"NEEDS_ORIGINAL_AUDIO_VIDEO_AND_CONTEXT"})
    return rules,links


def _dialogue_graph(events,limit_seconds=240):
    """Nearest-next candidate answer is a review hint, not a teacher attribution."""
    edges=[]
    ordered=sorted(events,key=lambda x:(x["start"],x["id"]))
    for i,e in enumerate(ordered):
        if e["kind"]!="QUESTION":continue
        for f in ordered[i+1:]:
            if f["start"]-e["end"]>limit_seconds:break
            if f["kind"]=="ANSWER" and f["start"]>=e["start"]:
                edges.append({"type":"POSSIBLE_ANSWER_TO","from":f["id"],"to":e["id"],
                              "cross_chunk":f["chunk"]!=e["chunk"],
                              "status":"SPEAKER_AND_DIALOGUE_MUST_BE_CHECKED"})
                break
    return edges


def merge(root:Path,require_all=True):
    root=Path(root).resolve();m=load_manifest(root)
    if m.get("strict_chunk_order"):
        check_saved_clips(root,m)
    segment_col=[];issues=[];events=[];existing_analysis=0
    for c in m["chunks"]:
        path=root/c["transcript"]
        if path.exists():
            segment_col.extend(validate_transcript(c,json.loads(path.read_text(encoding="utf8"))))
        else:issues.append({"chunk":c["chunk"],"reason":"TRANSCRIPT_MISSING"})
    utterances,dupes=deduplicate_segments(segment_col)
    merged_ids={u["id"] for u in utterances}
    for c in m["chunks"]:
        path=root/c["analysis"]
        if not path.exists():
            issues.append({"chunk":c["chunk"],"reason":"SEMANTIC_ANALYSIS_MISSING"})
            continue
        a=json.loads(path.read_text(encoding="utf8"))
        if a.get("schema")!="artin_chunk_analysis_v1" or a.get("chunk")!=c["chunk"]:
            raise ValueError(f"Invalid analysis for chunk {c['chunk']}")
        existing_analysis+=1
        for e in a.get("events",[]):
            ids=e.get("source_ids",[])
            if (e.get("chunk")!=c["chunk"] or any(x not in merged_ids and x not in dupes for x in ids)
                or e.get("can_trade") is not False or e.get("status")!=SOURCE_FLAGS):
                issues.append({"chunk":c["chunk"],"reason":"UNTRUSTED_ANALYSIS_EVENT"});continue
            e=dict(e)
            e["source_ids"]=[dupes.get(x,x) for x in ids]
            events.append(e)
    events.sort(key=lambda x:(x["start"],x["end"],x["id"]))
    # Distinguish repeated same evidence on chunk overlaps from actual new information.
    seen=set();unique=[]
    for e in events:
        key=(e["kind"],tuple(sorted(e["source_ids"])),normalize_text(e["quote"]))
        if key not in seen:
            seen.add(key);unique.append(e)
    events=unique
    instructional_events,noise_quarantine=quarantine_events(events)
    rules,correction_edges=_rule_graph(instructional_events)
    dialogue_edges=_dialogue_graph(instructional_events)
    # Each neighbor reference is an auditable *hypothesis* grounded by a
    # neighboring segment. It cannot be used as an exact quote from this chunk.
    anchor_by_id={}
    for c in m["chunks"]:
        path=root/artifact_path("context_capsules",c)
        if path.exists():
            capsule=json.loads(path.read_text(encoding="utf8"))
            for anchor in capsule.get("anchors",[]):
                if anchor.get("id") in anchor_by_id:
                    issues.append({"chunk":c["chunk"],"reason":"DUPLICATE_CONTEXT_ANCHOR"})
                anchor_by_id[anchor.get("id")]=anchor
    context_edges=[]
    for e in instructional_events:
        for aid in e.get("related_context_ids",[]):
            neighbor=anchor_by_id.get(aid)
            if (neighbor is None or abs(neighbor["chunk"]-e["chunk"])!=1):
                issues.append({"chunk":e["chunk"],"reason":"INVALID_CROSS_CHUNK_CONTEXT_EDGE"})
                continue
            context_edges.append({"from_event":e["id"],"to_context_anchor":aid,
                                  "anchor_chunk":neighbor["chunk"],
                                  "status":"NEEDS_ORIGINAL_AUDIO_VIDEO_REVIEW",
                                  "may_modify_engine":False})
    complete=(len([x for x in issues if x["reason"] in (
        "TRANSCRIPT_MISSING","SEMANTIC_ANALYSIS_MISSING","UNTRUSTED_ANALYSIS_EVENT",
        "DUPLICATE_CONTEXT_ANCHOR","INVALID_CROSS_CHUNK_CONTEXT_EDGE")])==0 and
        len(m["chunks"])==existing_analysis)
    summary={"schema":"artin_full_lesson_diagnostic_v1",
             "video_sha256":m["video_sha256"],"chunk_count":len(m["chunks"]),
             "source_chunk_numbers_in_order":[x["chunk"] for x in m["chunks"]],
             "five_minute_chunk_order_validated":True,
             "transcript_utterances":len(utterances),
             "overlap_duplicate_utterances":len(dupes),
             "semantic_events":len(events),"candidate_rule_groups":len(rules),
             "quarantined_classroom_noise":len(noise_quarantine),
             "cross_chunk_context_review_edges":len(context_edges),
             "visual_evidence_references":sum(len(e.get("related_visual_frame_evidence",[])) for e in events),
             "possible_question_answer_links":len(dialogue_edges),
             "possible_later_corrections":len(correction_edges),
             "transcript_and_semantic_outputs_present":complete,
             "audio_video_independently_verified":False,
             "teacher_speaker_verified":False,
             "teacher_rules_approved":0,"artin_rule_ready":False,
             "backtest_valid":False,"live_or_demo_orders_sent":0,
             "issues":issues,
             "next_gate":"REVIEW_ORIGINAL_VIDEO_QA_CORRECTIONS_AND_CHART_EXAMPLES"}
    if require_all and not complete:
        # Still materialize a report for diagnosis, but never represent it as complete.
        atomic_json(root/"audit_report.json",summary)
        raise RuntimeError(f"Incomplete lesson: {len(issues)} issues (see audit_report.json)")
    atomic_json(root/"unified_timeline.json",{
        "schema":"artin_linked_timeline_v1", "source_video_sha256":m["video_sha256"],
        "segments":utterances,"semantic_candidates":events})
    atomic_json(root/"rule_candidate_graph.json",{
        "schema":"artin_rule_candidate_graph_v1","candidate_rules":rules,
        "candidate_dialogue_links":dialogue_edges,"candidate_correction_links":correction_edges,
        "candidate_neighbor_context_links":context_edges,
        "teacher_approved_rule_count":0,"may_modify_engine":False})
    # Explicit research handoff for implementing teacher rules AFTER audiovisual
    # validation. This is never an executable rule DSL or an MT5 strategy file.
    atomic_json(root/"noise_quarantine.json",{
        "schema":"artin_classroom_noise_review_v1",
        "quarantined_events":noise_quarantine,
        "not_deleted_from_original_audio_video":True,
        "may_change_engine":False})
    by_event={e["id"]:e for e in instructional_events}
    handoff=[]
    for rule in rules:
        linked=[by_event[x] for x in rule["event_ids"]]
        handoff.append({"candidate_rule":rule["candidate_name"],
                        "rule_id_in_existing_artin_engine":None,
                        "decision_candidates":[x["decision_candidate"] for x in linked],
                        "conditional_text_candidates":[{
                            "event_id":x["id"],"conditions":x["condition_candidates"],
                            "video_second":x["start"],"quote":x["quote"],
                            "source_segments":x["source_ids"],
                            "chart_frame":x.get("near_speech_chart_frame"),
                            "sampled_visual_frame_references":x.get("related_visual_frame_evidence",[])
                        } for x in linked],
                        "later_correction_edges":[x for x in correction_edges if
                            x["from"] in rule["event_ids"]],
                        "requires_qa_and_visual_review":True,
                        "has_positive_and_negative_teacher_examples":False,
                        "rule_verified":False,"engine_code_ready":False})
    atomic_json(root/"artin_engine_handoff.json",{
        "schema":"artin_candidate_rule_handoff_v1",
        "source_video_sha256":m["video_sha256"],
        "purpose":"CANDIDATES_FOR_MANUAL_TEACHER_REVIEW_AND_LATER_CODING_ONLY",
        "trade_permissions":0,"approved_rules":0,"candidate_rules":handoff})
    atomic_json(root/"audit_report.json",summary)
    _write_vtt(root/"unified_subtitles.vtt",utterances)
    return summary


def reconcile_global(root:Path,model:str,endpoint="http://127.0.0.1:11434"):
    """Second-pass global lesson consistency review; never approves teacher rules."""
    root=Path(root).resolve()
    timeline=json.loads((root/"unified_timeline.json").read_text(encoding="utf8"))
    graph=json.loads((root/"rule_candidate_graph.json").read_text(encoding="utf8"))
    events,_noise=quarantine_events(timeline["semantic_candidates"])
    known={x["id"]:x for x in events}
    # A whole-film pass sees candidate events, not 90 minutes of raw AV.
    # Scope is therefore limited to proposing links for AUDIOVISUAL REVIEW.
    task={"instructions":"Connect question to likely answer, later correction to earlier rule, or same rule across chunks. Do NOT claim teacher speaker or trading readiness. Return JSON with edges. Each edge has from, to, type, reason. Only event IDs provided here may be used. The from event MUST be later than to.",
          "events":[{k:e[k] for k in ('id','kind','start','end','chunk',
                    'quote','rule_label_candidate','decision_candidate')} for e in events]}
    model_data=ollama_json(model,json.dumps(task,ensure_ascii=False),endpoint=endpoint)
    valid=[];invalid=[];seen=set()
    for ix,e in enumerate(model_data.get('edges',[]) if isinstance(model_data,dict) else []):
        if not isinstance(e,dict):
            invalid.append({'index':ix,'reason':'NOT_AN_OBJECT'});continue
        src,dst,kind=e.get('from'),e.get('to'),e.get('type')
        if (kind not in ('POSSIBLE_QA','POSSIBLE_CORRECTION_OF','POSSIBLE_EXCEPTION_TO',
                         'POSSIBLE_RULE_CONTINUATION') or src not in known or dst not in known or
            known[src]['start']<=known[dst]['start'] or src==dst):
            invalid.append({'index':ix,'reason':'INVALID_OR_NONCHRONOLOGICAL_EDGE'});continue
        key=src,dst,kind
        if key in seen:continue
        seen.add(key)
        valid.append({'from':src,'to':dst,'type':kind,
                      'from_at':known[src]['start'],'to_at':known[dst]['start'],
                      'reason_is_only_model_hypothesis':str(e.get('reason',''))[:500],
                      'status':'NEEDS_ORIGINAL_AUDIO_VIDEO_REVIEW',
                      'teacher_verified':False,'may_change_engine':False})
    result={'schema':'artin_global_connection_suggestions_v1',
            'source_video_sha256':load_manifest(root)['video_sha256'],
            'model':model,'whole_video_really_watched':False,
            'inputs_are_chunk_candidate_summaries_only':True,
            'candidate_edges':valid,'rejected_edges':invalid,
            'approved_corrections':0,'can_trade':False}
    atomic_json(root/'global_connection_suggestions.json',result)
    return {'edges':len(valid),'rejected':len(invalid),
            'approved_corrections':0,'teacher_method_verified':False}


def chapters_for_ffmpeg(root:Path):
    """Local metadata chapter map: exact original VIDEO kept in order.

No narrative captions are burned into frames; sidecar JSON links Q&A and rules.
"""
    m=load_manifest(root)
    lines=[";FFMETADATA1", "comment=Artin research index; not teacher-verified"]
    for chunk in m["chunks"]:
        lines.extend(["[CHAPTER]","TIMEBASE=1/1000",
                      f"START={round(chunk['core_start']*1000)}",
                      f"END={round(chunk['core_end']*1000)}",
                      f"title=Batch {chunk['batch']:03d} Slot {chunk['slot']:02d} Global {chunk['chunk']:04d} - unverified"])
    p=Path(root)/"chapters.ffmetadata"
    p.write_text("\n".join(lines)+"\n",encoding="utf8")
    return p


def remux_chapters(root:Path,output:Path):
    root=Path(root).resolve();m=load_manifest(root)
    source=Path(m["video_path_private"])
    if not source.exists() or file_sha256(source)!=m["video_sha256"]:
        raise ValueError("Cannot reconstruct without unchanged exact original video")
    output=Path(output).resolve()
    if output==source or output.is_relative_to(root/"clips"):
        raise ValueError("Cannot replace original video or use clips folder")
    meta=chapters_for_ffmpeg(root)
    run_cmd(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
             "-i",str(source),"-f","ffmetadata","-i",str(meta),
             "-map","0","-map_metadata","1","-map_chapters","1", "-c","copy",str(output)])
    duration,_=probe_video(output)
    if abs(duration-m["source_duration"])>1:
        raise RuntimeError("Reconstructed video has incorrect duration")
    return {"output":str(output),"chapters":len(m["chunks"]),
            "original_sha256":m["video_sha256"],
            "semantic_overlay":"SIDE_CAR_JSON_AND_VTT_NOT_EMBEDDED_IN_VIDEO",
            "teacher_rules_verified":0}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    a=sub.add_parser("prepare",help="Split video into overlapping clips and sample chart frames")
    a.add_argument("--video",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    a.add_argument("--workers",type=int,default=3);a.add_argument("--frames-per-chunk",type=int,default=3)
    a.add_argument("--chunk-seconds",type=int,default=300)
    a=sub.add_parser("transcribe",help="Transcribe locally with user-installed faster-whisper")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--model-path",required=True)
    a.add_argument("--workers",type=int,default=1);a.add_argument("--device",default="cpu")
    a=sub.add_parser("capsules",help="First parallel pass: 5-minute grounded semantic context capsules")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--model",required=True)
    a.add_argument("--workers",type=int,default=2)
    a.add_argument("--endpoint",default="http://127.0.0.1:11434")
    a=sub.add_parser("vision",help="Inspect sampled source video frames using a LOCAL vision-capable Ollama model")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--model",required=True)
    a.add_argument("--workers",type=int,default=2);a.add_argument("--sample-seconds",type=int,default=20)
    a.add_argument("--max-images-per-request",type=int,default=4)
    a.add_argument("--endpoint",default="http://127.0.0.1:11434")
    a=sub.add_parser("analyze",help="Second parallel pass: each chunk sees previous/next 5-minute context")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--model",required=True)
    a.add_argument("--workers",type=int,default=2);a.add_argument("--with-frames",action="store_true")
    a.add_argument("--endpoint",default="http://127.0.0.1:11434")
    a.add_argument("--require-capsules",action="store_true")
    a=sub.add_parser("merge",help="Produce aligned timeline, dialogue links and candidate rule graph")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--allow-partial",action="store_true")
    a=sub.add_parser("reconcile",help="Optional full-film candidate rule and Q&A cross-link review on LOCAL Ollama")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--model",required=True)
    a.add_argument("--endpoint",default="http://127.0.0.1:11434")
    a=sub.add_parser("all",help="Run complete local workflow; requires local ASR and Ollama models")
    a.add_argument("--video",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    a.add_argument("--asr-model",required=True,help="Previously downloaded local faster-whisper model directory")
    a.add_argument("--ollama-model",required=True)
    a.add_argument("--workers",type=int,default=2)
    a.add_argument("--with-frames",action="store_true",help="Legacy alias: visual processing is already enabled by default")
    a.add_argument("--no-vision",action="store_true",help="Explicit incomplete audio-only diagnostic; NOT full video analysis")
    a.add_argument("--visual-sample-seconds",type=int,default=20)
    a.add_argument("--endpoint",default="http://127.0.0.1:11434")
    a=sub.add_parser("remux",help="Copy original video tracks plus exact 5-min chapter markers")
    a.add_argument("--out",type=Path,required=True);a.add_argument("--video-output",type=Path,required=True)
    args=p.parse_args(argv)
    if args.command=="prepare":
        result=prepare(args.video,args.out,args.workers,args.frames_per_chunk,args.chunk_seconds)
        report={"video_seconds":result["source_duration"],"chunks":len(result["chunks"]),
                "clips_created":result["parts_ready"],"teacher_rules_verified":0}
    elif args.command=="transcribe":
        report={"transcribed_chunks":len(transcribe(args.out,args.model_path,args.workers,args.device)),
                "transcript_verified_against_original_audio":False}
    elif args.command=="capsules":
        report={"grounded_context_capsules":len(build_context_capsules(
                    args.out,args.model,args.workers,args.endpoint)),
                "teacher_rule_verified":False}
    elif args.command=="vision":
        from artin_vision_scan import scan_vision
        v=scan_vision(args.out,args.model,args.workers,args.sample_seconds,
                      args.max_images_per_request,args.endpoint)
        report={"visual_chunks_scanned":len(v),"sampled_frames":sum(len(x['frames']) for x in v),
                "original_visuals_completely_understood":False}
    elif args.command=="analyze":
        report={"analyzed_chunks":len(analyze(args.out,args.model,args.workers,args.with_frames,
                    args.endpoint,require_capsules=args.require_capsules)),
                "neighbor_context_is_verified_teacher_rule":False}
    elif args.command=="merge":report=merge(args.out,require_all=not args.allow_partial)
    elif args.command=="reconcile":report=reconcile_global(args.out,args.model,args.endpoint)
    elif args.command=="all":
        # As requested: numbered five-minute clips are produced FIRST, even if
        # semantic models are missing; in that case only the safe split remains.
        prepared=prepare(args.video,args.out,args.workers,3)
        from artin_model_preflight import check
        readiness=check(args.asr_model,args.ollama_model,args.endpoint)
        checks=readiness['checks']
        if not checks['can_attempt_local_speech_transcription']:
            p.error('ASR unavailable: '+', '.join(readiness['recommendations']))
        if not checks['chosen_ollama_model_installed']:
            p.error('Local Ollama model unavailable: '+', '.join(readiness['recommendations']))
        if not args.no_vision and not checks['can_attempt_local_video_frame_understanding']:
            p.error('A verified locally installed Ollama vision-capable model is required for full video run')
        visual_enabled=not args.no_vision
        check_saved_clips(Path(args.out),prepared)
        transcribe(args.out,args.asr_model,workers=1) # protect RAM
        build_context_capsules(args.out,args.ollama_model,args.workers,args.endpoint)
        if visual_enabled:
            from artin_vision_scan import scan_vision
            scan_vision(args.out,args.ollama_model,args.workers,args.visual_sample_seconds,
                        4,args.endpoint)
        analyze(args.out,args.ollama_model,args.workers,visual_enabled,
                args.endpoint,require_capsules=True)
        report=merge(args.out)
        report['global_reconcile']=reconcile_global(args.out,args.ollama_model,args.endpoint)
        report['vision_model_run']=visual_enabled
        report['original_video_fully_covered_by_visual_samples']=False
        report['chaptered_video']=remux_chapters(args.out,Path(args.out)/'original_with_numbered_chapters.mp4')
    else:report=remux_chapters(args.out,args.video_output)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    sys.exit(main())
