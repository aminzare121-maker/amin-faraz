import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_negative_context_packets import build

def sample():
    row={'session':19,'source_segment_id':'s1','start_seconds':10.0,'end_seconds':12.0,
        'machine_text_unverified':'ورود نکنید','source_audio_sha256':'sha','visual_source_nearby':[]}
    case={'session':19,'segment_id':'s1','start_seconds':10.0,'end_seconds':12.0,
        'text_unverified':'ورود نکنید','audio_source_sha256':'sha','assigned_routes':['REVERSAL_STAR']}
    return row,case

class ContextTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'source.zip'
        row,self.case=sample()
        neighbor={**row,'source_segment_id':'near','start_seconds':13.0,'end_seconds':14.0,
            'machine_text_unverified':'بعد از تأیید'}
        with zipfile.ZipFile(self.path,'w') as z:
            z.writestr('session_19_unified_machine_speech_UNVERIFIED.jsonl',
                '\n'.join(json.dumps(x,ensure_ascii=False) for x in (row,neighbor)))
    def tearDown(self):self.temp.cleanup()
    def test_source_verified_context_not_teacher_verified(self):
        r=build(self.path,{'cases':[self.case]})
        self.assertEqual(r['case_count'],1)
        self.assertEqual(len(r['cases'][0]['context']),2)
        self.assertFalse(r['cases'][0]['teacher_meaning_verified'])
        self.assertEqual(r['cases'][0]['action'],'NO_TRADE')
    def test_modified_text_rejected(self):
        case={**self.case,'text_unverified':'ورود کنید'}
        with self.assertRaises(ValueError):build(self.path,{'cases':[case]})
    def test_modified_time_rejected(self):
        case={**self.case,'start_seconds':9.0}
        with self.assertRaises(ValueError):build(self.path,{'cases':[case]})
    def test_missing_source_rejected(self):
        case={**self.case,'segment_id':'forged'}
        with self.assertRaises(ValueError):build(self.path,{'cases':[case]})
    def test_invalid_radius_rejected(self):
        with self.assertRaises(ValueError):build(self.path,{'cases':[self.case]},-1)
if __name__=='__main__':unittest.main()
