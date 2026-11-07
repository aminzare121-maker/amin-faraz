#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent, fail-closed reliability audit of original teacher-video evidence.

IMPORTANT:
- ASR ≠ exact teacher quote.
- A timestamped chat screenshot ≠ the time a question was posted.
- Nearest audio ≠ verified teacher answer.
- A plausible Persian phrase ≠ executable market rule.
- Passing software tests ≠ measured instructional comprehension accuracy.

This produces a private review packet and *never* releases live or paper orders.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

from artin_teacher_evidence_v4 import line_identity

HASH=re.compile(r"^[a-f0-9]{64}$")
ACTION=re.compile(r"(?:خرید|فروش|بای|سل|لانگ|شورت|ورود|خروج|حد سود|حد ضرر)")
CONDITIONAL=re.compile(r"(?:اگر|زمانی که|وقتی|به شرط|در صورتی|بعد از|قبل از)")
MARKET=re.compile(r"(?:قیمت|کندل|کَندل|کف|سقف|روند|شکست|حمایت|مقاومت|چارت|تایم ?فریم|"
                  r"میانگین|مووینگ|RSI|EMA|ADX|ATR|واگرایی|کلوز|بسته شدن|سطح)")
TEACHING_DEFINITION=re.compile(r"(?:یعنی|فرض کنید|فرض کن|مثال|مثلا|وقتی میگم|اگر بخوام|"
                                r"منظورم|بهش میگن|اصطلاح)")
CORRECTION=re.compile(r"(?:اشتباه گفتم|برعکس|منظورم|اصلاح|درستش|نه نه|گفتم نه)")
SHA_SOURCE_REDACTED="SOURCE_HASHED_NO_PERSONAL_DETAILS"


def clean(text):
    if not isinstance(text,str):return ""
    return " ".join(unicodedata.normalize("NFKC",text).replace("ي","ی")
                    .replace("ك","ک").replace("\u200c"," ").split())


def _num(x):
    return type(x) in (float,int) and math.isfinite(x)


def _verify_review(review):
    if not isinstance(review,dict) or review.get("schema")!="artin_teacher_av_review_v5":
        raise ValueError("Evidence must be authentic V5 original-video review")
    src=review.get("source_video_sha256")
    if not isinstance(src,str) or not HASH.fullmatch(src):
        raise ValueError("Missing source MP4 SHA256")
    duration=review.get("duration_seconds")
    if not _num(duration) or duration<=0:
        raise ValueError("Invalid original video duration")
    parts=review.get("parts_total")
    if type(parts) is not int or parts<1 or parts>10000:
        raise ValueError("Invalid global five-minute part count")
    if parts!=math.ceil((duration-0.000001)/300):
        raise ValueError("Global chunk count inconsistent with movie duration")
    if review.get("parts_with_asr")!=parts or review.get("parts_missing_asr"):
        raise ValueError("Incomplete source ASR coverage: cannot certify any full lesson")
    speech=review.get("speech_lines")
    if not isinstance(speech,list) or not speech:
        raise ValueError("Missing time-sourced ASR evidence")
    seen=set();by_id={};by_qa={}
    for u in speech:
        if not isinstance(u,dict):
            raise ValueError("Invalid utterance object")
        uid=u.get("id");n=u.get("part_global")
        start,end=u.get("start"),u.get("end")
        if (not isinstance(uid,str) or not uid or uid in seen or
                type(n) is not int or not 1<=n<=parts or
                not _num(start) or not _num(end) or
                not 0<=start<end<=duration+0.25):
            raise ValueError("Duplicate, out-of-range or untraceable source utterance")
        seen.add(uid)
        if not isinstance(u.get("text"),str) or not u["text"].strip():
            raise ValueError("Missing source speech candidate text")
        h=u.get("source_audio_sha256")
        if not isinstance(h,str) or not HASH.fullmatch(h):
            raise ValueError("Utterance missing original audio SHA256")
        if u.get("speaker_verified") is True or u.get("human_verified") is True:
            raise ValueError("An ASR-only bundle may not claim verified teacher identity")
        if abs((int((start+end)/2//300)+1)-n)>0:
            # The audio core ownership must match original timeline.
            raise ValueError("Utterance assigned to wrong original global chunk")
        by_id[uid]=u
        by_qa[line_identity(src,n,u)]=u
    ids=set()
    for r in review.get("rule_candidates",[]):
        if not isinstance(r,dict) or r.get("source_utterance_id") not in by_id:
            raise ValueError("Invented rule statement without original speech")
        if r.get("candidate_id") in ids:
            raise ValueError("Repeated rule candidate")
        ids.add(r.get("candidate_id"))
    for q in review.get("possible_questions_and_following_utterances",[]):
        if q.get("question_line_id") not in by_qa:
            raise ValueError("Question is not anchored in original speaker-unknown ASR")
        for ans in q.get("possible_following_utterances",[]):
            if ans.get("line_id") not in by_qa:
                raise ValueError("Potential reply source does not exist")
    return src,duration,parts,by_id,by_qa


def _verify_visual(visual,source,duration):
    if visual is None:return []
    if (not isinstance(visual,dict) or
            visual.get("schema")!="artin_classroom_visual_v6" or
            visual.get("source_video_sha256")!=source):
        raise ValueError("The visual timeline is from another video")
    rows=visual.get("rows")
    if not isinstance(rows,list):raise ValueError("Visual rows missing")
    last=-1;unique=set()
    for row in rows:
        t=row.get("time_seconds"); fid=row.get("frame_id")
        if not _num(t) or not 0<=t<=duration or t<=last or fid in unique:
            raise ValueError("Missing, duplicated or out-of-order video frame evidence")
        last=t;unique.add(fid)
        for channel in ("video_frame","board","chat"):
            v=row.get(channel,{})
            if not isinstance(v.get("sha256"),str) or not HASH.fullmatch(v["sha256"]):
                raise ValueError("Frame evidence missing source SHA256")
    return rows


def audit_original_teacher_evidence(review,visual=None,context_seconds=45):
    """Produce all candidates in REVIEW status, plus a measurable human-review worklist."""
    if type(context_seconds) is not int or not 15<=context_seconds<=180:
        raise ValueError("Context must be 15..180 source-video seconds")
    source,duration,parts,by_id,by_qa=_verify_review(review)
    frames=_verify_visual(visual,source,duration)
    speech=sorted(by_id.values(),key=lambda u:(u["start"],u["id"]))
    all_claims=[]
    for r in review["rule_candidates"]:
        u=by_id[r["source_utterance_id"]]
        t0,t1=u["start"],u["end"]
        nearby=[x for x in speech if x["end"]>=t0-context_seconds and
                x["start"]<=t1+context_seconds]
        source_images=[x for x in frames
             if x["time_seconds"]>=t0-context_seconds and
             x["time_seconds"]<=t1+context_seconds]
        txt=clean(u["text"])
        flags=[]
        if len(txt.split())<9 or txt.endswith(("که","وقتی","اگر","باید","رو","یا")):
            flags.append("FRAGMENT_OR_UNFINISHED_SENTENCE")
        if not ACTION.search(txt):
            flags.append("NO_PRECISE_TRADE_ACTION_IN_UTTERANCE")
        if not CONDITIONAL.search(txt):
            flags.append("NO_CONDITIONAL_TRIGGER_IN_UTTERANCE")
        if not MARKET.search(txt):
            flags.append("NO_OBSERVABLE_MARKET_CONDITION_IN_UTTERANCE")
        if TEACHING_DEFINITION.search(txt):
            flags.append("EXPLANATION_OR_EXAMPLE_NOT_CONFIRMED_AS_STRATEGY")
        if any(x.get("asr_quality_flags") for x in nearby):
            flags.append("NEARBY_ASR_LOW_CONFIDENCE_OR_HALLUCINATION")
        if not source_images:
            flags.append("NO_SYNCHRONIZED_CLASSROOM_SCREENSHOT_IN_REVIEW_WINDOW")
        # A later correction may affect earlier teaching. Automated keyword
        # presence does not prove what rule was superseded.
        later_corrections=[x for x in review.get("possible_later_corrections",[])
                           if _num(x.get("time")) and x["time"]>=t0]
        if later_corrections:
            flags.append("UNRESOLVED_POSSIBLE_LATER_CORRECTIONS")
        all_claims.append({
            "candidate_id":r["candidate_id"],
            "source_utterance_id":u["id"],
            "video_sha256":source,
            "global_part":u["part_global"],
            "start":t0,"end":t1,
            "unverified_asr_quote":txt,
            "audio_sha256":u["source_audio_sha256"],
            "context_audio_seconds":[max(0,round(t0-context_seconds,3)),
                                     min(duration,round(t1+context_seconds,3))],
            "nearby_unverified_asr":[{"id":x["id"],"t":x["start"],"text":x["text"]}
                  for x in nearby],
            "source_video_frames":[{"id":x["frame_id"],"t":x["time_seconds"],
                 "original_sha256":x["video_frame"]["sha256"],
                 "board_sha256":x["board"]["sha256"],
                 "chat_sha256":x["chat"]["sha256"]}
                 for x in source_images],
            "completeness_risks":sorted(set(flags)),
            "speaker_identity_verified":False,
            "teacher_quote_audio_verified":False,
            "chart_example_interpreted_and_verified":False,
            "qa_answer_verified":False,
            "later_corrections_reconciled":False,
            "teacher_strategy_rule_verified":False,
            "status":"REVIEW_REQUIRED",
            "can_execute_trade":False,
            "can_submit_paper_order":False,
        })
    qa=[{"question_line_id":q["question_line_id"],
         "start":q["question_time_seconds"],
         "text_candidate":q["question_text"],
         "potential_replies_count":len(q["possible_following_utterances"]),
         "speaker_identity_verified":False,"actual_teacher_answer_verified":False,
         "status":"REVIEW_REQUIRED"}
        for q in review.get("possible_questions_and_following_utterances",[])]
    critical=[
        "PERSIAN_ASR_HAS_NO_INDEPENDENT_HUMAN_REFERENCE_WER",
        "CHAT_AND_BOARD_OCR_REFERENCE_ACCURACY_NOT_MEASURED",
        "SPEAKER_DIARIZATION_TEACHER_IDENTITY_NOT_VALIDATED",
        "STUDENT_QUESTIONS_AND_TEACHER_ANSWERS_NOT_MATCHED_BY_SOURCE_REVIEW",
        "POTENTIAL_LATER_CORRECTIONS_NOT_RECONCILED",
        "NO_VIDEO_VERIFIED_RULE_WITH_POSITIVE_AND_NEGATIVE_CASES",
        "NO_INDEPENDENT_REPLAY_OF_TEACHER_STRATEGY_ON_DEMO_DATA"]
    if not frames:critical.append("NO_MATCHING_SOURCE_VISUAL_INDEX")
    summary={"schema":"artin_fidelity_audit_v7",
             "source_video_sha256":source,
             "duration_seconds":duration,
             "all_global_audio_parts":parts,
             "speech_lines_source_checked":len(speech),
             "visual_frames_source_checked":len(frames),
             "legacy_rule_candidate_count":len(all_claims),
             "questions_for_review":len(qa),
             "legacy_rule_candidates_missing_source":0,
             "candidate_context_packets":len(all_claims),
             "candidates_with_no_market_condition":sum(
                   "NO_OBSERVABLE_MARKET_CONDITION_IN_UTTERANCE" in
                   x["completeness_risks"] for x in all_claims),
             "critical_quality_gaps":critical,
             "verified_trading_rules":0,
             "asr_word_error_rate":None,
             "image_text_character_error_rate":None,
             "teacher_answer_accuracy":None,
             "teacher_rule_precision":None,
             "teacher_rule_recall":None,
             "status":"NOT_RELIABLE_FOR_EXECUTABLE_RULES",
             "paper_orders_authorized":False,
             "real_orders_authorized":False}
    return summary,{"schema":"artin_private_teacher_review_packet_v7",
             "source_video_sha256":source,
             "candidate_review_packets":all_claims,
             "question_review_packets":qa,
             "cross_boundary_asr_disagreements":
                review.get("cross_boundary_asr_review",[]),
             "possible_teacher_corrections":
                review.get("possible_later_corrections",[]),
             "all_source_material_must_remain_private":True,
             "rules_verified":0}


def write_outputs(review_path,visual_path,out_dir):
    review=json.loads(Path(review_path).read_text(encoding="utf-8"))
    visual=json.loads(Path(visual_path).read_text(encoding="utf-8")) if visual_path else None
    summary,private=audit_original_teacher_evidence(review,visual)
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"fidelity_summary_safe.json").write_text(
         json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    (out_dir/"fidelity_candidates_PRIVATE.json").write_text(
         json.dumps(private,ensure_ascii=False,indent=2),encoding="utf-8")
    print("ARTIN_V7_FIDELITY_AUDIT="+json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    a=argparse.ArgumentParser()
    a.add_argument("--review",type=Path,required=True)
    a.add_argument("--visual",type=Path)
    a.add_argument("--out",type=Path,required=True)
    args=a.parse_args()
    write_outputs(args.review,args.visual,args.out)


if __name__=="__main__":main()
