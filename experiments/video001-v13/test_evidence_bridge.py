import copy
import unittest
from evidence_bridge import merge_evidence

SHA='a'*64
BASE=[{'id':'audio1','kind':'audio','sha256':'b'*64,'start':0,'end':30},
      {'id':'chat1','kind':'chat','sha256':'c'*64,'start':30,'end':31}]

def report(tool,ident,sha,a,b,text='candidate'):
    return {'tool':tool,'source_sha256':SHA,'items':[{'id':ident,'original_sha256':sha,
            'start':a,'end':b,'content':text}]}

class BridgeTests(unittest.TestCase):
    def test_originals_remain_untouched_even_with_all_four_tools(self):
        original=copy.deepcopy(BASE)
        out=merge_evidence(SHA,BASE,[report('whisperx','audio1','b'*64,0,30),
                    report('paddleocr','chat1','c'*64,30,31),
                    report('qwen3-vl','chat1','c'*64,30,31),
                    report('videorag','audio1','b'*64,0,30)])
        self.assertEqual(BASE,original)
        self.assertEqual(len(out['evidence']),2)
        self.assertEqual([len(x['supplementary_candidates']) for x in out['evidence']],[2,2])
        self.assertFalse(out['teacher_semantic_accuracy_verified'])
        self.assertFalse(out['trading_allowed'])
    def test_baseline_operates_without_any_optional_tool(self):
        out=merge_evidence(SHA, BASE, [])
        self.assertEqual(len(out['tools_not_run']),4)
        self.assertEqual(out['original_evidence_count'],out['merged_original_evidence_count'])
    def test_reject_wrong_movie(self):
        r=report('whisperx','audio1','b'*64,0,30);r['source_sha256']='f'*64
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[r])
    def test_reject_wrong_sha(self):
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[report('paddleocr','chat1','d'*64,30,31)])
    def test_reject_wrong_tool_kind(self):
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[report('whisperx','chat1','c'*64,30,31)])
    def test_reject_missing_original(self):
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[report('videorag','missing','b'*64,0,1)])
    def test_reject_timing_drift(self):
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[report('whisperx','audio1','b'*64,0,40)])
    def test_reject_semantic_autocertification(self):
        r=report('whisperx','audio1','b'*64,0,30)
        r['items'][0]['verified_teacher_rule']=True
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[r])
    def test_reject_duplicate_reports(self):
        r=report('whisperx','audio1','b'*64,0,30)
        with self.assertRaises(ValueError):merge_evidence(SHA,BASE,[r,r])

if __name__=='__main__': unittest.main()
