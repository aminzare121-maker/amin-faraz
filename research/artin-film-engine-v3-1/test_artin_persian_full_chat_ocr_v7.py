"""Simulate full-video Persian chat OCR with known original image hashes."""
import copy
import tempfile
import unittest
from pathlib import Path
from artin_persian_full_chat_ocr_v7 import ocr_frames
from artin_persian_chat_ocr_trial_v7 import sha


class MockOCR:
    def __init__(self):self.i=0
    def predict(self,path):
        self.i+=1
        if self.i==2:
            return [{'rec_texts':[],'rec_scores':[],'rec_boxes':[]}]
        if self.i==3:
            raise RuntimeError('Simulated OCR failure')
        return [{'rec_texts':['هست؟','یعنی این عدد بالاتر از یک'],
                 'rec_scores':[.95,.9],
                 'rec_boxes':[[350,100,460,145],[50,10,470,55]]}]


class ChatOCRFullTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.rows=[]
        for i in range(3):
            f=self.root/f'chat_{i}.png'
            f.write_bytes(f'fake_source_{i}'.encode())
            self.rows.append({'frame_id':f'vid_{i}','time_seconds':15+i*30,
                'global_chunk':1,'batch':1,'slot':1,
                'chat':{'path':f.name,'sha256':sha(f)}})
        self.idx={'schema':'artin_classroom_visual_v6',
                  'source_video_sha256':'a'*64,'rows':self.rows}

    def test_unreadable_and_failed_are_not_claimed_verified(self):
        mock=MockOCR()
        summary=ocr_frames(self.root,self.idx,self.root/'output',ocr_factory=lambda **kw:mock,
                           checkpoint_every=1)
        self.assertEqual(summary['frames_attempted'],3)
        self.assertEqual(summary['frames_with_some_ocr_text'],1)
        self.assertEqual(summary['frames_without_detected_text'],1)
        self.assertEqual(summary['ocr_failed_frames'],1)
        self.assertEqual(summary['human_verified_typed_messages'],0)
        self.assertEqual(summary['valid_teacher_question_answer_pairs'],0)
        self.assertEqual(summary['verified_teacher_rules'],0)
        self.assertEqual(summary['frames_with_question_mark_candidates'],1)

    def test_restart_after_partial_checkpoint_does_not_reocr_finished_frames(self):
        import json
        class GoodOCR:
            def __init__(self):self.calls=0
            def predict(self,path):
                self.calls+=1
                return [{'rec_texts':['این چه زمانی شروع میشه؟'],
                         'rec_scores':[.96],
                         'rec_boxes':[[1,2,160,40]]}]
        output=self.root/'resumable'
        first=GoodOCR()
        ocr_frames(self.root,self.idx,output,ocr_factory=lambda **k:first,checkpoint_every=1)
        self.assertEqual(first.calls,3)
        p=output/'full_chat_ocr_candidates_PRIVATE.json'
        saved=json.loads(p.read_text(encoding='utf8'))
        saved['results']=saved['results'][:2]
        saved['frames_attempted']=2
        saved['complete']=False
        p.write_text(json.dumps(saved),encoding='utf8')
        second=GoodOCR()
        result=ocr_frames(self.root,self.idx,output,ocr_factory=lambda **k:second,checkpoint_every=1)
        self.assertEqual(second.calls,1)
        self.assertEqual(result['frames_attempted'],3)
        self.assertEqual(result['ocr_failed_frames'],0)

    def test_swapped_checkpoint_source_image_hash_rejected_before_model(self):
        import json
        class GoodOCR:
            def predict(self,path):
                return [{'rec_texts':[],'rec_scores':[],'rec_boxes':None}]
        output=self.root/'bad-checkpoint'
        ocr_frames(self.root,self.idx,output,ocr_factory=lambda **k:GoodOCR())
        p=output/'full_chat_ocr_candidates_PRIVATE.json'
        saved=json.loads(p.read_text(encoding='utf8'))
        saved['results'][0]['source_frame_sha256']='f'*64
        p.write_text(json.dumps(saved),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'checkpoint original image'):
            ocr_frames(self.root,self.idx,output,
                ocr_factory=lambda **k:(_ for _ in ()).throw(AssertionError('bad')))

    def test_blank_real_chat_with_none_geometry_is_blank_not_model_failure(self):
        class NoPrintedChatOCR:
            def predict(self,path):
                return [{'rec_texts':[],'rec_scores':[],'rec_boxes':None}]
        summary=ocr_frames(self.root,self.idx,self.root/'blank-output',
                 ocr_factory=lambda **kwargs:NoPrintedChatOCR())
        self.assertEqual(summary['frames_attempted'],3)
        self.assertEqual(summary['frames_without_detected_text'],3)
        self.assertEqual(summary['ocr_failed_frames'],0)
        self.assertEqual(summary['frames_with_some_ocr_text'],0)
        self.assertIsNone(summary['population_OCR_accuracy'])

    def test_missing_or_tampered_image_rejected_before_model(self):
        self.rows[0]['chat']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'changed chat'):
            ocr_frames(self.root,self.idx,self.root/'x',ocr_factory=lambda **kw:MockOCR())

    def test_source_limit_keeps_not_all_covered(self):
        summary=ocr_frames(self.root,self.idx,self.root/'x',
               ocr_factory=lambda **kw:MockOCR(),max_frames=1)
        self.assertEqual(summary['source_frames_total'],3)
        self.assertEqual(summary['frames_attempted'],1)
        self.assertIsNone(summary['population_OCR_accuracy'])
        self.assertTrue(summary['sampled_frames_are_not_every_video_frame'])

    def test_invalid_input_index_rejected(self):
        with self.assertRaisesRegex(ValueError,'Original video'):
            ocr_frames(self.root,{},self.root/'x',ocr_factory=lambda **kw:MockOCR())


if __name__=='__main__':unittest.main()
