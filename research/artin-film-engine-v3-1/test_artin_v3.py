"""Grounded tests: real FFmpeg imagery; model answers are mocked (NOT verified)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from artin_film_pipeline import validate_model_events,chunk_plan
from artin_vision_scan import (extract_sampled_frames,validate_vision_response,scan_vision)
from artin_course_compiler import compile_course
from artin_model_preflight import check,_valid_local_endpoint

class V3Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg unavailable')
    def test_real_video_frame_extraction_and_hashes(self):
        video=self.root/'fake.mkv'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc=size=256x144:rate=2',
            '-t','3','-c:v','mpeg4',str(video)],check=True)
        frames=extract_sampled_frames(video,self.root,
            {'core_start':0,'core_end':3,'chunk':1},step_seconds=1)
        self.assertGreaterEqual(len(frames),2)
        self.assertTrue(all((self.root/f['path']).read_bytes().startswith(b'\xff\xd8') for f in frames))
        self.assertTrue(all(len(f['sha256'])==64 for f in frames))
        self.assertTrue(all(f['time_is_exact_video_pts'] is False for f in frames))

    def test_vision_can_only_reference_known_sampled_frame(self):
        frames=[{'frame_id':'f01_0000','sha256':'f'*64,'time_approx_seconds':20}]
        ok,bad=validate_vision_response({'observations':[{'frame_id':'f01_0000',
            'scene_type':'CHART','related_to_trading_candidate':True,
            'visual_description_candidate':'fake chart','visible_text_candidate':''}]},frames)
        self.assertEqual(len(ok),1)
        self.assertFalse(ok[0]['teacher_rule_verified'])
        self.assertFalse(ok[0]['can_change_artin_engine'])
        ok,bad=validate_vision_response({'observations':[{'frame_id':'invented',
            'scene_type':'CHART','related_to_trading_candidate':True}]},frames)
        self.assertEqual(ok,[])
        self.assertIn('UNKNOWN_OR_DUPLICATE_FRAME_ID',str(bad))

    def test_vision_response_empty_is_not_complete(self):
        frames=[{'frame_id':'f01_0000','sha256':'f'*64,'time_approx_seconds':20}]
        ok,bad=validate_vision_response({'observations':[]},frames)
        self.assertEqual(ok,[])
        self.assertIn('FRAME_NOT_DESCRIBED',str(bad))

    def test_llm_event_rejects_fabricated_visual_reference(self):
        source=[{'id':'u1','text':'از این نقطه وارد می شویم','start':12,'end':15}]
        chunk={'chunk':1,'core_start':0,'core_end':300}
        event=dict(kind='RULE',source_ids=['u1'],exact_quote=source[0]['text'],
                   decision='UNKNOWN',related_visual_frame_ids=['imaginary'])
        events,rejected=validate_model_events({'events':[event]},source,chunk,visual_evidence={})
        self.assertEqual(events,[])
        self.assertEqual(rejected[0]['reason'],'UNKNOWN_OR_UNVERIFIED_VISUAL_FRAME_REFERENCE')

    def test_llm_event_accepts_visual_pointer_but_not_teacher_certainty(self):
        source=[{'id':'u1','text':'کندل تایید بسته شد','start':15,'end':18}]
        chunk={'chunk':1,'core_start':0,'core_end':300}
        event=dict(kind='RULE',source_ids=['u1'],exact_quote=source[0]['text'],
                   decision='BUY',rule_label='fake-rule',conditions=['unknown condition'],
                   related_visual_frame_ids=['f01_0000'])
        vision={'f01_0000':{'frame_id':'f01_0000','frame_sha256':'b'*64,
                            'time_approx_seconds':16}}
        events,bad=validate_model_events({'events':[event]},source,chunk,
                                          visual_evidence=vision)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['related_visual_frame_evidence'][0]['frame_sha256'],'b'*64)
        self.assertFalse(events[0]['can_trade'])
        self.assertFalse(events[0]['frame_evidence_not_verified'] is False)

    def test_preflight_rejects_external_destination(self):
        with self.assertRaises(ValueError):
            _valid_local_endpoint('https://remote.example.com:11434')
        with self.assertRaises(ValueError):
            _valid_local_endpoint('http://127.0.0.1:11434?redirect=external')

    def test_preflight_reports_actual_blockers(self):
        r=check(str(self.root/'model-not-there'),'not_installed_model',endpoint='http://127.0.0.1:1')
        self.assertFalse(r['checks']['can_attempt_full_local_analysis'])
        self.assertEqual(r['teacher_rules_verified'],0)

    def test_missing_lessons_must_not_be_marked_complete(self):
        result=compile_course({'lessons':[]},26)
        self.assertEqual(result['supplied_lessons'],0)
        self.assertEqual(len(result['missing_sessions']),26)
        self.assertEqual(result['rules_approved'],0)

    def test_reject_duplicated_lesson_identifiers(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            compile_course({'lessons':[{'session':1,'folder':'none'},
                 {'session':1,'folder':'none'}]},26)

    def test_reject_nonexistent_lesson_artefact(self):
        with self.assertRaisesRegex(ValueError,'missing'):
            compile_course({'lessons':[{'session':21,'folder':str(self.root)}]},26)

    def _lesson_fixture(self,session,sha,kind,decision,quote,include_noise=False):
        from artin_film_pipeline import atomic_json
        d=self.root/f'lesson_{session}'
        d.mkdir()
        atomic_json(d/'manifest.json',{'schema':'artin_video_manifest_v1',
            'video_sha256':sha,'source_duration':300,'chunks':[{'chunk':1}]})
        atomic_json(d/'audit_report.json',{'schema':'artin_full_lesson_diagnostic_v1',
            'video_sha256':sha,'chunk_count':1,'teacher_rules_approved':0,
            'artin_rule_ready':False,'transcript_and_semantic_outputs_present':True})
        texts=[quote]
        if include_noise: texts.append('اینترنت قطع شده و صدا نمیاد')
        segments=[{'id':f'u{i}','start':10+i*20,'end':12+i*20,'text':t}
                  for i,t in enumerate(texts)]
        events=[]
        for i,seg in enumerate(segments):
            events.append({'id':f'e{i}','kind':kind if i==0 else 'RULE',
                 'source_ids':[seg['id']],'quote':seg['text'],
                 'start':seg['start'],'end':seg['end'],'chunk':1,
                 'rule_label_candidate':'قانون ساختگی مشترک','decision_candidate':decision,
                 'condition_candidates':[],
                 'status':'UNVERIFIED_MODEL_INTERPRETATION_REQUIRES_AUDIO_VIDEO_REVIEW',
                 'can_trade':False})
        atomic_json(d/'unified_timeline.json',{'schema':'artin_linked_timeline_v1',
            'source_video_sha256':sha,'segments':segments,'semantic_candidates':events})
        atomic_json(d/'rule_candidate_graph.json',{'schema':'artin_rule_candidate_graph_v1',
            'candidate_rules':[],'may_modify_engine':False})
        atomic_json(d/'artin_engine_handoff.json',{'source_video_sha256':sha,
            'trade_permissions':0,'approved_rules':0})
        atomic_json(d/'noise_quarantine.json',{'schema':'artin_classroom_noise_review_v1',
            'quarantined_events':[]})
        return {'session':session,'folder':str(d)}

    def test_course_correction_across_lessons_and_noise_quarantine(self):
        a=self._lesson_fixture(21,'1'*64,'RULE','BUY','وقتی بدنه بسته شد وارد می شویم')
        b=self._lesson_fixture(22,'2'*64,'CORRECTION','NO_TRADE',
                               'نه این بار نباید معامله کنیم',include_noise=True)
        course=compile_course({'lessons':[a,b]},26)
        self.assertEqual(course['supplied_lessons'],2)
        self.assertEqual(course['candidate_topics'],1)
        self.assertEqual(len(course['cross_session_revision_review_edges']),1)
        self.assertEqual(len(course['candidate_decision_conflicts']),1)
        self.assertGreaterEqual(len(course['quarantined_noninstructional_or_mixed_events']),1)
        self.assertFalse(course['topics'][0]['can_compile_to_executable_artin_rule'])
        self.assertEqual(course['rules_approved'],0)

    def test_course_rejects_duplicate_video_under_new_lesson_number(self):
        a=self._lesson_fixture(21,'3'*64,'RULE','BUY','قانون اول')
        b=self._lesson_fixture(22,'3'*64,'RULE','BUY','قانون دوم')
        with self.assertRaisesRegex(ValueError,'Same source video'):
            compile_course({'lessons':[a,b]},26)

    def test_course_rejects_manufactured_teacher_permission(self):
        a=self._lesson_fixture(21,'4'*64,'RULE','BUY','قانون آموزشی')
        path=Path(a['folder'])/'artin_engine_handoff.json'
        payload=json.loads(path.read_text());payload['trade_permissions']=1
        path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError,'untrusted or executable'):
            compile_course({'lessons':[a]},26)

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg unavailable')
    def test_local_video_scanner_integrates_mocked_visual_model(self):
        from artin_film_pipeline import atomic_json,file_sha256
        video=self.root/'fake.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc=size=256x144:rate=2',
            '-t','4','-c:v','mpeg4',str(video)],check=True)
        part={'chunk':1,'core_start':0,'core_end':4}
        atomic_json(self.root/'manifest.json',{'schema':'artin_video_manifest_v1',
            'video_sha256':file_sha256(video),'video_path_private':str(video),'chunks':[part]})
        def fake_model(_model,prompt,**kwargs):
            req=json.loads(prompt)
            return {'observations':[{'frame_id':f['frame_id'],'scene_type':'UNKNOWN',
                'related_to_trading_candidate':False,'visual_description_candidate':'mock'}
                for f in req['frames']]}
        with patch('artin_vision_scan.ollama_json',side_effect=fake_model):
            docs=scan_vision(self.root,'SIMULATED_VISION_ONLY',step_seconds=1,workers=1)
        self.assertEqual(len(docs),1)
        self.assertGreaterEqual(len(docs[0]['frames']),3)
        self.assertFalse(docs[0]['full_video_visual_content_verified'])
        self.assertTrue((self.root/'visual_scan_summary.json').is_file())

    def test_reported_overlap_duration_at_boundaries(self):
        chunks=chunk_plan(90*60,300,12)
        self.assertEqual(len(chunks),18)
        self.assertEqual((chunks[1]['cut_start'],chunks[1]['cut_end']),(288,612))

if __name__=='__main__':unittest.main()
