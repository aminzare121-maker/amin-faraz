"""Self-contained synthetic regression tests for publicly shareable CI."""
import hashlib
import io
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from artin_packet_coverage_v2 import audit_packet


def fixture():
    b=io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000)
        w.writeframes(b'\0\0' * 8000 * 2)
    wav=b.getvalue();image=b'FAKE FRAME NOT AN ORIGINAL IMAGE'
    m={'unique_audio_clips':[{'filename':'synthetic.wav','sha256':hashlib.sha256(wav).hexdigest(),
        'duration_seconds':2.0}],
        'images':[{'filename':'synthetic.jpg','source_second':10,'sha256':hashlib.sha256(image).hexdigest()}],
        'windows':[{'id':'SYNTHETIC','queue_video':20,'clip':'synthetic.wav',
        'audio_start':10.0,'audio_end':12.0,'start':10.1,'end':11.9,
        'asr':[{'id':'synthetic_asr','start':11.5,'end':12.5,
        'audio_excerpt_truncated':True,'audible_end_seconds':12.0}]}]}
    return m,{'synthetic.wav':wav,'synthetic.jpg':image}

class PublicTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'packet.zip'
        self.manifest,self.files=fixture();self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):
        with zipfile.ZipFile(self.path,'w') as z:
            z.writestr('manifest.json',json.dumps(self.manifest))
            for name,data in self.files.items():z.writestr(name,data)
    def test_partial_audio_held(self):
        r=audit_packet(self.path);s=r['cases'][0]['machine_asr'][0]
        self.assertEqual((s['audible_seconds'],s['missing_seconds']),(0.5,0.5))
        self.assertFalse(s['audio_coverage_complete']);self.assertEqual(r['orders_authorized'],0)
    def test_missing_audio_rejected(self):
        del self.files['synthetic.wav'];self.save()
        with self.assertRaises(ValueError):audit_packet(self.path)
    def test_false_complete_rejected(self):
        self.manifest['windows'][0]['asr'][0]['audio_excerpt_truncated']=False;self.save()
        with self.assertRaises(ValueError):audit_packet(self.path)
    def test_bad_hash_rejected(self):
        self.manifest['unique_audio_clips'][0]['sha256']='0'*64;self.save()
        with self.assertRaises(ValueError):audit_packet(self.path)
    def test_wrong_end_rejected(self):
        self.manifest['windows'][0]['audio_end']=13.0;self.save()
        with self.assertRaises(ValueError):audit_packet(self.path)

if __name__=='__main__':unittest.main()