#!/usr/bin/env python3
"""Generate *real* neural Persian voice WAV samples on an ephemeral CI runner.

Model: alifthi/persian-TTS, CC-BY-4.0, 7 speakers, 22050 Hz.
NO subscriber tokens, secrets or private user text. Does not install a model
on Amin's mobile phone or computer. No ChatGPT API / Codex / Work used.
A generated WAV does not prove naturalness or similarity to ChatGPT Voice.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import wave
from array import array
from pathlib import Path

MODEL_REPO = "https://huggingface.co/alifthi/persian-TTS"
DEMO_TEXT = (
    "سلام، من هوش امین هستم. با هم فارسی صحبت می‌کنیم. "
    "من سعی می‌کنم واضح، روان و دقیق جواب بدهم. "
    "اگر اینترنت قطع شود، پاسخ جدید هوشمند دریافت نمی‌کنم."
)


def inspect(path):
    with wave.open(str(path), "rb") as handle:
        rate, channels, width, frames = (
            handle.getframerate(), handle.getnchannels(),
            handle.getsampwidth(), handle.getnframes())
        if rate != 22050 or channels != 1 or width != 2 or not (15_000 < frames < 2_000_000):
            raise RuntimeError("Unexpected neural TTS WAV format or duration")
        pcm = array("h")
        pcm.frombytes(handle.readframes(frames))
        if sys.byteorder != "little":
            pcm.byteswap()
        if not pcm:
            raise RuntimeError("Neural TTS generated empty audio")
        rms = math.sqrt(sum(float(n) * float(n) for n in pcm) / len(pcm))
        peak = max(abs(int(n)) for n in pcm)
        if rms < 100 or peak < 300:
            raise RuntimeError("Neural TTS output is silent or inaudible")
        if rms > 31000:
            raise RuntimeError("Neural TTS output is heavily saturated")
    data = path.read_bytes()
    return {
        "filename": path.name, "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "duration_seconds": round(frames / rate, 2),
        "sample_rate_hz": rate, "channels": channels,
        "rms_pcm16": round(rms, 2), "peak_pcm16": peak,
        "real_audio_generated": True,
        "quality_equal_to_chatgpt_tested": False,
    }


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: generate_samples.py model.onnx model.onnx.json output_dir")
    model, config, output = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if not model.is_file() or model.stat().st_size < 60_000_000:
        raise RuntimeError("Model is missing or truncated; will not fake samples")
    settings = json.loads(config.read_text(encoding="utf8"))
    if settings.get("num_speakers") != 7 or settings.get("audio", {}).get("sample_rate") != 22050:
        raise RuntimeError("Unexpected licensed Persian neural voice configuration")
    output.mkdir(parents=True, exist_ok=True)
    tracks = []
    for speaker in range(7):
        path = output / f"amin_voice_candidate_{speaker}.wav"
        command = [
            sys.executable, "-m", "piper",
            "--model", str(model), "--config", str(config),
            "--output_file", str(path), "--speaker", str(speaker),
        ]
        completed = subprocess.run(
            command, input=DEMO_TEXT + "\n", text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=150)
        if completed.returncode != 0:
            print(completed.stderr[-1200:], file=sys.stderr)
            raise RuntimeError(f"Neural TTS speaker {speaker} failed (exit={completed.returncode})")
        result = inspect(path)
        result["speaker_id"] = speaker
        tracks.append(result)
        print(f"SPEAKER {speaker}: {result['duration_seconds']}s, "
              f"RMS={result['rms_pcm16']}, SHA={result['sha256'][:16]}")
    manifest = {
        "status": "generated_wav_files_on_ephemeral_runner",
        "model": "alifthi/persian-TTS",
        "model_license": "CC-BY-4.0",
        "required_attribution": "Ali Fathi; https://huggingface.co/alifthi/persian-TTS",
        "model_download_url": MODEL_REPO,
        "demo_text": DEMO_TEXT,
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "no_new_paid_api_or_codex": True,
        "contains_private_user_text": False,
        "chatgpt_voice_equivalence": "NOT_TESTED",
        "on_device_latency": "NOT_TESTED",
        "trained_new_amin_voice": False,
        "continuous_online_service": False,
        "tracks": tracks,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (output / "CREDITS.txt").write_text(
        "Neural Persian sample voice model: Ali Fathi, alifthi/persian-TTS\n"
        "License CC-BY-4.0: https://huggingface.co/alifthi/persian-TTS\n"
        "Samples are research prototypes based on existing speaker voices;\n"
        "they are not a newly trained, proprietary Amin voice or ChatGPT voice.\n",
        encoding="utf8")
    print("PASS: generated and objectively inspected 7 REAL neural Persian voice samples")


if __name__ == "__main__":
    main()
