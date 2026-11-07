#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ingest REAL existing ASR + chat + fidelity artifact into durable private
multi-session source ANCHOR INDEX without storing student names or ASR text.

The original ASR content remains in private GitHub artifacts; this compact
source provenance index survives those artifacts expiring. It is not a gold
transcript and does not approve any trading strategy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from course_stitcher import validate_course, append_evidence, course_puzzle

def canon(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def digest(v):
    return hashlib.sha256(str(v).encode("utf8")).hexdigest()

def die_if(test,message):
    if not test:raise ValueError(message)

def generate(course,asr,qa,fidelity):
    sessions,existing=validate_course(course)
    die_if(len(sessions)==1,"This initial source-index importer only handles the first REAL lesson")
    session=course["registered_sessions"][0]
    src=session["source_sha256"]
    for name,obj,schema in [
        ("speech",asr,"artin_teacher_av_review_v5"),
        ("chat",qa,"artin_private_typed_chat_audio_candidates_v8"),
        ("rule review",fidelity,"artin_private_teacher_review_packet_v7")]:
        die_if(obj.get("schema")==schema and obj.get("source_video_sha256")==src,
               "Original source validation failed for "+name)
    parts=asr.get("parts_total")
    die_if(parts==session["chunks_5min"] and asr.get("parts_with_asr")==parts and
           not asr.get("parts_missing_asr"),"Real original-video ASR incomplete")
    lines=asr.get("speech_lines")
    questions=qa.get("question_groups")
    claims=fidelity.get("candidate_review_packets")
    die_if(isinstance(lines,list) and len(lines)>=1 and
           isinstance(questions,list) and isinstance(claims,list),
           "Missing source evidence content")
    die_if(asr.get("rules_executable")==0 and fidelity.get("rules_verified")==0,
           "Source cannot be enrolled as already executable")
    nodes=[];mapped={}
    last=-1
    for i,u in enumerate(sorted(lines,key=lambda x:(x["start"],x["id"])),1):
        start,end=u["start"],u["end"]
        uid=u["id"]
        h=u.get("source_audio_sha256")
        die_if(isinstance(uid,str) and uid not in mapped and
           isinstance(h,str) and len(h)==64 and
           isinstance(u.get("text"),str) and u["text"].strip() and
           0<=start<end<=session["duration_seconds"]+.25,
           "Invalid source utterance identity, text or time")
        mapped[uid]=len(nodes)
        nodes.append({
            "evidence_id":f"EVID-J2-SPEECH-{i:05d}",
            "session_id":session["session_id"],"video_sha256":src,
            "start_seconds":start,"end_seconds":end,
            "modality":"speech","source_media_sha256":h,
            "source_utterance_id":uid,
            "original_asr_text_sha256":digest(u["text"]),
            "topic_id":"TOPIC-UNCLASSIFIED-VOICE",
            "topic_classification_verified":False,
            "speaker_identity_verified":False,
            "review_status":"UNVERIFIED","can_trade":False})
    checked=set()
    for i,p in enumerate(claims,1):
        uid=p.get("source_utterance_id")
        die_if(uid in mapped and uid not in checked and p.get("video_sha256")==src,
               "Rule candidate does not have unique original audio utterance")
        checked.add(uid)
        node=nodes[mapped[uid]]
        die_if(p.get("audio_sha256")==node["source_media_sha256"],
               "Rule candidate original source audio changed")
        node["unverified_rule_candidate_id"]=p["candidate_id"]
        node["rule_readiness"]="INCOMPLETE_UNVERIFIED_ORIGINAL_LESSON_FRAGMENT"
        node["required_evidence_missing"]=p.get("completeness_risks",[])
    for i,q in enumerate(questions,1):
        fs=q.get("frame_sources",[])
        die_if(isinstance(fs,list) and fs and
            isinstance(q.get("candidate_text"),str) and
            isinstance(q.get("first_seen"),(float,int)) and
            isinstance(q.get("last_seen"),(float,int)),
            "Original chat question source or timeline missing")
        fr=fs[0]
        h=fr.get("chat_frame_sha256")
        start=q["first_seen"]
        die_if(isinstance(h,str) and len(h)==64 and
               0<=start<session["duration_seconds"] and
               fr.get("observed_at_seconds")==start,
               "Invalid original classroom screenshot identity/time")
        nodes.append({
            "evidence_id":f"EVID-J2-QUESTION-{i:05d}",
            "session_id":session["session_id"],"video_sha256":src,
            "start_seconds":start,
            "end_seconds":min(start+1,session["duration_seconds"]),
            "modality":"chat",
            "source_media_sha256":h,
            "source_frame_id":fr["frame_id"],
            "original_ocr_text_sha256":digest(q["candidate_text"]),
            "question_post_time_verified":False,
            "teacher_answer_verified":False,
            "topic_id":"TOPIC-STUDENT-QUESTION-UNCLASSIFIED",
            "topic_classification_verified":False,
            "review_status":"UNVERIFIED","can_trade":False})
    source_puzzle=append_evidence(course,nodes)
    report=course_puzzle(source_puzzle)
    die_if(report["registered_original_source_evidence"]==len(lines)+len(questions),
           "Cannot persist a partial real first video index")
    die_if(report["ready_to_issue_teacher_rules"] is False,
           "A source registration job cannot issue paper/live trades")
    summary={"schema":"artin_real_j2_source_anchor_summary_v1",
      "source_video_sha256":src,"session_id":session["session_id"],
      "original_asr_utterances_source_linked":len(lines),
      "original_classroom_question_groups_source_linked":len(questions),
      "unverified_rule_fragments_anchored_to_original_audio":len(claims),
      "total_persistent_source_anchors":len(nodes),
      "all_17_five_minute_audio_parts_in_source":parts,
      "source_text_in_git_commit":False,
      "teacher_meaning_independently_validated":False,
      "teacher_trading_rules_verified":0,
      "source_puzzle_topic_groups":len(report["topic_chains"]),
      "next_video_status":report["current_status"],
      "prevents_fabricated_later_video":True}
    return nodes,summary

def main():
    p=argparse.ArgumentParser()
    for name in ("course","asr","qa","fidelity","out"):
        p.add_argument("--"+name,type=Path,required=True)
    args=p.parse_args()
    load=lambda f:json.loads(f.read_text(encoding="utf8"))
    nodes,summary=generate(load(args.course),load(args.asr),load(args.qa),load(args.fidelity))
    args.out.mkdir(parents=True,exist_ok=True)
    result={"schema":"artin_source_anchor_catalog_v1",
            "source_video_sha256":summary["source_video_sha256"],
            "session_id":summary["session_id"],
            "all_personal_content_excluded":True,
            "contains_original_audio_or_classroom_chat_text":False,
            "evidence_nodes":nodes}
    (args.out/"J2_SOURCE_ANCHORS.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    (args.out/"J2_ANCHORS_SUMMARY_SAFE.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
    print("ARTIN_REAL_J2_PUZZLE_ANCHORS="+canon(summary),flush=True)
if __name__=="__main__":main()
