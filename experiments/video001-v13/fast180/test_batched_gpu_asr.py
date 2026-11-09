import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from batched_gpu_asr import verify_inputs,transcribe

SHA='a'*64
class FakeModel:
    def transcribe(self,src,**kwargs):
        return iter([NS(start=0.2,end=1.2,text=' بخریم یا نخریم؟ '),NS(start=2,end=4,text='این پاسخ خام است')]),NS(language='fa')
class TestGpuCandidate(unittest.TestCase):
    def setup(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        src=Path(tmp.name)/'src';src.mkdir();self.out=Path(tmp.name)/'result'
        parts=[]
        for n in range(1,3):
            rel=f'part_{n}.wav';(src/rel).write_bytes(f'fake {n}'.encode())
            parts.append({'chunk':n,'audio':rel,'audio_sha256':hashlib.sha256((src/rel).read_bytes()).hexdigest(),
                          'cut_start':(n-1)*300,'cut_end':n*300,'core_start':(n-1)*300,'core_end':n*300})
        (src/'fast_av_manifest.json').write_text(json.dumps({'video_sha256':SHA,'duration_seconds':600,'parts':parts}))
        self.src=src
    def test_preserve_every_raw_segment_and_source_bytes(self):
        self.setup()
        old=[(f.name,f.read_bytes()) for f in self.src.iterdir()]
        originals=verify_inputs(self.src,SHA)
        x=transcribe(originals,self.out,SHA,engine=FakeModel())
        self.assertEqual(x['chunks_processed'],2)
        o=json.loads((self.out/'gpu_00/raw_chunk_001.json').read_text())
        self.assertEqual(o['segments'][0]['text_machine_raw'],' بخریم یا نخریم؟ ')
        self.assertEqual(old,[(f.name,f.read_bytes()) for f in self.src.iterdir()])
    def test_missing_audio_rejected(self):
        self.setup();(self.src/'part_2.wav').unlink()
        with self.assertRaises(ValueError):verify_inputs(self.src,SHA)
    def test_sha_mutation_rejected(self):
        self.setup();(self.src/'part_2.wav').write_bytes(b'change')
        with self.assertRaises(ValueError):verify_inputs(self.src,SHA)
    def test_never_overwrite_existing_raw_output(self):
        self.setup();orig=verify_inputs(self.src,SHA)
        transcribe(orig,self.out,SHA,engine=FakeModel())
        a=self.out/'gpu_00/raw_chunk_001.json';a.write_text('altered elsewhere')
        with self.assertRaises(FileExistsError):transcribe(orig,self.out,SHA,engine=FakeModel())
    def test_one_gpu_shard(self):
        self.setup();orig=verify_inputs(self.src,SHA)
        res=transcribe(orig,self.out,SHA,gpu_index=1,gpu_count=2,engine=FakeModel())
        self.assertEqual(res['chunks_processed'],1)
        self.assertEqual(res['chunks'][0]['chunk'],2)

if __name__=='__main__':unittest.main()