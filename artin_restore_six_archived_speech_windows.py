#!/usr/bin/env python3
"""Recover six omitted timed ASR windows from original source artifacts.

The archive/machine words and original audio are source-linked, not independently
reviewed teacher interpretation. All outputs are private review evidence. This
module has NO access to broker, MT5, trades, or any market data.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import wave
import zipfile
from pathlib import Path

REGISTRY_VIDEO_SHA = {
    20: "6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9",
    22: "8214f077a05969730c21015dc0f24c489835a9d1a9e9e3be4f73cca1000992ca",
}
ARTIFACTS = {
    "20-14": {"asr": "v20_asr13.zip", "audio": "v20_original_audio13.zip", "asr_artifact_id": 13675544193, "audio_artifact_id": 13675558632, "part": 14},
    "20-15": {"asr": "v20_asr14.zip", "audio": "v20_original_audio14.zip", "asr_artifact_id": 13676943594, "audio_artifact_id": 13675718418, "part": 15},
    "22-16": {"asr": "v22_asr15.zip", "audio": "v22_original_audio15.zip", "asr_artifact_id": 13679119588, "audio_artifact_id": 13679791669, "part": 16},
}
WINDOWS = (
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 20, 4100.0, 4133.0, 21, "20-14"),
    ("STOPPUNCH_SAME_COLOUR", 20, 4201.30, 4208.84, 21, "20-15"),
    ("STOPPUNCH_DOJI_AHEAD", 20, 4210.14, 4214.52, 21, "20-15"),
    ("STOPPUNCH_DOJI_TIED", 20, 4210.14, 4214.52, 21, "20-15"),
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 20, 4214.52, 4223.26, 21, "20-15"),
    ("STOPPUNCH_OPPOSITE_CONFIRMATION", 22, 4694.0, 4728.0, 23, "22-16"),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_member(z: zipfile.ZipFile, suffix: str) -> dict:
    names = [x.filename for x in z.infolist() if x.filename.endswith(suffix)]
    if len(names) != 1:
        raise ValueError(f"exactly one expected source {suffix} required")
    info = z.getinfo(names[0])
    if info.file_size > 4 * 1024 * 1024 or info.flag_bits & 1:
        raise ValueError("invalid source JSON metadata")
    return json.loads(z.read(info))


def _one_original_audio(z: zipfile.ZipFile, part: int) -> bytes:
    expected = f"audio/batch_001/part_{part}.wav"
    if expected not in z.namelist() or z.namelist().count(expected) != 1:
        raise ValueError("original audio member absent/duplicated")
    info = z.getinfo(expected)
    if info.file_size > 20_000_000 or info.file_size < 100_000:
        raise ValueError("audio member size out of bounds")
    return z.read(expected)


def read_verified_chunk(directory: Path, key: str) -> dict:
    cfg = ARTIFACTS[key]
    queue_video = int(key.split("-")[0])
    expected_video_sha = REGISTRY_VIDEO_SHA[queue_video]
    with zipfile.ZipFile(directory / cfg["asr"]) as archive:
        if len(archive.infolist()) != 2:
            raise ValueError("unexpected original ASR archive members")
        asr = _json_member(archive, f"part_{cfg['part']:03d}_unverified.json")
    with zipfile.ZipFile(directory / cfg["audio"]) as archive:
        manifest = _json_member(archive, "fast_av_manifest.json")
        wav = _one_original_audio(archive, cfg["part"])
    if asr.get("source_video_sha256") != expected_video_sha or manifest.get("video_sha256") != expected_video_sha:
        raise ValueError("video source identity mismatch")
    if asr.get("global_chunk") != cfg["part"]:
        raise ValueError("incorrect ASR chunk identity")
    part = next((p for p in manifest.get("parts", ()) if p.get("chunk") == cfg["part"]), None)
    if not part:
        raise ValueError("original AV part metadata missing")
    wav_sha = digest(wav)
    if part.get("audio_sha256") != wav_sha or asr.get("source_audio_sha256") != wav_sha:
        raise ValueError("original WAV bytes do not match both source manifests")
    if part.get("audio") != f"audio/batch_001/part_{cfg['part']}.wav":
        raise ValueError("WAV source path mismatch")
    if asr.get("timebase") != "absolute_original_video_seconds":
        raise ValueError("ASR timebase mismatch")
    segments = asr.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("missing ASR segments")
    last = -1.0
    for s in segments:
        a,b = s.get("start"),s.get("end")
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)):
            raise ValueError("invalid ASR times")
        if a < part["cut_start"] or b > part["cut_end"] + .01 or a >= b or a < last - .01:
            raise ValueError("ASR timed source interval invalid")
        last = a
    with wave.open(io.BytesIO(wav), "rb") as f:
        audio_shape = {"channels": f.getnchannels(), "sample_width": f.getsampwidth(),
                       "rate": f.getframerate(), "frames": f.getnframes()}
    if audio_shape["channels"] != 1 or audio_shape["sample_width"] != 2 or audio_shape["rate"] != 16000:
        raise ValueError("unexpected source audio format")
    secs = audio_shape["frames"] / audio_shape["rate"]
    if abs(secs - (part["cut_end"]-part["cut_start"])) > .02:
        raise ValueError("audio duration is not aligned to source film time")
    return {**cfg, "queue_video": queue_video, "key": key, "asr": asr, "manifest_part": part,
            "audio": wav, "audio_sha256": wav_sha, "video_sha256": expected_video_sha,
            "audio_shape": audio_shape}


def audio_excerpt(source: dict, begin: float, finish: float, margin: float = 5.0) -> tuple[bytes, float, float]:
    p = source["manifest_part"]
    a = max(float(p["cut_start"]), begin-margin)
    b = min(float(p["cut_end"]), finish+margin)
    if b <= a:
        raise ValueError("requested sample outside original WAV")
    with wave.open(io.BytesIO(source["audio"]), "rb") as w:
        sample_rate = w.getframerate()
        start_frame = round((a-p["cut_start"])*sample_rate)
        frames = round((b-a)*sample_rate)
        w.setpos(start_frame)
        data = w.readframes(frames)
        result = io.BytesIO()
        with wave.open(result,"wb") as target:
            target.setnchannels(w.getnchannels())
            target.setsampwidth(w.getsampwidth())
            target.setframerate(sample_rate)
            target.writeframes(data)
    return result.getvalue(), a, b


def restore(directory: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = {key: read_verified_chunk(directory,key) for key in ARTIFACTS}
    windows=[]
    for i,(rule,video,start,end,legacy,key) in enumerate(WINDOWS,1):
        item=source[key]
        p=item["manifest_part"]
        if start < p["core_start"]-0.01 or end > p["core_end"] + .01:
            # Boundary window may overlap the next chunk at most 12 seconds;
            # only preserve it if the original audio really contains it.
            if start < p["cut_start"] or end > p["cut_end"]:
                raise ValueError("citation out of actual source audio cut")
        segs=[s for s in item["asr"]["segments"] if s["start"] < end and s["end"] > start]
        if not segs:
            raise ValueError("no recovered ASR text within an allegedly recovered window")
        clip,clip_start,clip_end=audio_excerpt(item,start,end)
        name=f"source_window_{i:02d}_video{video:02d}_{round(start)}-{round(end)}.wav"
        (output/name).write_bytes(clip)
        windows.append({
            "source_window_id": f"ARTIN-RESTORED-{i:02d}",
            "entry_rule_id": rule,"legacy_session": legacy,"queue_video":video,
            "video_sha256":item["video_sha256"],"start_seconds":start,"end_seconds":end,
            "source_audio_sha256":item["audio_sha256"],
            "original_audio_artifact_id":item["audio_artifact_id"],
            "original_asr_artifact_id":item["asr_artifact_id"],
            "original_asr_chunk":item["part"],
            "source_audio_cut_start_seconds":p["cut_start"],
            "source_audio_cut_end_seconds":p["cut_end"],
            "audio_excerpt_file":name,"audio_excerpt_sha256":digest(clip),
            "audio_excerpt_source_from_seconds":clip_start,"audio_excerpt_source_until_seconds":clip_end,
            "recovered_machine_asr_segments":[{
                "asr_id":s["id"],"start":s["start"],"end":s["end"],
                "text_unverified":s["text"],"speaker_status":s.get("speaker","UNKNOWN")
            } for s in segs],
            "source_identity_sha_verified":True,
            "independent_acoustic_transcription_verified":False,
            "teacher_speaker_verified":False,"teacher_meaning_verified":False,
            "trade_permitted":False,
        })
    report={
        "schema":"artin_six_citation_source_speech_and_original_audio_restoration_v1",
        "source":"GitHub Actions exact original audio and ASR shards for current queue videos 20 and 22",
        "restored_citation_windows":len(windows),
        "unique_restored_windows":len({(x["queue_video"],x["start_seconds"],x["end_seconds"]) for x in windows}),
        "verified_distinct_source_audio_chunks":len(source),
        "video_registry_identity_verified":True,
        "original_audio_chunk_sha_verification_passed":True,
        "source_text_filled_with_timed_machine_asr":True,
        "teacher_speech_independently_heard_and_verified":False,
        "teacher_strategy_semantics_certified":False,
        "financial_backtest_authorized":False,"orders_sent":0,
        "private_review_windows":windows,
        "note":"Do not re-label ASR as verified teacher speech; some ASR text may contain recognition errors."
    }
    (output/"ARTIN_RESTORED_SIX_AUDIO_AND_MACHINE_SPEECH_PRIVATE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    public={k:v for k,v in report.items() if k!="private_review_windows"}
    public["windows"]= [{k:w[k] for k in ("source_window_id","entry_rule_id","legacy_session","queue_video","start_seconds","end_seconds","video_sha256","source_audio_sha256","original_audio_artifact_id","original_asr_artifact_id","original_asr_chunk","source_identity_sha_verified","independent_acoustic_transcription_verified","teacher_speaker_verified","teacher_meaning_verified","trade_permitted")} for w in windows]
    (output/"ARTIN_RESTORED_SIX_SOURCE_PROVENANCE_PUBLIC.json").write_text(json.dumps(public,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,default=Path("/mnt/data"))
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    r=restore(args.inputs,args.output)
    print(json.dumps({"restored":r["restored_citation_windows"],"audio":r["verified_distinct_source_audio_chunks"],"speaker_verified":False,"orders_sent":0}))

if __name__=="__main__":
    main()