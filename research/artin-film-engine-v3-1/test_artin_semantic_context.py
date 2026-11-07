"""Synthetic-only checks for 18-way neighboring semantic context and noise isolation."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import artin_film_pipeline as pipeline
import artin_semantic_context as context


class SemanticContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def parts(self):
        chunks=pipeline.chunk_plan(5400)
        for c in chunks:
            c["clip_sha256"]="d"*64
            c["frames"]=[]
        pipeline.atomic_json(self.root/"manifest.json",{
            "schema":"artin_video_manifest_v1", "video_sha256":"e"*64,
            "source_duration":5400, "video_path_private":"/unavailable.mp4",
            "chunks":chunks})
        return chunks

    def seg(self,chunk,index,start,end,text):
        return {"id":f"c{chunk:02}_u{index:04}","start":start,"end":end,
                "text":text,"speaker":"UNKNOWN","speaker_verified":False}

    def prepare_18_transcripts(self):
        chunks=self.parts()
        populated={
            1:[self.seg(1,1,299,299.9,"چرا در اینجا خرید نمی گیریم؟")],
            2:[self.seg(2,1,302,305,"باید منتظر کندل تایید بمانیم"),
               self.seg(2,2,320,322,"قانون اول برای خرید منتظر کندل می مانیم")],
            3:[self.seg(3,1,615,617,"اینترنت قطع شد و صدای من نمیاد")],
            18:[self.seg(18,1,5300,5310,"قانون اول را اصلاح می کنم برای ورود باید تایید را ببینیم")],
        }
        for c in chunks:
            pipeline.atomic_json(self.root/c["transcript"],{
                "schema":"artin_chunk_transcript_v1","chunk":c["chunk"],
                "source_clip_sha256":c["clip_sha256"],
                "segments":populated.get(c["chunk"],[]),
                "original_audio_reviewed":False})
        return chunks

    def test_clear_noise_cannot_become_trade_rule(self):
        self.assertEqual(context.noise_risk("اینترنت قطع شد و صدای من نمیاد"),"CLEAR_OFFTOPIC")
        self.assertEqual(context.noise_risk("اینترنت قطع شد ولی حد ضرر را روی کندل بگذارید"),"MIXED_CONTEXT_REVIEW")
        self.assertEqual(context.noise_risk("حد ضرر پشت کندل و حد سود بالای چارت"),"NOT_IDENTIFIED")
        p=pipeline.chunk_plan(5400)[0]
        u=self.seg(1,1,20,25,"صدا قطع شد")
        good,bad=pipeline.validate_model_events({"events":[{
            "kind":"RULE","source_ids":[u["id"]],"exact_quote":u["text"],
            "rule_label":"قانون جعلی ورود","decision":"BUY","conditions":["BUY"]}]},[u],p)
        self.assertEqual(bad,[])
        self.assertEqual(good[0]["kind"],"CLASSROOM_NOISE")
        self.assertEqual(good[0]["decision_candidate"],"UNKNOWN")
        self.assertEqual(good[0]["condition_candidates"],[])
        self.assertEqual(good[0]["rule_label_candidate"],"")

    def test_mixed_noise_quarantined_without_erasing_the_record(self):
        model=[{"id":"fake","kind":"RULE","quote":"اینترنت قطع شد ولی حد ضرر را پشت کندل بگذارید"}]
        relevant,quarantined=context.quarantine_events(model)
        self.assertEqual(relevant,[])
        self.assertEqual(len(quarantined),1)
        self.assertEqual(quarantined[0]["noise_review_status"],"MIXED_TECH_AND_TRADING_REVIEW")
        self.assertIn("حد ضرر",quarantined[0]["quote"])
        self.assertFalse(quarantined[0]["can_change_artin_engine"])

    def test_anchor_must_quote_exact_original_segment(self):
        part=pipeline.chunk_plan(5400)[0]
        seg=self.seg(1,1,20,23,"این فقط گفتار آزمایشی است")
        capsule,rej=context.validate_capsule({"anchors":[{
            "source_id":seg["id"],"exact_quote":"حد ضرر ۵ دلار",
            "kind":"RULE"}]},[seg],part)
        self.assertEqual(capsule["anchors"],[])
        self.assertEqual(rej[0]["reason"],"FABRICATED_QUOTE")
        self.assertFalse(capsule["teacher_meaning_understood_and_verified"])

    def test_neighbors_have_distinct_previous_and_next_windows(self):
        capsules={x:{"anchors":[{"id":f"ac_{x}"}]} for x in range(1,19)}
        middle=context.adjacent_context(10,capsules)
        self.assertEqual(middle["previous"]["chunk"],9)
        self.assertEqual(middle["next"]["chunk"],11)
        self.assertEqual(middle["previous"]["anchors"][0]["id"],"ac_9")
        self.assertIsNone(context.adjacent_context(1,capsules)["previous"]["chunk"])
        self.assertIsNone(context.adjacent_context(18,capsules)["next"]["chunk"])

    def test_unknown_neighbor_anchor_never_enters_event_graph(self):
        p=pipeline.chunk_plan(5400)[1]
        s=self.seg(2,1,302,305,"این یک پاسخ است")
        events,rejected=pipeline.validate_model_events({"events":[{
            "kind":"ANSWER","source_ids":[s["id"]],"exact_quote":s["text"],
            "related_context_ids":["nonexistent_anchor"]}]},[s],p,neighbor_anchor_ids={"ac_ok"})
        self.assertEqual(events,[])
        self.assertEqual(rejected[0]["reason"],"UNAUTHENTICATED_NEIGHBOR_CONTEXT_REFERENCE")

    def test_full_18_chunk_two_pass_neighbor_synthesis_and_noise(self):
        self.prepare_18_transcripts()
        capsule_calls=[];analysis_calls=[]
        def pretend_local_ollama(model,prompt,frames=None,endpoint=None,system_prompt=None,**kwargs):
            data=json.loads(prompt);n=data["chunk"]
            if "segments" in data:
                capsule_calls.append(n)
                return {"anchors":[{
                    "source_id":s["id"],"exact_quote":s["text"],
                    "kind":("QUESTION" if n==1 else "ANSWER" if n==2 and "منتظر" in s["text"]
                         else "CLASSROOM_NOISE" if n==3 else "CORRECTION" if n==18
                         else "RULE")
                } for s in data["segments"]]}
            analysis_calls.append(n)
            previous=data["adjacent_five_minute_context"]["previous"]
            following=data["adjacent_five_minute_context"]["next"]
            if n==2:
                self.assertEqual(previous["chunk"],1)
                self.assertEqual(following["chunk"],3)
                self.assertEqual(len(previous["anchors"]),1)
            if n==1:
                self.assertEqual(following["chunk"],2)
                self.assertIsNone(previous["chunk"])
            own=[x for x in data["transcript"] if data["core_start"]<=x["start"]<data["core_end"]]
            out=[]
            for s in own:
                is_noise="اینترنت" in s["text"]
                kind=("QUESTION" if n==1 else "ANSWER" if n==2 and "باید" in s["text"]
                       else "RULE" if n==2 else "CORRECTION" if n==18 else "RULE")
                referenced=previous["anchors"][0]["id"] if n==2 and previous["anchors"] else None
                event={"kind":kind,"source_ids":[s["id"]],
                    "exact_quote":s["text"],
                    "rule_label":"قاعده ساختگی اول" if n in (2,18) else "",
                    "decision":"BUY","conditions":["ابتدا شرط"]}
                if referenced and kind=="ANSWER":
                    event["related_context_ids"]=[referenced]
                out.append(event)
            return {"events":out}
        with patch.object(pipeline,"ollama_json",side_effect=pretend_local_ollama):
            capsules=pipeline.build_context_capsules(self.root,"offline-mock",workers=6)
            analyses=pipeline.analyze(self.root,"offline-mock",workers=6,
                                      require_capsules=True)
        self.assertEqual(len(capsules),18)
        self.assertEqual(len(analyses),18)
        self.assertEqual(set(capsule_calls),set(range(1,19)))
        self.assertEqual(set(analysis_calls),set(range(1,19)))
        report=pipeline.merge(self.root)
        self.assertTrue(report["transcript_and_semantic_outputs_present"])
        self.assertEqual(report["chunk_count"],18)
        self.assertEqual(report["possible_question_answer_links"],1)
        self.assertEqual(report["possible_later_corrections"],1)
        self.assertEqual(report["quarantined_classroom_noise"],1)
        self.assertGreaterEqual(report["cross_chunk_context_review_edges"],1)
        graph=json.loads((self.root/"rule_candidate_graph.json").read_text())
        self.assertEqual(len(graph["candidate_rules"]),1)
        self.assertFalse(graph["may_modify_engine"])
        noise=json.loads((self.root/"noise_quarantine.json").read_text())
        self.assertEqual(noise["quarantined_events"][0]["kind"],"CLASSROOM_NOISE")
        self.assertIn("اینترنت قطع شد",noise["quarantined_events"][0]["quote"])
        handoff=json.loads((self.root/"artin_engine_handoff.json").read_text())
        self.assertEqual(handoff["trade_permissions"],0)
        self.assertFalse(handoff["candidate_rules"][0]["engine_code_ready"])

    def test_missing_neighbor_capsule_fails_strict_mode(self):
        self.prepare_18_transcripts()
        with self.assertRaisesRegex(FileNotFoundError,"Missing first-pass context capsule"):
            pipeline.analyze(self.root,"any-model",require_capsules=True)


if __name__=="__main__":
    unittest.main()
