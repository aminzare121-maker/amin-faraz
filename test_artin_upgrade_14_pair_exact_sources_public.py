"""Public no-private-media unit tests for original WAV source safety."""
import hashlib,io,unittest,wave
from artin_upgrade_14_pair_exact_sources import sha,verified_source,slice_verified

def audio_pcm(seconds=2,sr=16000):
    pcm=(b'\x00\x00\x03\x00')*(seconds*sr//2)
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(pcm)
    return out.getvalue()

class PublicExactSourceTests(unittest.TestCase):
    def test_valid_exact_source_and_length(self):
        b=audio_pcm();self.assertEqual(verified_source(b,sha(b),10,12),2)
    def test_reject_mismatched_hash(self):
        b=audio_pcm()
        with self.assertRaisesRegex(ValueError,'EXACT_ORIGINAL_WAV_SHA_MISMATCH'):
            verified_source(b,'0'*64,10,12)
    def test_reject_bad_duration_even_when_hash_matches(self):
        b=audio_pcm()
        with self.assertRaisesRegex(ValueError,'ORIGINAL_WAV_TIMEBASE_MISMATCH'):
            verified_source(b,sha(b),10,13)
    def test_reject_truncated_pcm_when_hash_matches(self):
        b=audio_pcm()[:-222]
        with self.assertRaisesRegex(ValueError,'ORIGINAL_WAV_PCM_TRUNCATED'):
            verified_source(b,sha(b),10,12)
    def test_reject_wrong_source_format(self):
        b=audio_pcm(sr=8000)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_WAV_SHAPE_MISMATCH'):
            verified_source(b,sha(b),10,12)
    def test_reject_clip_outside_original(self):
        b=audio_pcm()
        with self.assertRaisesRegex(ValueError,'EXCERPT_OUTSIDE_PINNED_ORIGINAL_WAV'):
            slice_verified(b,10,12,9.5,11)
    def test_reject_zero_length_clip(self):
        b=audio_pcm()
        with self.assertRaisesRegex(ValueError,'EXCERPT_OUTSIDE_PINNED_ORIGINAL_WAV'):
            slice_verified(b,10,12,11,11)
    def test_clip_matches_original_samples(self):
        b=audio_pcm()
        excerpt=slice_verified(b,10,12,10.5,11.75)
        with wave.open(io.BytesIO(b),'rb') as src, wave.open(io.BytesIO(excerpt),'rb') as clip:
            src.setpos(8000)
            self.assertEqual(src.readframes(20000),clip.readframes(20000))
            self.assertEqual(clip.getnframes(),20000)
if __name__=='__main__': unittest.main()