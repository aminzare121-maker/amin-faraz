"""Fake multimodal model may propose text, never authorize teacher rules."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from artin_film_pipeline import file_sha256
from artin_local_visual_model_v6 import scan_local_visual


class VisualModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rows=[]
        for i in range(2):
            frame={'frame_id':f'part_{i+1:02d}','time_seconds':10+i*30,
                   'global_chunk':1,'batch':1,'slot':1}
            for channel in ('chat','board'):
                fp=self.root/f'{channel}_{i}.png'
                Image.new('RGB',(64,100),(30+i*20,90,30)).save(fp)
                frame[channel]={'path':fp.name,'sha256':file_sha256(fp)}
            self.rows.append(frame)
        self.index={'schema':'artin_classroom_visual_v6','source_video_sha256':'a'*64,
                    'rows':self.rows}

    def test_model_results_are_unverified_and_hashed(self):
        called=[]
        def fake(model,prompt,*,frames,endpoint,system_prompt):
            called.append(frames[0])
            return {'visible_text_candidate':'چرا کندل برگشت؟',
                    'legibility':'MEDIUM'}
        r=scan_local_visual(self.root,self.index,'fake-model',max_frames=2,call_model=fake)
        self.assertEqual(len(called),4)
        self.assertEqual(r['provisional_text_observations'],4)
        self.assertEqual(r['verified_teacher_chart_rules'],0)
        self.assertFalse(r['can_change_artin_engine'])

    def test_priority_reduces_expensive_calls(self):
        called=[]
        def fake(model,prompt,*,frames,endpoint,system_prompt):
            called.append(frames[0])
            return {'visible_text_candidate':'فارکس','legibility':'LOW'}
        r=scan_local_visual(self.root,self.index,'fake-model',max_frames=2,call_model=fake,
                             priority_frame_ids={'part_02'})
        self.assertEqual(len(called),2)
        self.assertEqual(r['frames_requested'],1)

    def test_missing_crop_rejected(self):
        (self.root/'chat_0.png').unlink()
        with self.assertRaisesRegex(ValueError,'missing or unsafe'):
            scan_local_visual(self.root,self.index,'fake',call_model=lambda *a,**k: {})

    def test_no_text_not_pretended_success(self):
        def no_text(*args,**kwargs):
            return {'visible_text_candidate':'','legibility':'LOW'}
        with self.assertRaisesRegex(RuntimeError,'no usable'):
            scan_local_visual(self.root,self.index,'fake',call_model=no_text)

    def test_nonstandard_model_legibility_is_review_not_crash(self):
        def odd(*args,**kwargs):
            return {'visible_text_candidate':'عدد بالاتر از یک؟','legibility':'مبهم'}
        got=scan_local_visual(self.root,self.index,'fake',max_frames=1,
                    channels=('chat',),call_model=odd)
        self.assertEqual(got['provisional_text_observations'],1)
        self.assertEqual(got['candidates'][0]['legibility_candidate'],'UNKNOWN')
        self.assertIn('NONSTANDARD_MODEL_LEGIBILITY_CONVERTED_TO_UNKNOWN',
            [e['status'] for e in got['missing_or_unreadable']])

    def test_chat_only_half_the_expensive_model_calls(self):
        requests=[]
        def fake(*args,**kwargs):
            requests.append(kwargs['frames'][0])
            return {'visible_text_candidate':'آیا این درست است؟','legibility':'MEDIUM'}
        r=scan_local_visual(self.root,self.index,'fake',max_frames=2,
                channels=('chat',),call_model=fake)
        self.assertEqual(len(requests),2)
        self.assertEqual(r['channels'],['chat'])
        self.assertEqual(r['views_attempted'],2)

    def test_unknown_priority_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unknown'):
            scan_local_visual(self.root,self.index,'fake',priority_frame_ids={'unseen'},
                              call_model=lambda *a,**k:{})


if __name__=='__main__':unittest.main()
