import tempfile,unittest,json,hashlib
from pathlib import Path
from gpu_chat_ocr_candidate import run

class FakeOCR:
    def predict(self,paths):
        return [{'res':{'input_path':p,'rec_texts':['نخر','بخر','دانشجو: چرا؟'],
            'rec_scores':[.8,.75,.91]}} for p in paths]

class RawGpuOcrTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.images=self.root/'src';self.images.mkdir()
        rows=[]
        for i in range(3):
            p=self.images/f'{i}.png';p.write_bytes(b'exact-pixels'+bytes([i]))
            rows.append({'frame_id':f'frame{i}','time_seconds':float(i),'chat':{
                'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}})
        self.index=self.root/'index.json'
        self.index.write_text(json.dumps({'schema':'artin_change_selected_chat_v8',
            'source_video_sha256':'a'*64,'rows':rows}),encoding='utf8')
    def go(self,where='out'):
        return run(self.index,self.images,self.root/where,model_factory=lambda:FakeOCR(),batch_size=2)
    def test_preserve_all_questions_and_negations(self):
        r=self.go();self.assertEqual(r['raw_frames_saved'],3)
        t=json.loads((self.root/'out'/'frame_000002_OCR_RAW.json').read_text())
        self.assertEqual(t['paddle_raw_unmodified']['res']['rec_texts'],['نخر','بخر','دانشجو: چرا؟'])
        self.assertFalse(r['human_qa_accuracy_verified']);self.assertFalse(r['board_and_actions_textualized'])
    def test_never_overwrite(self):
        self.go()
        with self.assertRaises(FileExistsError):self.go()
    def test_detect_modified_input(self):
        (self.images/'1.png').write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError,'SHA'):self.go()
    def test_detect_engine_response_reorder(self):
        class Reverse:
            def predict(self,paths):
                return [{'res':{'input_path':p}} for p in reversed(paths)]
        with self.assertRaisesRegex(ValueError,'ordering'):
            run(self.index,self.images,self.root/'out',model_factory=lambda:Reverse())
        self.assertTrue((self.root/'out'/'INCOMPLETE_OCR_REVIEW_REQUIRED.flag').exists())
    def test_reject_dropped_ocr_frame(self):
        class Drop:
            def predict(self,paths):return [{'res':{}}]
        with self.assertRaisesRegex(ValueError,'count'):
            run(self.index,self.images,self.root/'out',model_factory=lambda:Drop(),batch_size=3)
    def test_unsafe_output_inside_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            run(self.index,self.images,self.images/'out',model_factory=lambda:FakeOCR())

if __name__=='__main__':unittest.main()