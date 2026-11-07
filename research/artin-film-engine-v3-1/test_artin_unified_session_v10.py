"""End-to-end contract tests for actual SOURCE -> ASR -> OCR -> Q&A -> audit.

No mock is used by the real GitHub workflow, only these quick regressions.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import artin_unified_session_v10 as mod


class UnifiedPipelineContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.video=self.root/"original.mp4"
        self.video.write_bytes(b"source-preserving-fixture-video"*60)
        self.digest=hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.out=self.root/"private"
        self.flags=[]

    def stub_pipeline(self, *, fail_ocr=False, fail_asr=False, false_teacher_answer=False):
        p={"chunk":1,"audio":"audio_part.wav","cut_start":0,"cut_end":60,
           "audio_sha256":"b"*64}
        manifest={"video_sha256":self.digest,"duration_seconds":60.0,"parts":[p]}
        visual={"schema":"artin_classroom_visual_v6",
                "source_video_sha256":self.digest,"rows":[{"frame_id":"1"}]}
        def preparation(*args,**kwargs):
            self.flags.append("prepare")
            return manifest
        def valid(*args,**kwargs):
            self.flags.append("validate")
            return True
        def asr_factory(*args,**kwargs):
            self.flags.append("asr_model")
            class FakeWhisper:
                def transcribe(self,arr,**kwargs):
                    self_used=True
                    return iter([SimpleNamespace(start=1.0,end=7.0,text="اگر قیمت شکست بخوریم؟",
                         avg_logprob=-.4,no_speech_prob=.05)]),None
            return FakeWhisper()
        def audio(*args,**kwargs):
            self.flags.append("read_audio")
            return b"audio"
        def review(man,docs):
            self.flags.append("review_audio")
            return {"schema":"artin_teacher_av_review_v5",
                 "source_video_sha256":self.digest,"parts_with_asr":0 if fail_asr else 1,
                 "parts_missing_asr":[1] if fail_asr else [],
                 "speech_lines":[{"id":docs[0]["segments"][0]["id"],
                    "text":docs[0]["segments"][0]["text"]}]} 
        def img(*args,**kwargs):
            self.flags.append("image")
            return visual
        def ocr(root,index,out,**kwargs):
            self.flags.append("ocr")
            Path(out).mkdir(parents=True,exist_ok=True)
            (Path(out)/"full_chat_ocr_candidates_PRIVATE.json").write_text(
                 json.dumps({"complete":True}),encoding="utf8")
            return {"ocr_failed_frames":1 if fail_ocr else 0,
                    "frames_attempted":1,"frames_with_some_ocr_text":1}
        def join(*args,**kwargs):
            self.flags.append("join")
            return {"verified_teacher_answers":1 if false_teacher_answer else 0,
                    "provisional_distinct_question_groups":1}, {
                "schema":"artin_private_typed_chat_audio_candidates_v8",
                "source_video_sha256":self.digest,
                "question_groups":[{
                    "candidate_text":"آیا برای ورود باید صبر کنیم؟",
                    "first_seen":12.0,"last_seen":12.0,
                    "frame_sources":[{"frame_id":"1","chat_frame_sha256":"a"*64,
                                      "observed_at_seconds":12.0}],
                    "teacher_answer_verified":False,"student_question_verified":False,
                    "provisional_nearby_speech":[]}],
                "all_teacher_answers_unverified":True}
        def fidelity(*args,**kwargs):
            self.flags.append("fidelity")
            return {"verified_trading_rules":0,"legacy_rule_candidate_count":1}, {"review_only":True}
        return [patch.object(mod,"fast_prepare",side_effect=preparation),
            patch.object(mod,"validate_fast",side_effect=valid),
            patch.object(mod,"read_pcm_array",side_effect=audio),
            patch.object(mod,"review_real_asr",side_effect=review),
            patch.object(mod,"extract_visual_timeline",side_effect=img),
            patch.object(mod,"ocr_frames",side_effect=ocr),
            patch.object(mod,"join_original_chat_qa",side_effect=join),
            patch.object(mod,"audit_original_teacher_evidence",side_effect=fidelity)],asr_factory

    def run_with(self,**flags):
        from contextlib import ExitStack
        patches,model=self.stub_pipeline(**flags)
        with ExitStack() as s:
            for p in patches:s.enter_context(p)
            return mod.run_session(self.video,self.out,whisper_model_factory=model,ocr_model_factory=lambda **k:None)

    def test_every_stage_must_run_in_one_execution(self):
        result=self.run_with()
        self.assertEqual(result["state"],"SOURCE_PIPELINE_DONE_SEMANTIC_TRUTH_NOT_CERTIFIED")
        self.assertEqual(result["global_audio_chunks_asr_completed"],1)
        self.assertEqual(result["source_screenshots_ocr_completed"],1)
        self.assertEqual(self.flags,["prepare","validate","asr_model","read_audio",
             "review_audio","image","ocr","join","fidelity"])
        self.assertTrue((self.out/"safe_session_result.json").is_file())
        self.assertEqual(result["conservative_question_review_clusters"],1)
        self.assertTrue(result["all_original_question_observations_retained"])
        self.assertTrue((self.out/"private_question_clusters_REVIEW_ONLY.json").is_file())
        self.assertFalse(result["demo_trades_allowed"])
        self.assertFalse(result["real_trades_allowed"])

    def test_incomplete_speech_must_fail_before_visual_work(self):
        with self.assertRaisesRegex(RuntimeError,"speech source coverage incomplete"):
            self.run_with(fail_asr=True)
        self.assertNotIn("image",self.flags)
        self.assertFalse((self.out/"safe_session_result.json").exists())

    def test_ocr_error_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError,"OCR failure"):
            self.run_with(fail_ocr=True)
        self.assertNotIn("join",self.flags)
        self.assertFalse((self.out/"safe_session_result.json").exists())

    def test_fake_verified_answer_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError,"cannot self-approve"):
            self.run_with(false_teacher_answer=True)
        self.assertFalse((self.out/"safe_session_result.json").exists())

    def test_restart_reuses_completed_source_verified_asr_checkpoint(self):
        first=self.run_with()
        self.assertEqual(first["global_audio_chunks_asr_completed"],1)
        self.flags.clear()
        second=self.run_with()
        self.assertEqual(second["global_audio_chunks_asr_completed"],1)
        self.assertNotIn("asr_model",self.flags)
        self.assertNotIn("read_audio",self.flags)
        self.assertIn("review_audio",self.flags)
        self.assertIn("ocr",self.flags)

    def test_corrupt_or_cross_source_checkpoint_is_never_accepted(self):
        self.run_with()
        checkpoint=self.out/"private_asr"/"chunk_0001_UNVERIFIED.json"
        saved=json.loads(checkpoint.read_text(encoding="utf8"))
        saved["source_audio_sha256"]="f"*64
        checkpoint.write_text(json.dumps(saved),encoding="utf8")
        self.flags.clear()
        with self.assertRaisesRegex(ValueError,"ASR checkpoint provenance"):
            self.run_with()
        self.assertNotIn("asr_model",self.flags)
        self.assertNotIn("read_audio",self.flags)

    def test_wrong_asr_model_checkpoint_requires_reprocessing_or_refusal(self):
        self.run_with()
        checkpoint=self.out/"private_asr"/"chunk_0001_UNVERIFIED.json"
        saved=json.loads(checkpoint.read_text(encoding="utf8"))
        saved["model"]="incompatible-old-model"
        checkpoint.write_text(json.dumps(saved),encoding="utf8")
        with self.assertRaisesRegex(ValueError,"ASR checkpoint provenance"):
            self.run_with()

    def test_no_source_video_no_session(self):
        self.video.unlink()
        with self.assertRaisesRegex(ValueError,"Source video not present"):
            mod.run_session(self.video,self.out)


if __name__=="__main__":unittest.main()
