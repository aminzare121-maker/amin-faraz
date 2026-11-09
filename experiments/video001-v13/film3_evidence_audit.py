#!/usr/bin/env python3
"""V13 read-only audit of prior authentic Artin film-3 GitHub artifacts.

Checks original 18-chunk/17-worker coverage, SHA for sampled original
audio payloads, timestamps and all 16 OCR partition receipts.
Does not perform model inference or certify teacher understanding.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile


def read_zip_json(path, member):
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read(member))


def validate_original_parts(manifest):
    try:
        duration = float(manifest.get("duration_seconds", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid duration") from exc
    count = math.ceil(duration / 300) if math.isfinite(duration) and duration > 0 else 0
    parts = manifest.get("parts")
    if not count or not isinstance(parts, list) or len(parts) != count:
        raise ValueError("missing or extra original chunks")
    if [p.get("chunk") for p in parts if isinstance(p, dict)] != list(range(1, count + 1)):
        raise ValueError("duplicate/misordered original chunks")
    if abs(parts[0]["core_start"]) > .001 or abs(parts[-1]["core_end"] - duration) > .01:
        raise ValueError("original start/end drift")
    for i, p in enumerate(parts):
        if i and abs(p["core_start"] - parts[i - 1]["core_end"]) > .01:
            raise ValueError("original timeline gap/overlap")
        if p["cut_start"] > p["core_start"] or p["cut_end"] < p["core_end"]:
            raise ValueError("audio context missing")
    return count


def zipped_sha256(archive, name):
    h = hashlib.sha256()
    with archive.open(name) as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(root):
    root = Path(root)
    summary = read_zip_json(root / "artin-film3-source-summary.zip", "safe_source_prep_summary.json")
    manifest = read_zip_json(root / "artin3-audio-worker0.zip", "fast_av_manifest.json")
    temporal = read_zip_json(root / "artin3-temporal.zip", "original_second_by_second_chat_index.json")
    index = read_zip_json(root / "artin3-chat-index.zip", "chat_selected_index.json")
    digest = manifest["video_sha256"]
    assert summary["source_video_sha256"] == temporal["source_video_sha256"] == index["source_video_sha256"] == digest
    duration = manifest["duration_seconds"]
    assert abs(summary["original_duration_seconds"] - duration) < .001
    assert abs(temporal["video_duration_seconds"] - duration) < .001
    assert abs(index["original_video_seconds"] - duration) < .001
    count = validate_original_parts(manifest)
    assert count == summary["source_global_audio_chunks"] == 18
    assert summary["source_audio_worker_count"] == 17
    assignments = [[p["chunk"] for p in manifest["parts"] if (p["chunk"] - 1) % 17 == n]
                   for n in range(17)]
    assert assignments[0] == [1, 18]
    assert sorted(j for row in assignments for j in row) == list(range(1, 19))
    checked_audio = []
    for worker in (0, 16):
        with zipfile.ZipFile(root / f"artin3-audio-worker{worker}.zip") as z:
            m = json.loads(z.read("fast_av_manifest.json"))
            assert m["video_sha256"] == digest and len(m["parts"]) == 18
            files = sorted(name for name in z.namelist() if name.endswith(".wav"))
            required = sorted(manifest["parts"][i-1]["audio"] for i in assignments[worker])
            assert files == required
            for i in assignments[worker]:
                part = manifest["parts"][i - 1]
                assert zipped_sha256(z, part["audio"]) == part["audio_sha256"]
                checked_audio.append(i)
    assert len(temporal["rows"]) == temporal["sampled_source_frames"] == summary["one_second_frames_scanned"] == 5157
    assert len(index["rows"]) == index["frames_selected"] == summary["original_chat_images_selected"] == 243
    frames = {r["frame_id"]: r for r in index["rows"]}
    assert len(frames) == 243
    for frame in index["rows"]:
        assert 0 <= frame["time_seconds"] < duration
        assert frame["global_chunk"] == int(frame["time_seconds"] // 300) + 1
    ocr_frames = set()
    for worker in range(16):
        d = read_zip_json(root / f"artin3-ocr-worker{worker}.zip", "full_chat_ocr_candidates_PRIVATE.json")
        assert d["source_video_sha256"] == digest and d["partition_index"] == worker
        assert d["partition_count"] == 16 and d["complete"] is True
        assert d["frames_targeted"] == d["frames_attempted"] == len(d["results"])
        for row in d["results"]:
            frame_id = row["frame_id"]
            assert frame_id in frames and frame_id not in ocr_frames
            assert row["source_frame_sha256"] == frames[frame_id]["chat"]["sha256"]
            assert abs(row["time_original_video_seconds"] - frames[frame_id]["time_seconds"]) < .001
            assert row["state"] != "OCR_EXECUTION_FAILED"
            ocr_frames.add(frame_id)
    assert ocr_frames == set(frames)
    assert summary["original_board_frames"] == 172
    return {
        "schema": "video001_v13_film3_offline_proof_v1",
        "result": "PASS_EVIDENCE_ONLY_NOT_COMPLETE_TRANSCRIPTION",
        "source_sha256": digest, "duration_seconds": duration,
        "global_audio_chunks": count, "asr_workers": 17,
        "worker_0_chunks": assignments[0],
        "sha_verified_audio_chunks": sorted(checked_audio),
        "timed_frames": len(temporal["rows"]), "original_chat_ocr_frames": len(ocr_frames),
        "reported_board_frames": 172, "ocr_worker_outputs": 16,
        "previous_source_preparation_seconds": summary["elapsed_seconds"],
        "three_minute_full_film_target_proven": False,
        "complete_third_film_asr_proven": False,
        "four_external_model_adapters_executed": False,
        "teacher_rules_verified": False,
        "note": "Only existing film-3 artifacts were used; no source video or model was rerun."
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    result = audit(args.artifacts)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
