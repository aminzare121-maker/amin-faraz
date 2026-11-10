"""Public synthetic fixtures only. No private course frames or voice recordings."""
import hashlib
import io
import unittest
import wave
import zipfile
from artin_restored_av_window_gate_v2 import audit

def _wav():
    buf=io.BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b'\x00\x00' * (8000*10))
    return buf.getvalue()

def fixture():
    samples={"frames/sample_t0000012500_original.jpg":b'synthetic frame #1',
             "frames/sample_t0000009500_original.jpg":b'synthetic margin frame'}
    framebuf=io.BytesIO()
    with zipfile.ZipFile(framebuf,'w') as z:
        for name,data in samples.items():z.writestr(name,data)
    audio=_wav()
    audiobuf=io.BytesIO()
    with zipfile.ZipFile(audiobuf,'w') as z:z.writestr('synthetic.wav',audio)
    original_frames=[{'source_time_seconds':t,'source_member':name,
            'original_frame_sha256':hashlib.sha256(data).hexdigest()}
            for (name,data),t in zip(samples.items(),[12.5,9.5])]
    c={'id':'EXAMPLE-01','queue_video':20,'route':'SYNTHETIC_ROUTE',
       'citation_start_seconds':12,'citation_end_seconds':14,
       'clip_start_seconds':9,'clip_end_seconds':19,
       'original_fullres_frames_inside_citation':[12.5],
       'original_fullres_frames_inside_clip_margin':[9.5,12.5],
       'declared_clip':'synthetic.wav'}
    p={'original_frames':original_frames,
       'audio_clips':{'synthetic.wav':{'sha256':hashlib.sha256(audio).hexdigest(),
            'rate_hz':8000,'channels':1,'duration_seconds':10}},
       'citation_windows':[c],'aliases':[]}
    framebuf.seek(0);audiobuf.seek(0)
    return p,framebuf,audiobuf

class PublicSyntheticTests(unittest.TestCase):
    def test_verified_frame_vs_margin(self):
        p,f,a=fixture();r=audit(p,f,a)
        self.assertEqual(r['video20_citations_with_strict_in_window_frame'],1)
        self.assertEqual(r['cases'][0]['frames_exclusively_in_audio_margin'],[9.5])
        self.assertEqual(r['trading_orders_authorized'],0)
    def test_bad_audio_digest_rejected(self):
        p,f,a=fixture();p['audio_clips']['synthetic.wav']['sha256']='0'*64
        with self.assertRaises(ValueError):audit(p,f,a)
    def test_bad_frame_digest_rejected(self):
        p,f,a=fixture();p['original_frames'][0]['original_frame_sha256']='0'*64
        with self.assertRaises(ValueError):audit(p,f,a)
    def test_fake_in_window_frame_rejected(self):
        p,f,a=fixture();p['citation_windows'][0]['original_fullres_frames_inside_citation']=[9.5,12.5]
        with self.assertRaises(ValueError):audit(p,f,a)
    def test_invalid_clip_span_rejected(self):
        p,f,a=fixture();p['citation_windows'][0]['clip_end_seconds']=13
        with self.assertRaises(ValueError):audit(p,f,a)
    def test_missing_audio_rejected(self):
        p,f,a=fixture();p['citation_windows'][0]['declared_clip']='missing.wav'
        with self.assertRaises(ValueError):audit(p,f,a)

if __name__ == '__main__':unittest.main()
