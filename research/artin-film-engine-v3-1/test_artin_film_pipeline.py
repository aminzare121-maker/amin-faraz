import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import artin_film_pipeline as a


class ArtinFilmPipelineTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)

    def manifest(self):
        chunks = a.chunk_plan(5400)
        for c in chunks:
            c['clip_sha256'] = 'c' * 64
            c['frames'] = []
        m = {'schema': 'artin_video_manifest_v1', 'source_duration': 5400,
             'video_sha256':'v'*64, 'video_path_private': str(self.root/'video.mp4'),
             'chunks':chunks}
        a.atomic_json(self.root/'manifest.json',m)
        return m

    def transcript(self, chunk, segments):
        obj={'schema':'artin_chunk_transcript_v1','chunk':chunk['chunk'],
             'source_clip_sha256':chunk['clip_sha256'], 'asr':'SYNTHETIC_FIXTURE',
             'segments':segments}
        a.atomic_json(self.root/chunk['transcript'],obj)

    def segment(self,c,n,start,end,text):
        return {'id':f'c{c:02}_u{n:04}', 'start':start,'end':end,
                'text':text,'speaker':'UNKNOWN','speaker_verified':False}

    def save_events(self,chunk,events):
        a.atomic_json(self.root/chunk['analysis'],{
            'schema':'artin_chunk_analysis_v1','chunk':chunk['chunk'],
            'events': events,'interpretation_verified':False})

    def validated_event(self,part,source,kind,quote,rule='',decision='UNKNOWN'):
        e,_=a.validate_model_events({'events':[{
            'kind':kind, 'exact_quote':quote, 'source_ids':[source['id']],
            'rule_label':rule, 'decision':decision, 'conditions':[]}]},
            [source],part)
        self.assertEqual(len(e),1)
        return e[0]

    def test_exactly_eighteen_chunks_with_overlap_and_core_no_gaps(self):
        plan=a.chunk_plan(5400)
        self.assertEqual(len(plan),18)
        self.assertEqual(plan[0]['cut_start'],0)
        self.assertEqual(plan[-1]['cut_end'],5400)
        for i, c in enumerate(plan):
            self.assertEqual(c['core_start'],i*300)
            self.assertEqual(c['core_end'],(i+1)*300)
            if i:
                self.assertEqual(c['cut_start'],i*300-12)
            if i<17:
                self.assertEqual(c['cut_end'],(i+1)*300+12)

    def test_parallel_results_out_of_order_are_reordered_by_part_number(self):
        expected=a.chunk_plan(5400)
        shuffled=[dict(x) for x in expected[::-1]]
        actual=a.canonical_chunk_order(shuffled,expected)
        self.assertEqual([x['chunk'] for x in actual],list(range(1,19)))
        self.assertEqual(actual[0]['clip'],'clips/part_01.mp4')
        self.assertEqual(actual[-1]['clip'],'clips/part_18.mp4')

    def test_parallel_missing_chunk_cannot_produce_complete_manifest(self):
        p=a.chunk_plan(5400)
        with self.assertRaisesRegex(ValueError,'Missing five-minute chunk'):
            a.canonical_chunk_order(p[:8]+p[9:],p)

    def test_parallel_duplicate_number_fails_even_if_count_is_eighteen(self):
        p=a.chunk_plan(5400)
        wrong=p[:8]+[dict(p[7])]+p[9:]
        with self.assertRaisesRegex(ValueError,'Duplicate five-minute chunk'):
            a.canonical_chunk_order(wrong,p)

    def test_swapped_five_minute_file_mapping_detected(self):
        p=a.chunk_plan(5400)
        wrong=[dict(x) for x in p]
        wrong[0]['clip'],wrong[1]['clip']=wrong[1]['clip'],wrong[0]['clip']
        with self.assertRaisesRegex(ValueError,'wrong numbered file'):
            a.canonical_chunk_order(wrong,p)

    def test_wrong_part_source_time_detected(self):
        p=a.chunk_plan(5400)
        wrong=[dict(x) for x in p]
        wrong[12]['core_start']=wrong[12]['core_start']+300
        with self.assertRaisesRegex(ValueError,'wrong source-time interval'):
            a.canonical_chunk_order(wrong,p)

    def test_manifest_with_scrambled_numbering_is_rejected(self):
        m=self.manifest()
        m['chunks'][2],m['chunks'][3]=m['chunks'][3],m['chunks'][2]
        a.atomic_json(self.root/'manifest.json',m)
        with self.assertRaisesRegex(ValueError,'scrambled'):
            a.load_manifest(self.root)

    def test_media_container_padding_does_not_create_nineteenth_very_short_part(self):
        p=a.chunk_plan(5400.08)
        self.assertEqual(len(p),18)
        self.assertEqual(p[-1]['core_end'],5400.08)
        self.assertEqual(p[0]['core_start'],0)
        self.assertEqual(p[-1]['chunk'],18)

    def test_non_multiple_duration_has_short_final_core(self):
        p=a.chunk_plan(601)
        self.assertEqual(len(p),3)
        self.assertEqual(p[-1]['core_end'],601)

    def test_no_blind_speaker_verification_in_asr(self):
        m=self.manifest()
        s=self.segment(1,0,15,17,'آیا باید خرید کنیم؟')
        s['speaker_verified']=True
        with self.assertRaisesRegex(ValueError,'verified speakers'):
            a.validate_transcript(m['chunks'][0],{
                'schema':'artin_chunk_transcript_v1','chunk':1,
                'source_clip_sha256':'c'*64,'segments':[s]})

    def test_clip_sha_mismatch_rejected(self):
        m=self.manifest()
        with self.assertRaisesRegex(ValueError,'SHA256'):
            a.validate_transcript(m['chunks'][0],{'schema':'artin_chunk_transcript_v1',
                'chunk':1,'source_clip_sha256':'0'*64,'segments':[]})

    def test_overlap_repeated_utterance_dedup_does_not_duplicate_question(self):
        ss=[self.segment(1,1,299,301,'آیا اینجا خرید می‌گیریم؟'),
            self.segment(2,1,299.1,301.1,'آیا اینجا خرید می‌گیریم؟')]
        unique,alias=a.deduplicate_segments(ss)
        self.assertEqual(len(unique),1)
        self.assertEqual(alias['c02_u0001'],'c01_u0001')

    def test_repeated_identical_speech_far_apart_is_not_deleted(self):
        ss=[self.segment(1,1,20,22,'بله'),self.segment(1,2,220,223,'بله')]
        unique,_=a.deduplicate_segments(ss)
        self.assertEqual(len(unique),2)

    def test_reject_model_hallucinated_quote(self):
        p=a.chunk_plan(5400)[0]
        s=self.segment(1,0,18,22,'این قسمت فقط مثال آزمایشی است.')
        yes,no=a.validate_model_events({'events':[{
            'kind':'RULE','source_ids':[s['id']], 'exact_quote':'قانون خرید در ۴۰۰۰',
            'rule_label':'x'}]},[s],p)
        self.assertEqual(yes,[])
        self.assertEqual(no[0]['reason'],'QUOTE_NOT_FOUND_IN_SOURCE')

    def test_cross_chunk_context_has_no_duplicate_rule_ownership(self):
        parts=a.chunk_plan(5400)
        s=self.segment(1,0,298,299,'روش بیست: در اینجا صبر کن')
        good,rejected=a.validate_model_events({'events':[{'kind':'RULE','source_ids':[s['id']],
            'exact_quote':s['text'],'rule_label':'روش بیست'}]},[s],parts[1])
        self.assertEqual(good,[])
        self.assertEqual(rejected[0]['reason'],'CROSS_CHUNK_CONTEXT_NOT_OWNED')

    def test_question_cross_chunk_merged_but_not_teacher_verified(self):
        m=self.manifest()
        for c in m['chunks']:
            self.transcript(c,[])
            self.save_events(c,[])
        q=self.segment(1,1,299,299.9,'این کندل را چرا معامله نکنیم؟')
        ans=self.segment(2,1,302,306,'طبق شرطی که گفتیم هنوز تأیید نشده')
        old=self.segment(2,2,320,327,'قانون اول: بعد از بسته شدن کندل خرید')
        correction=self.segment(18,1,5300,5310,'نه قانون اول را اصلاح می‌کنم، باید منتظر تأیید ماند')
        self.transcript(m['chunks'][0],[q])
        self.transcript(m['chunks'][1],[ans,old])
        self.transcript(m['chunks'][17],[correction])
        self.save_events(m['chunks'][0],[self.validated_event(m['chunks'][0],q,'QUESTION',q['text'])])
        self.save_events(m['chunks'][1],[self.validated_event(m['chunks'][1],ans,'ANSWER',ans['text']),
                                         self.validated_event(m['chunks'][1],old,'RULE',old['text'],'قانون اول','BUY')])
        self.save_events(m['chunks'][17],[self.validated_event(m['chunks'][17],correction,
                                        'CORRECTION',correction['text'],'قانون اول','NO_TRADE')])
        report=a.merge(self.root)
        self.assertEqual(report['chunk_count'],18)
        self.assertEqual(report['transcript_utterances'],4)
        self.assertEqual(report['possible_question_answer_links'],1)
        self.assertEqual(report['possible_later_corrections'],1)
        self.assertEqual(report['candidate_rule_groups'],1)
        self.assertEqual(report['teacher_rules_approved'],0)
        self.assertFalse(report['artin_rule_ready'])
        graph=json.loads((self.root/'rule_candidate_graph.json').read_text())
        self.assertTrue(graph['candidate_dialogue_links'][0]['cross_chunk'])
        self.assertEqual(graph['candidate_correction_links'][0]['type'],'POSSIBLE_CORRECTION_OF')
        self.assertFalse(graph['may_modify_engine'])
        self.assertTrue((self.root/'unified_subtitles.vtt').read_text().startswith('WEBVTT'))

    def test_missing_semantic_analysis_fails_closed_not_zero_success(self):
        m=self.manifest()
        for c in m['chunks']:
            self.transcript(c,[])
        with self.assertRaisesRegex(RuntimeError,'Incomplete lesson'):
            a.merge(self.root)
        report=json.loads((self.root/'audit_report.json').read_text())
        self.assertEqual(len(report['issues']),18)
        self.assertFalse(report['transcript_and_semantic_outputs_present'])

    def test_partial_merge_has_uncertainty_report(self):
        self.manifest()
        r=a.merge(self.root,require_all=False)
        self.assertEqual(len(r['issues']),36)
        self.assertFalse(r['audio_video_independently_verified'])
        self.assertEqual(r['teacher_rules_approved'],0)

    def test_llm_is_local_only(self):
        with self.assertRaisesRegex(ValueError,'LOCAL Ollama'):
            a.ollama_json('model','hi',endpoint='https://example.org')

    def test_global_crosschunk_link_reviewer_is_only_a_hypothesis(self):
        from unittest.mock import patch
        m=self.manifest()
        # This supplied event pair is an invented mock of a correction two chapters later.
        fake=[{'id':'e_early','kind':'RULE','start':30,'end':31,'chunk':1,
               'quote':'قانون ساختگی اول','rule_label_candidate':'قاعده فرضی',
               'decision_candidate':'BUY'},
              {'id':'e_late','kind':'CORRECTION','start':4800,'end':4810,'chunk':17,
               'quote':'اصلاح ساختگی','rule_label_candidate':'قاعده فرضی',
               'decision_candidate':'NO_TRADE'}]
        a.atomic_json(self.root/'unified_timeline.json',{
           'schema':'artin_linked_timeline_v1', 'semantic_candidates':fake})
        a.atomic_json(self.root/'rule_candidate_graph.json',{'candidate_rules':[]})
        response={'edges':[{'from':'e_late','to':'e_early','type':'POSSIBLE_CORRECTION_OF',
                            'reason':'experimental candidate'},
                           {'from':'e_early','to':'e_late','type':'POSSIBLE_CORRECTION_OF',
                            'reason':'invalid future-to-past'},
                           {'from':'e_fake','to':'e_early','type':'POSSIBLE_QA'}]}
        with patch.object(a,'ollama_json',return_value=response):
            report=a.reconcile_global(self.root,model='synthetic-mock-model')
        self.assertEqual(report['edges'],1)
        self.assertEqual(report['rejected'],2)
        graph=json.loads((self.root/'global_connection_suggestions.json').read_text())
        self.assertFalse(graph['candidate_edges'][0]['teacher_verified'])
        self.assertFalse(graph['candidate_edges'][0]['may_change_engine'])
        self.assertFalse(graph['whole_video_really_watched'])

    def test_blank_normalized_quote_rejected(self):
        part=a.chunk_plan(5400)[0]
        u=self.segment(1,1,15,17,'صحبت')
        good,bad=a.validate_model_events({'events':[{'kind':'RULE','source_ids':[u['id']],
            'exact_quote':'...', 'rule_label':'تست'}]},[u],part)
        self.assertEqual(good,[])
        self.assertEqual(bad[0]['reason'],'QUOTE_NOT_FOUND_IN_SOURCE')

    def test_chapter_metadata_spans_original_exactly(self):
        self.manifest()
        metadata=a.chapters_for_ffmpeg(self.root).read_text()
        self.assertEqual(metadata.count('[CHAPTER]'),18)
        self.assertIn('END=5400000',metadata)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg tools unavailable')
    def test_real_ffmpeg_prepare_and_remux_small_synthetic_video(self):
        # Test the actual executable pipeline with synthetic picture+sound only.
        video=self.root/'source_test.mp4'
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
             '-f','lavfi','-i','color=c=black:s=80x64:r=1:d=12',
             '-f','lavfi','-i','anullsrc=r=16000:cl=mono', '-t','12',
             '-c:v','libx264','-preset','ultrafast','-c:a','aac',str(video)]
        subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out=self.root/'project'
        m=a.prepare(video,out,workers=2,frames_per_chunk=1,chunk_s=5)
        self.assertEqual(len(m['chunks']),3)
        self.assertEqual(m['chunk_numbers_in_order'],[1,2,3])
        self.assertTrue(m['strict_chunk_order'])
        a.check_saved_clips(out,m)
        index=json.loads((out/'chunk_order_verified.json').read_text(encoding='utf8'))
        self.assertEqual(index['chunk_numbers_in_source_order'],[1,2,3])
        self.assertTrue(index['no_missing_or_duplicate_numbers'])
        self.assertFalse((out/'chunk_plan_pending.json').exists())
        self.assertEqual(len(list((out/'frames').glob('*.jpg'))),3)
        merged=a.remux_chapters(out,self.root/'chaptered.mp4')
        self.assertEqual(merged['chapters'],3)
        self.assertTrue((self.root/'chaptered.mp4').exists())
        self.assertEqual(merged['teacher_rules_verified'],0)
        # Changing an extracted chunk must invalidate any later semantic merge.
        with (out/'clips'/'part_02.mp4').open('ab') as fh:
            fh.write(b'FAKE_AFTER_EXTRACTION')
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            a.check_saved_clips(out,a.load_manifest(out))
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            a.merge(out,require_all=False)

if __name__=='__main__':
    unittest.main(verbosity=2)
