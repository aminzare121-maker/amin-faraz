#!/usr/bin/env python3
"""Real Persian neural speech on an *optional, authorized remote voice host*.

Does not run in the Android app or GitHub Actions continuously. A GitHub Actions
job can verify this code with REAL WAVs but cannot keep a permanent WSS alive.

Only authenticated owner-scoped WSS requests may call this module. The model
is CC-BY-4.0 Ali Fathi / alifthi/persian-TTS. No API key, Codex, Work, or
ChatGPT audio endpoint. Speech text never goes to GitHub or persisted logs.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from array import array
from pathlib import Path

MODEL_CREDIT = "Ali Fathi — https://huggingface.co/alifthi/persian-TTS (CC-BY-4.0)"
SAMPLE_RATE = 22050
MAX_INPUT = 700
MAX_CHUNK = 145
MAX_PARTS = 7
MAX_AUDIO_BYTES = 650_000
MAX_SECONDS = 14.5
VOICE_ID = "amin-persian-neural-v1"
ASCII_SECRET = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_-]{12,})")
URL = re.compile(r"(?i)https?://[^\s\]\)>]+")
CODE_BLOCK = re.compile(r"(?s)```.*?```")
MARKDOWN_LINK = re.compile(r"\[([^\]\r\n]{1,90})\]\(https?://[^)\s]+\)")


class VoiceUnavailable(RuntimeError):
    pass


def text_for_speech(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise VoiceUnavailable("Empty speech text")
    value = raw[:MAX_INPUT]
    value = CODE_BLOCK.sub(" بخشی از کد ", value)
    value = MARKDOWN_LINK.sub(r"\1", value)
    value = URL.sub(" پیوند اینترنتی ", value)
    value = ASCII_SECRET.sub(" اطلاعات محرمانه ", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = value.replace("ي", "ی").replace("ك", "ک")
    value = re.sub(r"(?i)(?<![A-Za-z])XAUUSD(?![A-Za-z])", "اونس طلای جهانی", value)
    value = re.sub(r"(?i)(?<![A-Za-z])MT5(?![A-Za-z])", "متاتریدر پنج", value)
    value = re.sub(r"(?i)(?<![A-Za-z])GitHub(?![A-Za-z])", "گیت هاب", value)
    value = re.sub(r"(?i)(?<![A-Za-z])ChatGPT(?![A-Za-z])", "چت جی پی تی", value)
    value = re.sub(r"(?i)(?<![A-Za-z])SL(?![A-Za-z])", "حد ضرر", value)
    value = re.sub(r"(?i)(?<![A-Za-z])TP(?![A-Za-z])", "حد سود", value)
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        raise VoiceUnavailable("No speakable text")
    return value


def split_text(text):
    """Bounded Persian phrase splitting without regex catastrophic backtracking."""
    text = text_for_speech(text)
    result, part = [], ""
    for word in text.split(" "):
        if len(word) > MAX_CHUNK:
            # Unreadable machine-generated word; don't synthesize it as a secret.
            word = "عبارت طولانی"
        if part and len(part) + 1 + len(word) > MAX_CHUNK:
            result.append(part)
            part = ""
        part = (part + " " + word).strip()
        if len(part) >= 55 and part[-1:] in "؟.!؛":
            result.append(part)
            part = ""
        if len(result) >= MAX_PARTS:
            break
    if part and len(result) < MAX_PARTS:
        result.append(part)
    if not result:
        raise VoiceUnavailable("No safe speech segments")
    return result


def read_pcm16_wav(wav_path):
    try:
        with wave.open(str(wav_path), "rb") as audio:
            rate = audio.getframerate()
            frames = audio.getnframes()
            if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                    or rate != SAMPLE_RATE or frames <= 2205
                    or frames > int(SAMPLE_RATE * MAX_SECONDS)):
                raise VoiceUnavailable("Unsupported neural speech format/duration")
            raw = audio.readframes(frames)
    except (EOFError, ValueError, wave.Error, OSError) as error:
        raise VoiceUnavailable("Neural speech WAV is incomplete") from error
    if not raw or len(raw) > MAX_AUDIO_BYTES or len(raw) != frames * 2:
        raise VoiceUnavailable("Neural speech packet exceeds safe size")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise VoiceUnavailable("No neural speech samples")
    rms = math.sqrt(sum(float(s) * float(s) for s in samples) / len(samples))
    peak = max(abs(int(s)) for s in samples)
    if rms < 100 or peak < 300 or rms > 31_000:
        raise VoiceUnavailable("Neural speech signal is silent or saturated")
    return raw, round(frames / SAMPLE_RATE, 3), round(rms, 1)


class PiperPersianVoice:
    def __init__(self, model: Path, config: Path, speaker=2, *,
                 runner=subprocess.run, test_only_no_weight_size_check=False):
        self.model = Path(model)
        self.config = Path(config)
        if not (self.model.is_file() and self.config.is_file()):
            raise VoiceUnavailable("Remote neural voice assets are not installed")
        if (not test_only_no_weight_size_check and
                self.model.stat().st_size < 60_000_000):
            raise VoiceUnavailable("Remote neural model file appears incomplete")
        if self.config.stat().st_size > 200_000:
            raise VoiceUnavailable("Model config too large")
        try:
            meta = json.loads(self.config.read_text(encoding="utf8"))
        except (ValueError, UnicodeError):
            raise VoiceUnavailable("Invalid model configuration") from None
        if (meta.get("audio", {}).get("sample_rate") != SAMPLE_RATE or
                meta.get("num_speakers") != 7):
            raise VoiceUnavailable("Wrong Persian model version")
        if not isinstance(speaker, int) or isinstance(speaker, bool) or speaker not in range(7):
            raise VoiceUnavailable("Speaker must be one of the seven licensed voices")
        self.speaker = speaker
        self.runner = runner

    def synthesize(self, text, *, style=0):
        if style not in (0, 1):
            raise VoiceUnavailable("Unknown voice style")
        parts = split_text(text)
        for index, phrase in enumerate(parts):
            # TemporaryDirectory cleans private spoken text AND WAV after each task.
            with tempfile.TemporaryDirectory(prefix="amin-voice-") as directory:
                out = Path(directory) / "speech.wav"
                cmd = [sys.executable, "-m", "piper", "--model", str(self.model),
                       "--config", str(self.config), "--output_file", str(out),
                       "--speaker", str(self.speaker)]
                # No shell or user-controlled CLI flags; response text only via stdin.
                try:
                    proc = self.runner(
                        cmd, input=phrase + "\n", text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=55)
                except (subprocess.TimeoutExpired, OSError):
                    raise VoiceUnavailable("Remote neural synthesis timed out") from None
                if proc.returncode != 0 or not out.is_file():
                    # Never put model, user text or stderr contents in client-visible errors.
                    raise VoiceUnavailable("Remote neural synthesis failed")
                pcm, duration, rms = read_pcm16_wav(out)
            if style == 1 and index < len(parts) - 1:
                # Deliberate Persian narration adds restrained phrase pauses;
                # do not alter the licensed model's timbre or fake voice pitch.
                silence = b"\\x00\\x00" * int(SAMPLE_RATE * 0.16)
                pcm += silence
                duration = round(duration + 0.16, 3)
                if len(pcm) > MAX_AUDIO_BYTES:
                    raise VoiceUnavailable("Narration pause exceeds safe packet size")
            yield {
                "encoding": "pcm_s16le_base64", "sample_rate": SAMPLE_RATE,
                "channels": 1, "speaker": self.speaker,
                "voice_id": VOICE_ID,
                "credit": MODEL_CREDIT,
                "part_index": index, "part_count": len(parts),
                "final": index == len(parts)-1,
                "sha256": hashlib.sha256(pcm).hexdigest(),
                "data": base64.b64encode(pcm).decode("ascii"),
                "duration_seconds": duration, "rms": rms,
            }


def from_environment():
    """Opt-in only; never download or silently launch/install a model."""
    if os.environ.get("AMIN_NEURAL_VOICE_ENABLE") != "1":
        return None
    model = os.environ.get("AMIN_NEURAL_MODEL_PATH", "").strip()
    config = os.environ.get("AMIN_NEURAL_CONFIG_PATH", "").strip()
    if not model or not config:
        raise VoiceUnavailable("Enable voice only with an explicitly installed remote model")
    raw = os.environ.get("AMIN_NEURAL_SPEAKER_ID", "2")
    if not raw.isdigit():
        raise VoiceUnavailable("Invalid neural voice speaker setting")
    return PiperPersianVoice(Path(model), Path(config), int(raw))
