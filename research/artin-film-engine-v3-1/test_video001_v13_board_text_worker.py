from pathlib import Path
import tempfile,hashlib,json,unittest
from video001_v13_board_text_worker import process

class BoardTextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.board=self.root/'source';(self.board/'board').mkdir(parents=True)
        f=self.board/'board'/'source.png';f.write_bytes(b'FAKE_SCREEN_BYTES')
        s=hashlib.sha256(f.read_bytes()).hexdigest();v='a'*64
        index={'schema':'artin_classroom_visual_v6','source_video_sha256':v,'sample_seconds':30,
        'rows':[{'frame_id':'f01','time_seconds':15,'board':{'path':'board/source.png','sha256':s}}]}
        (self.board/'visual_timeline_v6.json').write_text(json.dumps(index))
    def test_preserves_raw_and_marks_unverified(self):
        x=process(self.board,self.root/'new',workers=1,ocr_fn=lambda path:'فقط متن ماشینی؟')
        self.assertEqual(x['frames_processed'],1)
        raw=json.loads((self.root/'new'/'board_ocr_candidates_PRIVATE.json').read_text())
        self.assertFalse(raw['human_verified']);self.assertFalse(raw['results'][0]['chart_action_semantics_verified'])
        self.assertEqual(raw['results'][0]['machine_text_raw'],'فقط متن ماشینی؟')
        with self.assertRaises(FileExistsError):process(self.board,self.root/'new',workers=1,ocr_fn=lambda path:'')
    def test_reject_modified_source(self):
        (self.board/'board'/'source.png').write_bytes(b'CHANGED')
        with self.assertRaisesRegex(ValueError,'SHA_MISMATCH'):
            process(self.board,self.root/'new',workers=1,ocr_fn=lambda path:'')

if __name__=='__main__':unittest.main()