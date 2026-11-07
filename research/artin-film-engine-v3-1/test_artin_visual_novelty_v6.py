"""Test priority frame selection without losing source evidence."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from artin_film_pipeline import file_sha256
from artin_visual_novelty_v6 import score_difference,novelty_plan


class NoveltyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rows=[]
        for i,(colour,t) in enumerate([(255,10),(255,40),(0,70),(0,100),(0,410)],1):
            name=f'chat/c{i}.png'
            p=self.root/name
            p.parent.mkdir(exist_ok=True)
            Image.new('RGB',(64,160),(colour,colour,colour)).save(p)
            sha=file_sha256(p)
            self.rows.append({'frame_id':f'f{i}','global_chunk':1,
                'time_seconds':float(t),'chat':{'path':name,'sha256':sha},
                'board':{'path':name,'sha256':sha}})
        self.index={'schema':'artin_classroom_visual_v6',
                    'source_video_sha256':'a'*64,'rows':self.rows}

    def test_scene_change_selected_and_duplicates_retained(self):
        out=novelty_plan(self.root,self.index)
        self.assertEqual(out['selected_frames'],3)
        self.assertEqual(len(out['rows']),5)
        self.assertEqual(out['rows'][0]['selection_reason'],'INITIAL_FRAME')
        self.assertEqual(out['rows'][1]['selection_reason'],'DEFERRED_RETAINED')
        self.assertEqual(out['rows'][2]['selection_reason'],'SCENE_CHANGE')
        self.assertEqual(out['rows'][4]['selection_reason'],'PERIODIC_ANCHOR')
        self.assertTrue(out['nothing_deleted'])

    def test_full_review_keeps_all(self):
        out=novelty_plan(self.root,self.index,full_review=True)
        self.assertEqual(out['selected_frames'],5)

    def test_source_image_tamper_rejected(self):
        (self.root/'chat/c2.png').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):
            novelty_plan(self.root,self.index)

    def test_nonmonotonic_timestamp_rejected(self):
        self.index['rows'][2]['time_seconds']=0.0
        with self.assertRaisesRegex(ValueError,'time order'):
            novelty_plan(self.root,self.index)

    def test_untrusted_path_rejected(self):
        self.index['rows'][0]['chat']['path']='../../unknown.png'
        with self.assertRaisesRegex(ValueError,'Unsafe'):
            novelty_plan(self.root,self.index)

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):novelty_plan(self.root,self.index,threshold=1.2)

    def test_diff_score_exactly_zero_for_matching(self):
        a=Image.new('L',(64,160),200)
        self.assertEqual(score_difference(a,a),0.0)
        self.assertEqual(score_difference(None,a),1.0)


if __name__=='__main__':unittest.main()
