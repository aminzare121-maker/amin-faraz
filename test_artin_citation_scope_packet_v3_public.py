"""Public synthetic citation-scope gate tests. No private Artin speech/media."""
import copy
import unittest
from artin_citation_scope_packet_v3 import classify

def fixture():
    return {'windows':[{'id':'SYNTHETIC','route':'TEST','queue_video':22,'start':10.,'end':20.,
      'audio_start':5.,'audio_end':25.,'asr':[
        {'id':'in','start':11.,'end':13.,'text_unverified':'synthetic inside'},
        {'id':'edge','start':19.,'end':23.,'text_unverified':'استاد synthetic question'},
        {'id':'out','start':21.,'end':24.,'text_unverified':'synthetic context'}]}]}
class PublicScopeTest(unittest.TestCase):
    def test_three_scopes(self):
        d=fixture();r=classify(d)
        self.assertEqual(r['totals'],{'fully_inside':1,'crosses_boundary':1,'outside':1})
        self.assertEqual(r['orders_authorized'],0)
        self.assertFalse(r['semantics_verified'])
    def test_question_not_teacher_certified(self):
        d=fixture();classify(d)
        seg=d['windows'][0]['asr'][1]
        self.assertEqual(seg['speaker_review_flag'],'ADDRESSED_TO_TEACHER_POSSIBLE_STUDENT')
        self.assertFalse(seg['teacher_role_independently_verified'])
    def test_precise_clip_intersection(self):
        d=fixture();classify(d)
        s=d['windows'][0]['asr'][1]
        self.assertEqual((s['inside_citation_from'],s['inside_citation_until']),(19.,20.))
    def test_outside_not_usable(self):
        d=fixture();classify(d)
        self.assertIsNone(d['windows'][0]['asr'][2]['inside_citation_until'])
    def test_truncated_audio_rejected(self):
        d=fixture();d['windows'][0]['asr'][1]['end']=26
        with self.assertRaises(ValueError):classify(d)
    def test_reversed_citation_rejected(self):
        d=fixture();d['windows'][0]['end']=9
        with self.assertRaises(ValueError):classify(d)
if __name__=='__main__':unittest.main()
