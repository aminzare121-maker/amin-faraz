"""Only model-independent Windows PCM protocol is tested on Linux CI."""
import base64
import hashlib
import unittest
from windows_neural_speaker import WindowsNeuralSpeaker, WindowsVoiceUnavailable


class WindowsVoiceTests(unittest.TestCase):
    def setUp(self):
        self.played = []
        self.speaker = WindowsNeuralSpeaker(audio_sink=self.played.append)
        self.speaker.begin("pc1")
        self.pcm = b"\x31\x00" * 12000

    def frame(self, *, index=0, total=1, ident="pc1", pcm=None):
        raw = pcm if pcm is not None else self.pcm
        return {
            "type":"voice_frame", "id":ident, "voice_id":"amin-persian-neural-v1",
            "encoding":"pcm_s16le_base64", "sample_rate":22050,
            "channels":1, "speaker":2,
            "part_index":index, "part_count":total, "final":index==total-1,
            "data":base64.b64encode(raw).decode("ascii"),
            "sha256":hashlib.sha256(raw).hexdigest(),
        }

    def test_pcm_voice_is_really_encoded_for_native_windows_wav_sink(self):
        self.assertTrue(self.speaker.accept(self.frame()))
        self.assertTrue(self.played)
        self.assertTrue(self.played[0].startswith(b"RIFF"))
        self.assertEqual(self.played[0][8:12], b"WAVE")
        self.assertIn(self.pcm, self.played[0])
        self.assertTrue(self.speaker.heard_any)
        with self.assertRaisesRegex(WindowsVoiceUnavailable, "replay"):
            self.speaker.accept(self.frame())

    def test_request_isolation_digest_and_chunk_order(self):
        with self.assertRaisesRegex(WindowsVoiceUnavailable, "request"):
            self.speaker.accept(self.frame(ident="other"))
        bad=self.frame()
        bad["sha256"]="0"*64
        with self.assertRaisesRegex(WindowsVoiceUnavailable, "hash"):
            self.speaker.accept(bad)
        with self.assertRaisesRegex(WindowsVoiceUnavailable, "frame"):
            self.speaker.accept(self.frame(index=1, total=2))
        with self.assertRaisesRegex(WindowsVoiceUnavailable, "frame"):
            self.speaker.accept(self.frame(index=0, total=8))
        self.assertEqual(self.played, [])
        self.speaker.accept(self.frame(index=0,total=2))
        self.assertTrue(self.speaker.accept(self.frame(index=1,total=2)))
        self.assertEqual(len(self.played),2)

    def test_invalid_audio_or_rate_refused_without_playing(self):
        for change in ({"sample_rate":16000},{"encoding":"mp3"},{"channels":2},
                       {"data":"?","sha256":"0"*64},
                       {"speaker":-1}):
            frame=self.frame()
            frame.update(change)
            with self.subTest(change=change), self.assertRaises(WindowsVoiceUnavailable):
                self.speaker.accept(frame)
        self.assertEqual(self.played, [])


if __name__=="__main__":
    unittest.main()
