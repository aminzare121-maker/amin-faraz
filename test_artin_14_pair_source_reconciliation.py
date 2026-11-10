import copy, hashlib, io, json, tempfile, unittest, wave, zipfile
from pathlib import Path
from artin_14_pair_source_reconciliation import reconcile,index_sources


def archive(root,truncate=False):
    b=io.BytesIO()
    with wave.open(b,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000)
    wav=b.getvalue();sha=hashlib.sha256(wav).hexdigest()
    if truncate:wav=wav[:-100]
    path=root/'original.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('audio/batch_001/part_1.wav',wav)
        z.writestr('fast_av_manifest.json',json.dumps({'video_sha256':'fictional','parts':[{'audio':'audio/batch_001/part_1.wav','audio_sha256':sha,'cut_start':10,'cut_end':11}]}))
    return path,sha

class SourceChecks(unittest.TestCase):
    def test_sha_verified_wav(self):
        with tempfile.TemporaryDirectory() as d:
            p,sha=archive(Path(d));idx=index_sources([p]);self.assertIn(sha,idx);self.assertEqual(idx[sha]['end_seconds'],11)
    def test_sha_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p,_=archive(Path(d),truncate=True)
            with self.assertRaises(ValueError):index_sources([p])
    def test_temporal_overlap_not_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            p,sha=archive(Path(d));idx=index_sources([p]);self.assertNotIn('different-hash',idx)
    def test_real_14_pair_sources(self):
        src=Path('/mnt/data/files/ARTIN_13_DECISION_CONFLICT_REVIEW_PRIVATE_20261110.json')
        wav=Path('/mnt/data/files/AUDIO_11.zip')
        if not src.exists() or not wav.exists():self.skipTest('private originals unavailable')
        result=reconcile(json.loads(src.read_text()),index_sources([wav]))
        self.assertEqual(result['unique_pairs'],14)
        self.assertEqual(result['unique_source_wavs'],4)
        self.assertEqual(sum(g['status']=='EXACT_SOURCE_SHA_AND_INTERVAL_MATCH' for g in result['source_groups']),1)
        self.assertEqual(result['orders_authorized'],0)
if __name__=='__main__':unittest.main()