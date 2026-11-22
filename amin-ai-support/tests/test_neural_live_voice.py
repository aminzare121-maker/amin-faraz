"""Strict offline tests of the real PCM WSS neural voice production adapter.

The model and remote host are mocked in unit tests; a SEPARATE GitHub Actions
job downloads the real licensed model and invokes actual Piper inference.
"""
import base64
import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from neural_live_voice import (PiperPersianVoice, VoiceUnavailable,
                               split_text, text_for_speech, read_pcm16_wav,
                               from_environment)


def make_wav(out, *, rate=22050, duration=.72, magnitude=3100):
    samples = array("h", (
        round(magnitude*math.sin(2*math.pi*260*t/rate))
        for t in range(round(rate*duration))))
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())


class FakePiper:
    def __init__(self):
        self.commands = []
        self.texts = []
    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        self.texts.append(kwargs["input"])
        assert kwargs["timeout"] <= 55
        assert kwargs["text"] is True
        path = Path(cmd[cmd.index("--output_file")+1])
        make_wav(path)
        return CompletedProcess(cmd, 0, stdout="", stderr="")


class NeuralVoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.model = Path(self.temp.name)/"model.onnx"
        self.model.write_bytes(b"TEST ONLY: never loaded by actual ONNX")
        self.config = Path(self.temp.name)/"model.onnx.json"
        self.config.write_text(json.dumps({
            "num_speakers": 7, "audio": {"sample_rate": 22050}}))
        self.runner = FakePiper()

    def voice(self, speaker=2):
        return PiperPersianVoice(
            self.model, self.config, speaker,
            runner=self.runner, test_only_no_weight_size_check=True)

    def test_actual_pcm_format_and_digests_with_mocked_speech_source(self):
        output = list(self.voice().synthesize(
            "سلام امین. برای متاتریدر پنج و طلا، برنامه را مرور کنیم. "
            "چند دقیقه فرصت دارید؟"))
        self.assertTrue(1 <= len(output) <= 7)
        self.assertEqual(len(output), len(self.runner.commands))
        for i, frame in enumerate(output):
            self.assertEqual(frame["part_index"], i)
            self.assertEqual(frame["part_count"], len(output))
            self.assertEqual(frame["final"], i == len(output)-1)
            self.assertEqual(frame["sample_rate"], 22050)
            self.assertEqual(frame["encoding"], "pcm_s16le_base64")
            self.assertEqual(frame["voice_id"], "amin-persian-neural-v1")
            pcm = base64.b64decode(frame["data"])
            self.assertEqual(hashlib.sha256(pcm).hexdigest(), frame["sha256"])
            self.assertEqual(len(pcm) % 2, 0)
            self.assertGreater(frame["duration_seconds"], .5)
        # Test mode intentionally DOES NOT claim the model ran.
        self.assertEqual(self.runner.commands[0][0], sys.executable)

    def test_never_speak_code_urls_or_plaintext_tokens(self):
        phrase = text_for_speech(
            "سلام. [اطلاعات](https://one.example/private?a=1) "
            "github_pat_abcdefghijklmnopqrstuvwxyzSECRET123 "
            "```python\nprint('private')\n```")
        self.assertNotIn("one.example", phrase)
        self.assertNotIn("SECRET123", phrase)
        self.assertNotIn("print('private')", phrase)
        self.assertIn("اطلاعات", phrase)

    def test_split_is_bounded_and_does_not_lose_single_paragraph(self):
        chunks = split_text("باید تمام روش‌های بررسی برنامه را دقیق انجام بدهیم. " * 50)
        self.assertTrue(len(chunks) <= 7)
        self.assertTrue(all(len(c) <= 145 for c in chunks))
        self.assertTrue(all(c.strip() for c in chunks))
        with self.assertRaises(VoiceUnavailable):
            split_text("   ")

    def test_invalid_speaker_and_config_or_missing_model_denied(self):
        with self.assertRaisesRegex(VoiceUnavailable, "Speaker"):
            self.voice(7)
        with self.assertRaisesRegex(VoiceUnavailable, "incomplete"):
            PiperPersianVoice(self.model, self.config)
        self.config.write_text(json.dumps({
            "num_speakers": 1, "audio": {"sample_rate": 24000}}))
        with self.assertRaisesRegex(VoiceUnavailable, "Wrong Persian model"):
            self.voice()

    def test_truncated_saturated_or_wrong_rate_wav_is_rejected(self):
        out=Path(self.temp.name)/"test.wav"
        make_wav(out, rate=16000)
        with self.assertRaises(VoiceUnavailable):
            read_pcm16_wav(out)
        make_wav(out, magnitude=0)
        with self.assertRaisesRegex(VoiceUnavailable, "silent"):
            read_pcm16_wav(out)
        make_wav(out, duration=15.1)
        with self.assertRaises(VoiceUnavailable):
            read_pcm16_wav(out)
        out.write_bytes(b"not-wav")
        with self.assertRaises(VoiceUnavailable):
            read_pcm16_wav(out)

    def test_production_does_not_silently_download_model(self):
        with patch.dict(os.environ, {"AMIN_NEURAL_VOICE_ENABLE": "0"}):
            self.assertIsNone(from_environment())
        with patch.dict(os.environ, {"AMIN_NEURAL_VOICE_ENABLE":"1",
            "AMIN_NEURAL_MODEL_PATH": "", "AMIN_NEURAL_CONFIG_PATH":""}):
            with self.assertRaisesRegex(VoiceUnavailable, "explicitly installed"):
                from_environment()

    def test_nonzero_piper_exit_fails_closed_and_temporary_files_removed(self):
        def failed_runner(cmd, **kwargs):
            return CompletedProcess(cmd, 13, stdout="", stderr="sensitive private")
        voice = PiperPersianVoice(
            self.model, self.config, 2,
            runner=failed_runner, test_only_no_weight_size_check=True)
        with self.assertRaisesRegex(VoiceUnavailable, "failed"):
            list(voice.synthesize("سلام، حالت خوبه؟"))

    def test_voice_is_bounded_and_no_paid_fallback(self):
        frames=list(self.voice().synthesize("کوتاه", style=1))
        self.assertEqual(len(frames),1)
        self.assertFalse(any("openai" in " ".join(cmd).lower()
                              for cmd in self.runner.commands))
        with self.assertRaisesRegex(VoiceUnavailable, "style"):
            list(self.voice().synthesize("سلام",style=4))


if __name__ == "__main__":
    unittest.main()
