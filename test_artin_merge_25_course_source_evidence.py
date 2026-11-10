import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_merge_25_course_source_evidence import merge_records, citation_coverage, run, parse_zip

class UnificationPureTests(unittest.TestCase):
    @staticmethod
    def row(video,start,end):
        return {'session':video,'start_seconds':start,'end_seconds':end,'record_id':f'original-{video}-{start}',
                'machine_text_unverified':'kept exactly','teacher_meaning_verified':False}

    @staticmethod
    def window(id,video,a,b,segments):
        return {'source_window_id':id,'queue_video':video,'start_seconds':a,'end_seconds':b,
                'source_audio_sha256':'b'*64,'video_sha256':'a'*64,'original_audio_artifact_id':1,
                'original_asr_artifact_id':2,'semantic_rule_verified':False,
                'recovered_machine_asr_segments':[{'asr_id':sid,'start':start,'end':end,'text_unverified':text}
                 for sid,start,end,text in segments]}

    def test_original_kept_and_new_sorted(self):
        original={20:[self.row(20,30,31)],22:[]}
        win=[self.window('A',20,10,20,[('asr_1',12,13,'متن')])]
        merge,seen,_=merge_records(original,win)
        self.assertEqual(len(original[20]),1)
        self.assertEqual(merge[20][1],original[20][0])
        self.assertEqual(len(seen),1)
        self.assertFalse(merge[20][0]['trade_permitted'])

    def test_shared_doji_asr_not_double_counted(self):
        original={20:[],22:[]}
        w=self.window('DOJI_A',20,4210,4215,[('asr_1',4211,4213,'همپوشانی')])
        v=copy.deepcopy(w);v['source_window_id']='DOJI_T'
        combined,seen,ids=merge_records(original,[w,v])
        self.assertEqual(len(combined[20]),1)
        self.assertEqual(len(seen),1)
        self.assertEqual(set(combined[20][0]['source_window_ids']),{'DOJI_A','DOJI_T'})
        self.assertEqual(len(ids),2)

    def test_conflicting_reused_asr_id_rejected(self):
        w=self.window('A',20,1,5,[('same',1,2,'الف')]);v=copy.deepcopy(w)
        v['source_window_id']='B';v['recovered_machine_asr_segments'][0]['text_unverified']='ب'
        with self.assertRaisesRegex(ValueError,'contradictory'):merge_records({20:[],22:[]},[w,v])

    def test_segments_not_within_window_rejected(self):
        w=self.window('A',20,1,5,[('wrong',10,12,'متن')])
        with self.assertRaisesRegex(ValueError,'invalid ASR'):merge_records({20:[],22:[]},[w])

    def test_unsafe_archive_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','bad')
            with self.assertRaisesRegex(ValueError,'unsafe'):parse_zip(p)

    def test_all_13_routes_have_24_original_source_citations(self):
        from artin_merge_25_course_source_evidence import LEGACY_RULE_SOURCES
        self.assertEqual(len(LEGACY_RULE_SOURCES),13)
        self.assertEqual(sum(len(v) for v in LEGACY_RULE_SOURCES.values()),24)


class WithOriginalPrivateArchives(unittest.TestCase):
    def test_real_25_sessions_and_6_citations(self):
        p=Path(__file__).resolve().parent
        original=p/'ARTIN_ALL_10235_PRIVATE_REVIEW_INVENTORY.zip'
        recovered=p/'ARTIN_SIX_RECOVERED_5_AUDIO_CLIPS_PRIVATE_20261110.zip'
        if not original.exists() or not recovered.exists():
            self.skipTest('original privately uploaded ASR archives absent in public CI')
        with tempfile.TemporaryDirectory() as tmp:
            report=run(original,recovered,Path(tmp)/'unified.zip')
            self.assertEqual(report['original_rows'],10235)
            self.assertEqual(report['new_unique_asr_segments'],37)
            self.assertEqual(report['unified_rows'],10272)
            self.assertEqual(report['unified_citations_with_asr'],24)
            self.assertEqual(sum(x['original_speech_rows']==0 for x in report['source_window_review']),6)
            self.assertTrue(all(x['machine_asr_present'] and not x['teacher_semantics_certified'] for x in report['source_window_review']))

if __name__=='__main__':unittest.main()