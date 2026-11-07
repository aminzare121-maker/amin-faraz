#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Original-video lesson readiness: valid abstention is an actual result.

Use previously audited *complete* lesson speech + original image provenance
and fidelity records to determine whether executable STRATEGY RULES are
supported by independent source-reviewed evidence.

Do not create artificial/LLM-invented trades to make an introductory lesson
look like a trading strategy. Fail closed for missing or malformed evidence.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path

J2_SOURCE_SHA="b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff"
SCHEMA="artin_teacher_lesson_readiness_v9"
REQUIRED_RULE_FIELDS=(
  "teacher_source_quote_human_verified",
  "teacher_voice_identity_human_verified",
  "chart_source_condition_human_verified",
  "original_video_time_range_verified",
  "later_corrections_reconciled",
  "all_student_qa_exceptions_checked",
  "positive_and_negative_examples_confirmed",
)
COMPLETE_RULE_STRUCTURE=("market_condition","entry_action","invalidation","exit_rule",
                         "timeframe","risk_limit","source_utterance_ids")


def safe_rule(rule,source,utterances):
    """Reject each missing or ambiguous piece before simulation/strategy export."""
    if not isinstance(rule,dict):return False,["NOT_A_RULE_OBJECT"]
    faults=[name for name in REQUIRED_RULE_FIELDS if rule.get(name) is not True]
    for field in COMPLETE_RULE_STRUCTURE:
        v=rule.get(field)
        if v is None or isinstance(v,str) and not v.strip() or isinstance(v,(list,tuple)) and not v:
            faults.append("MISSING_"+field.upper())
    if rule.get("source_video_sha256")!=source:
        faults.append("SOURCE_VIDEO_HASH_MISMATCH")
    ids=rule.get("source_utterance_ids",[])
    if not isinstance(ids,list) or not ids or not all(isinstance(x,str) and x in utterances for x in ids):
        faults.append("NOT_ALL_VOICE_CLAIMS_FROM_ORIGINAL_UTTERANCES")
    if rule.get("teacher_approval_for_paper_testing") is not True:
        faults.append("NO_EXPLICIT_PAPER_TEST_APPROVAL")
    if rule.get("is_trade_template") is True and rule.get("trade_from_raw_asr") is True:
        faults.append("RAW_ASR_CANNOT_CREATE_TRADE")
    return not faults,faults


def readiness(lesson,review,fidelity,visual_index=None,proposed_rules=None):
    if not isinstance(review,dict) or review.get("schema")!="artin_teacher_av_review_v5":
        raise ValueError("Only full original-video ASR review is accepted")
    source=review.get("source_video_sha256")
    if not isinstance(source,str) or not re.fullmatch("[0-9a-f]{64}",source):
        raise ValueError("Invalid video source SHA256")
    if lesson.get("schema")!="artin_source_lesson_metadata_v9" or lesson.get("video_sha256")!=source:
        raise ValueError("Source lesson metadata and ASR must match")
    duration=review.get("duration_seconds")
    if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
        raise ValueError("Original duration unavailable")
    total=review.get("parts_total")
    if type(total) is not int or total!=math.ceil((duration-1e-6)/300):
        raise ValueError("Incomplete or impossible five-minute timebase")
    if (review.get("parts_with_asr")!=total or
            review.get("parts_missing_asr") or
            not isinstance(review.get("speech_lines"),list) or
            not review.get("speech_lines")):
        raise ValueError("Incomplete speech evidence; cannot evaluate lesson")
    ids=set()
    for line in review["speech_lines"]:
        if not isinstance(line,dict) or line.get("id") in ids or not line.get("text") or not line.get("source_audio_sha256"):
            raise ValueError("Untraceable or duplicate source utterance")
        ids.add(line["id"])
    if fidelity.get("schema")!="artin_fidelity_audit_v7" or fidelity.get("source_video_sha256")!=source:
        raise ValueError("Independent source-linked fidelity audit is required")
    if fidelity.get("speech_lines_source_checked")!=len(ids):
        raise ValueError("Fidelity audit count differs from original source")
    if visual_index is not None:
        if visual_index.get("schema")!="artin_classroom_visual_v6" or visual_index.get("source_video_sha256")!=source:
            raise ValueError("Visual image source different from teacher audio")
        frames=visual_index.get("rows",[])
        if len(frames)!=fidelity.get("visual_frames_source_checked"):
            raise ValueError("Source-backed image timeline incomplete")
    else:
        frames=[]
    declared=lesson.get("chapters")
    if not isinstance(declared,list) or not declared:
        raise ValueError("Source lesson classification lacks timestamped chapters")
    previous=0
    for c in declared:
        lo,hi=c.get("start"),c.get("end")
        if (type(lo) not in (int,float) or type(hi) not in (int,float) or
            lo<0 or lo!=previous or lo>=hi or hi>duration+1):
            raise ValueError("Original lesson chapter boundaries invalid")
        if not isinstance(c.get("topic"),str) or not c["topic"].strip():
            raise ValueError("Unnamed source chapter")
        if c.get("content_human_verified") is True:
            raise ValueError("Model-only lesson outline cannot claim human certification")
        previous=hi
    if abs(previous-duration)>1:
        raise ValueError("Uncovered original lesson duration")

    rules=proposed_rules or []
    if not isinstance(rules,list):
        raise ValueError("Proposed rules must be a list")
    judgments=[{"rule_index":i,"verified_for_paper":safe_rule(rule,source,ids)[0],
                "blocking_evidence":safe_rule(rule,source,ids)[1]}
               for i,rule in enumerate(rules)]
    accepted=sum(x["verified_for_paper"] for x in judgments)
    # This release gate cannot approve a rule merely from LLM output or an
    # unreviewed ASR transcription. No approval by this tool is a brokerage order.
    return {"schema":SCHEMA,"original_video_sha256":source,
       "video_duration_seconds":duration,
       "full_source_audio_parts":total,"speech_lines_seen":len(ids),
       "source_visual_frames_in_audit":len(frames),
       "source_lesson_chapters":declared,
       "ASR_quote_human_accuracy":None,
       "persian_handwriting_accuracy":None,
       "verified_full_teacher_trading_rules":accepted,
       "incomplete_rule_fragments_in_prior_classifier":fidelity.get("legacy_rule_candidate_count"),
       "submitted_rule_claims":len(rules),
       "rule_decisions":judgments,
       "status":"INTRODUCTORY_OR_UNVERIFIED_NO_AUTOMATED_STRATEGY_EXPORT"
                if not accepted else "SOURCE_REVIEWED_RULE_CANDIDATES_PENDING_TEST",
       "mt5_changes_permitted":False,
       "live_trading_permitted":False,
       "requires_more_source_or_reference_review":accepted==0,
       "no_rule_output_is_an_expected_valid_result":True,
       "accuracy_or_teacher_identity_not_inferred":True}


def main():
    p=argparse.ArgumentParser()
    for key in ("lesson","asr","fidelity","visual","out"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args()
    j=lambda path:json.loads(path.read_text(encoding="utf8"))
    result=readiness(j(a.lesson),j(a.asr),j(a.fidelity),j(a.visual))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    brief={k:v for k,v in result.items() if k not in ("source_lesson_chapters","rule_decisions")}
    print("ARTIN_LESSON_READINESS="+json.dumps(brief,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
