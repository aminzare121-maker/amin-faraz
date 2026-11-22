#!/usr/bin/env python3
"""Play authenticated neural PCM chunks in Windows RAM, no local ONNX model.

No private transcript, provider key, WAV or voice weights are saved. On
non-Windows OS use an explicitly injected test speaker, never fake playback.
"""
from __future__ import annotations
import base64
import hashlib
import io
import re
import sys
import wave


class WindowsVoiceUnavailable(RuntimeError):
    pass


class WindowsNeuralSpeaker:
    def __init__(self, *, audio_sink=None):
        if audio_sink is None:
            if sys.platform != "win32":
                raise WindowsVoiceUnavailable("Live PCM speaker is Windows-only")
            import winsound
            audio_sink = lambda wav: winsound.PlaySound(wav, winsound.SND_MEMORY)
        self.audio_sink = audio_sink
        self.request_id = ""
        self.next_index = 0
        self.parts = 0
        self.finished = False
        self.heard_any = False

    def begin(self, ident):
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident):
            raise WindowsVoiceUnavailable("Invalid voice stream id")
        self.request_id = ident
        self.next_index = 0
        self.parts = 0
        self.finished = False
        self.heard_any = False

    def accept(self, packet):
        if packet.get("id") != self.request_id or not self.request_id:
            raise WindowsVoiceUnavailable("Wrong voice request id")
        if self.finished:
            raise WindowsVoiceUnavailable("Voice replay refused")
        try:
            idx = packet["part_index"]
            count = packet["part_count"]
            if (packet.get("voice_id") != "amin-persian-neural-v1"
                    or packet.get("encoding") != "pcm_s16le_base64"
                    or packet.get("sample_rate") != 22050
                    or packet.get("channels") != 1
                    or type(packet.get("speaker")) is not int
                    or packet.get("speaker") not in range(7)
                    or type(idx) is not int or type(count) is not int
                    or count not in range(1, 8)
                    or idx != self.next_index or idx not in range(count)
                    or (self.parts and self.parts != count)
                    or packet.get("final") is not (idx == count-1)):
                raise WindowsVoiceUnavailable("Incorrect PCM speaker frame")
            sha = packet.get("sha256", "")
            data = packet.get("data", "")
            if (not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{64}", sha)
                    or not isinstance(data, str) or len(data) > 900000):
                raise WindowsVoiceUnavailable("Invalid PCM payload")
            pcm = base64.b64decode(data, validate=True)
            if not 1024 <= len(pcm) <= 650000 or len(pcm) % 2:
                raise WindowsVoiceUnavailable("PCM size invalid")
            if hashlib.sha256(pcm).hexdigest() != sha:
                raise WindowsVoiceUnavailable("PCM hash mismatch")
        except (KeyError, TypeError, ValueError, base64.binascii.Error) as exc:
            raise WindowsVoiceUnavailable("Malformed audio packet") from None

        memory = io.BytesIO()
        with wave.open(memory, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(pcm)
        # The injected speaker or Windows native winsound plays the REAL WAV.
        # If it errors, report failure; do not claim audio was heard.
        self.audio_sink(memory.getvalue())
        self.parts = count
        self.next_index += 1
        self.heard_any = True
        if idx == count-1:
            self.finished = True
        return self.finished
