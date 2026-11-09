#!/usr/bin/env python3
"""Isolated, non-trading Artin20 evidence review. No teacher rules certified."""
from __future__ import annotations
import collections
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

OUT = Path("artin20_semantic_output")
REPO = "aminzare121-maker/amin-faraz"
SOURCE_ARTIFACT_ID = 13691821276
TERMS = {
    "entry": ["ورود", "وارد", "انتری", "پوزیشن بگیر", "پوزیشن باز", "خرید", "فروش", "بای", "سل"],
    "exit": ["خروج", "بستن", "ببند", "ببندیم", "سیو سود", "تی پی", "حد سود", "تارگت"],
    "risk": ["استاپ", "حد ضرر", "ریسک", "ضرر", "لات", "حجم", "سرمایه"],
    "confirmation": ["تایید", "تأیید", "شرط", "صبر", "کندل", "بسته بش", "بسته شد", "شکست"],
    "market": ["روند", "حمایت", "مقاومت", "پولبک", "بازگشت", "نقدینگی", "تایم فریم", "تایم‌فریم"],
    "revision": ["جلسه قبل", "جلسه قبلی", "دفعه قبل", "اشتباه", "تصحیح", "اصلاح", "برخلاف", "استثنا"]
}
NEGATIONS = ["نکن", "نباید", "نمی‌ش", "نمی ش", "نه", "ممنوع", "اشتباه"]
def normalized(s):
    return str(s).replace("ي","ی").replace("ك","ک").replace("\u200c"," ").replace("أ","ا").replace("ۀ","ه").strip().lower()
def term_present(phrase, text):
    p=normalized(phrase)
    # A short standalone trade word (buy/sell) must not match Persian words like "باید".
    if p in {"بای","سل","روند"}:
        return re.search(r"(?<!\\w)"+re.escape(p)+r"(?!\\w)", text) is not None
    return p in text
def sha(data): return hashlib.sha256(data).hexdigest()
def read_zip_jsonl(z, basename):
    hits=[n for n in z.namelist() if n.endswith(basename)]
    if len(hits)!=1:raise RuntimeError(f"Expected exactly one {basename}: {hits}")
    blob=z.read(hits[0])
    return [json.loads(x) for x in blob.decode("utf-8-sig").splitlines() if x.strip()], sha(blob)
def read_summary(z):
    hits=[n for n in z.namelist() if n.endswith("/summary.json") or n=="summary.json"]
    if len(hits)!=1:raise RuntimeError(f"Source summary missing/ambiguous: {hits}")
    return json.loads(z.read(hits[0]))
def dump(path,doc):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding="utf-8")
def write_jsonl(path,rows):
    with path.open("w",encoding="utf-8") as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+"\n")
def main():
    OUT.mkdir(exist_ok=True)
    raw=OUT/"source_artifact.zip"
    with raw.open("wb") as f:
        p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{SOURCE_ARTIFACT_ID}/zip"],
                         stdout=f,stderr=subprocess.PIPE,timeout=300)
    if p.returncode:raise RuntimeError("SOURCE_ARTIFACT_FETCH_FAILED: "+p.stderr.decode("utf-8","replace")[:250])
    if not zipfile.is_zipfile(raw):raise RuntimeError("SOURCE_ARTIFACT_IS_NOT_ZIP")
    with zipfile.ZipFile(raw) as z:
        assert z.testzip() is None,"Corrupt source archive"
        speech,hash_speech=read_zip_jsonl(z,"speech_source_rows_UNVERIFIED.jsonl")
        visual,hash_visual=read_zip_jsonl(z,"visual_source_rows_UNVERIFIED.jsonl")
        temporal,hash_temporal=read_zip_jsonl(z,"temporal_candidates_NOT_SEMANTIC.jsonl")
        source=read_summary(z)
    raw.unlink() # source stays unchanged in the original GitHub run
    if len(temporal)!=len(speech):raise RuntimeError("SPEECH_TIME_ROW_COUNT_MISMATCH")
    if len(speech)!=source.get("speech_records"):raise RuntimeError("SPEECH_COUNT_MISMATCH")
    if len(visual)!=source.get("chat_ocr_records",0)+source.get("board_ocr_records",0):
        raise RuntimeError("VISUAL_COUNT_MISMATCH")
    if source.get("teacher_semantic_verified") is not False:raise RuntimeError("SOURCE_VERIFICATION_STATUS_UNEXPECTED")
    review=[]
    whole=[]
    priorities=collections.Counter()
    link_counts=collections.Counter()
    time_issue=0
    visual_with_text=0
    for i,(s,t) in enumerate(zip(speech,temporal)):
        if t.get("speech_index")!=i:raise RuntimeError("TEMPORAL_INDEX_OUT_OF_ORDER")
        txt=s.get("text") or ""
        norm=normalized(txt)
        categories={cat:[p for p in phrases if term_present(p,norm)] for cat,phrases in TERMS.items()}
        categories={cat:phrases for cat,phrases in categories.items() if phrases}
        if not categories:continue
        linked=[]
        for h in t.get("visual_candidates",[]):
            idx=h["visual_index"]
            if not isinstance(idx,int) or idx<0 or idx>=len(visual):raise RuntimeError("VISUAL_LINK_INDEX_INVALID")
            v=visual[idx]
            ocr=v.get("text","")
            if isinstance(ocr,list):
                ocr=" ".join(str(w) if not isinstance(w,dict) else json.dumps(w,ensure_ascii=False) for w in ocr)
            elif isinstance(ocr,dict):ocr=json.dumps(ocr,ensure_ascii=False)
            if str(ocr).strip():visual_with_text+=1
            relation=h.get("relation")
            if relation not in ["WITHIN_SPEECH_INTERVAL","NEAR_START_WITHIN_6_SECONDS"]:
                raise RuntimeError("UNRECOGNIZED_TEMPORAL_LINK")
            link_counts[relation]+=1
            linked.append({
                "relation":relation,"delta_seconds":h.get("delta_seconds"),
                "visual_time_seconds":v.get("time_start"),"source_visual_id":v.get("source_id"),
                "visual_kind":v.get("category"),"source_file":v.get("source_file"),
                "source_frame_sha256":v.get("source_frame_sha256"),
                "ocr_text_original":v.get("text"),"ocr_has_content":bool(str(ocr).strip()),
                "verified_meaning":False
            })
        # Important: a time match alone never certifies that the picture illustrates the speaker's words.
        score=len(categories)*3+(2 if any(x["relation"]=="WITHIN_SPEECH_INTERVAL" and x["ocr_has_content"] for x in linked) else 0)
        score+=1 if any(x["visual_kind"]=="board" for x in linked) else 0
        score+=2 if "revision" in categories else 0
        if not linked:time_issue+=1
        label="REVIEW_PRIORITY" if score>=8 else "POTENTIAL_CONTEXT"
        context=[{
            "speech_index":j,"time_start":speech[j].get("time_start"),
            "time_end":speech[j].get("time_end"),"text_exact":speech[j].get("text",""),
            "speaker_verified":speech[j].get("speaker_verified",False)
        } for j in range(max(0,i-3),min(len(speech),i+4))]
        context_text=normalized(" ".join(str(x.get("text_exact") or "") for x in context))
        explicit_conditional_cue=any(term_present(x,context_text) for x in ["اگر","وقتی","زمانی که"])
        temporal_exact_with_nonempty_ocr=any(x["relation"]=="WITHIN_SPEECH_INTERVAL" and x["ocr_has_content"] for x in linked)
        priorities[label]+=1
        rec={
            "candidate_id":f"artin20-speech-{i:04d}","source_video_queue_sequence":20,
            "video_name_in_queue":"فیلم ۱۸","speech_index":i,"speech_time_start":s.get("time_start"),
            "speech_time_end":s.get("time_end"),"speech_text_exact":txt,
            "speech_source_file":s.get("source_file"),"speech_source_id":s.get("source_id"),
            "source_audio_sha256":s.get("source_audio_sha256"),
            "teacher_speaker_verified":bool(s.get("speaker_verified",False)),
            "lexical_tags":categories,"negation_cues":[p for p in NEGATIONS if term_present(p,norm)],
            "speech_context_unverified":context,
            "conditional_language_nearby_not_verified":explicit_conditional_cue,
            "exact_time_visual_with_nonempty_ocr":temporal_exact_with_nonempty_ocr,
            "visual_candidates":linked,
            "evidence_priority_score_not_confidence":score,
            "label":label,
            "cross_session_rule_verified":False,
            "teacher_semantics_verified":False,
            "mt5_executable_rule_approved":False
        }
        review.append(rec)
    review.sort(key=lambda r:(-r["evidence_priority_score_not_confidence"],r["speech_index"]))
    write_jsonl(OUT/"speech_visual_review_queue_UNVERIFIED.jsonl",review)
    # An explicit no-trade gate avoids turning keyword matches into instructions.
    gate={
        "schema":"artin20_mql5_semantics_gate_v1",
        "teacher_rules_approved":0,"allow_mt5_auto_entry":False,
        "source_teacher_semantics_verified":False,
        "note":"Only teacher-confirmed actions from audio+visual examples and cross-session reviews may be executable."
    }
    dump(OUT/"mt5_rule_gate.json",gate)
    summary={
        "schema":"artin20_source_grounded_review_v1","source_artifact_run":42655568756,
        "source_artifact_id":SOURCE_ARTIFACT_ID,
        "source_sha256":{"speech":hash_speech,"visual":hash_visual,"temporal":hash_temporal},
        "speech_total":len(speech),"visual_total":len(visual),
        "speech_with_detected_trading_or_revision_terms":len(review),
        "review_priority_count":priorities["REVIEW_PRIORITY"],
        "potential_context_count":priorities["POTENTIAL_CONTEXT"],
        "candidates_without_temporal_visual":time_issue,
        "visual_links_with_nonempty_ocr":visual_with_text,
        "review_records_with_context":len(review),
        "lexical_match_only_not_semantic":True,
        "teacher_roles_not_authenticated":True,
        "semantic_verified_count":0,"mt5_rules_approved":0,"originals_mutated":False,
        "status":"SOURCE_GROUNDED_REVIEW_CANDIDATES_READY_NOT_TEACHER_CERTIFIED"
    }
    dump(OUT/"review_summary.json",summary)
    sample=[{"id":x["candidate_id"],"start":x["speech_time_start"],"tags":list(x["lexical_tags"]),
             "text":x["speech_text_exact"][:210],"visual_links":len(x["visual_candidates"])}
             for x in review[:8]]
    dump(OUT/"review_priority_sample.json",sample)
    tests={
        "original_speech_count_matches":len(speech)==source["speech_records"],
        "original_ocr_count_matches":len(visual)==source["chat_ocr_records"]+source["board_ocr_records"],
        "temporal_list_matches_speech":len(temporal)==len(speech),
        "all_source_rows_unverified":all(not x.get("semantic_verification") for x in speech+visual),
        "all_rule_candidates_unverified":all(x["mt5_executable_rule_approved"] is False for x in review),
        "zero_approved_mql5_rules":gate["teacher_rules_approved"]==0
    }
    dump(OUT/"tests.json",tests)
    print("ARTIN20_SEMANTIC_REVIEW_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
    print("ARTIN20_REVIEW_SAMPLE="+json.dumps(sample,ensure_ascii=False),flush=True)
    print("ARTIN20_TEST_RESULTS="+json.dumps(tests),flush=True)
    if not all(tests.values()):sys.exit(2)
if __name__=="__main__":main()
