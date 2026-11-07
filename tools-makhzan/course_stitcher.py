#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A persistent, incremental, source-first puzzle for Artin instructor videos.

A *new* teacher lesson may explain, amend or contradict an earlier lesson.
Never infer this from timestamps or keywords alone. Preserve every original
utterance, its source evidence identity, and all pending corrections.
This can run on the central GitHub tools-makhzan branch and in future chats.

NO transcription/vision/LLM is bundled in this graph; those are separate
workers whose original-video source hashes must be checked before intake.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

REGISTRY_SCHEMA="makhzan_artin_multi_session_course_v1"
HASH=re.compile(r"^[a-f0-9]{64}$")
VIDEO_ID=re.compile(r"^[A-Z0-9][A-Z0-9_-]{3,80}$")
MODES={"speech","board","chat","video"}
RELATIONS={"CONTINUES","EXPLAINS","CORRECTS","QUALIFIES","EXCEPTION",
           "CONTRADICTS","SUPPORTS","EXAMPLE_FOR"}
REVIEW_STATES={"UNVERIFIED","SOURCE_HUMAN_REVIEWED"}
COURSE_STATUS="WAITING_FOR_USER_TO_SUBMIT_NEXT_TEACHER_VIDEO"


def _require(ok,msg):
    if not ok:raise ValueError(msg)


def _source_sha(value):
    return isinstance(value,str) and bool(HASH.fullmatch(value))


def _session_by_id(doc):
    sessions=doc.get("registered_sessions")
    _require(isinstance(sessions,list) and sessions,"Need actual first submitted class")
    result={}; hashes=set()
    for n,s in enumerate(sessions,1):
        sid=s.get("session_id")
        _require(isinstance(sid,str) and VIDEO_ID.fullmatch(sid) and sid not in result,
                 "Duplicate or malformed session ID")
        _require(s.get("sequence")==n,"Session order must match original submission order")
        _require(s.get("submitted_by_user") is True,"Cannot invent an unsent lesson")
        h=s.get("source_sha256")
        _require(_source_sha(h) and h not in hashes,"Original source video hash missing/repeated")
        duration=s.get("duration_seconds")
        _require(type(duration) in (float,int) and duration>0,"Original lesson duration invalid")
        _require(isinstance(s.get("source_label"),str) and bool(s["source_label"]),
                 "Original filename/source label missing")
        _require(s.get("verified_strategy_rules",0)==0,
                 "Source registry may not itself certify a trading strategy")
        _require(type(s.get("chunks_5min")) is int and
                 s["chunks_5min"]==int((duration-0.000001)//300)+1,
                 "Global five-minute chunk count does not match original duration")
        hashes.add(h);result[sid]=s
    return result


def validate_course(doc):
    _require(isinstance(doc,dict) and doc.get("schema")==REGISTRY_SCHEMA,
             "Missing canonical multiphase Artin course registry")
    _require(doc.get("course_id")=="ARTIN-COURSE-001","Wrong instructor course")
    _require(doc.get("session_count_expected") is None or
             type(doc["session_count_expected"]) is int and
             doc["session_count_expected"]>=len(doc.get("registered_sessions",[])),
             "Unknown expected lesson count must remain unset until user tells us")
    sessions=_session_by_id(doc)
    _require(type(doc.get("all_sessions_received_confirmed_by_user")) is bool,
             "Course-complete declaration must be explicit")
    if not doc["all_sessions_received_confirmed_by_user"]:
        _require(doc.get("next_intake_status")==COURSE_STATUS,
                 "Course cannot be called complete while new class videos are pending")
    nodes=doc.get("evidence_nodes")
    edges=doc.get("cross_session_links")
    _require(isinstance(nodes,list) and isinstance(edges,list),
             "Course must contain evidence graph lists")
    known={}
    for n in nodes:
        _require(isinstance(n,dict),"Non-object source evidence")
        evid=n.get("evidence_id")
        _require(isinstance(evid,str) and VIDEO_ID.fullmatch(evid) and evid not in known,
                 "Duplicate or malformed evidence ID")
        sid=n.get("session_id")
        _require(sid in sessions,"Evidence refers to video user has not sent")
        _require(n.get("video_sha256")==sessions[sid]["source_sha256"],
                 "Evidence source video SHA does not match registered class")
        start,end=n.get("start_seconds"),n.get("end_seconds")
        _require(type(start) in (int,float) and type(end) in (int,float)
                 and 0<=start<end<=sessions[sid]["duration_seconds"]+.25,
                 "Invalid original-video time interval")
        _require(n.get("modality") in MODES,"Missing original evidence modality")
        _require(_source_sha(n.get("source_media_sha256")),"Original media chunk hash missing")
        _require(isinstance(n.get("topic_id"),str) and VIDEO_ID.fullmatch(n["topic_id"]),
                 "Source evidence must declare a stable topic ID")
        _require(n.get("review_status") in REVIEW_STATES,"Unknown source review status")
        if n["review_status"]=="SOURCE_HUMAN_REVIEWED":
            _require(isinstance(n.get("reviewer_reference"),str) and n["reviewer_reference"].strip(),
                     "Human source review needs an independent verifier reference")
        _require(n.get("can_trade") is not True,"Source evidence may never directly place orders")
        known[evid]=n
    edge_ids=set()
    for link in edges:
        _require(isinstance(link,dict),"Cross-session link must be an object")
        lid=link.get("link_id")
        _require(isinstance(lid,str) and VIDEO_ID.fullmatch(lid) and lid not in edge_ids,
                 "Duplicate or malformed explanation link")
        edge_ids.add(lid)
        earlier=known.get(link.get("earlier_evidence_id"))
        later=known.get(link.get("later_evidence_id"))
        _require(earlier is not None and later is not None,
                 "Cannot link nonexistent source evidence")
        _require(sessions[earlier["session_id"]]["sequence"] <
                 sessions[later["session_id"]]["sequence"],
                 "Course amendments must point from earlier to a later teacher session")
        _require(link.get("relationship") in RELATIONS,"Unsupported relationship type")
        _require(link.get("review_status") in REVIEW_STATES,
                 "Cross-lesson interpretation must be flagged unverified")
        if link["review_status"]=="SOURCE_HUMAN_REVIEWED":
            _require(earlier["review_status"]=="SOURCE_HUMAN_REVIEWED" and
                     later["review_status"]=="SOURCE_HUMAN_REVIEWED" and
                     isinstance(link.get("reviewer_reference"),str) and
                     bool(link["reviewer_reference"].strip()),
                     "Only independently reviewed originals can have confirmed meaning links")
        _require(link.get("replaces_earlier_evidence") is not True,
                 "Never erase earlier teacher words after a later correction")
        _require(link.get("can_trade") is not True,
                 "Cross-video link is not an execution-ready strategy")
    return sessions,known


def register_lesson(doc,session):
    """Add only a newly user-submitted real source, preserving first lesson exactly."""
    sessions,_=validate_course(doc)
    _require(doc.get("all_sessions_received_confirmed_by_user") is False,
             "Course already closed; require explicit reopening")
    nxt=copy.deepcopy(doc)
    expected=len(sessions)+1
    _require(isinstance(session,dict) and session.get("sequence")==expected,
             "Next source must follow the previous lesson without renumbering")
    _require(session.get("submitted_by_user") is True,"Only user-submitted videos are permitted")
    _require(session.get("verified_strategy_rules",0)==0,
             "New source cannot arrive as a preapproved trading rule")
    nxt["registered_sessions"].append(copy.deepcopy(session))
    validate_course(nxt)
    return nxt


def append_evidence(doc,nodes):
    nxt=copy.deepcopy(doc)
    _require(isinstance(nodes,list) and nodes,"Provide source-verified evidence nodes")
    nxt["evidence_nodes"].extend(copy.deepcopy(nodes))
    validate_course(nxt)
    return nxt


def link_lessons(doc,links):
    nxt=copy.deepcopy(doc)
    _require(isinstance(links,list) and links,"No cross-session evidence links provided")
    nxt["cross_session_links"].extend(copy.deepcopy(links))
    validate_course(nxt)
    return nxt


def course_puzzle(doc):
    """Return a clear per-topic ordered puzzle and all unresolved revisions."""
    sessions,nodes=validate_course(doc)
    topic_ids=sorted({n["topic_id"] for n in nodes.values()})
    topics=[]
    for topic in topic_ids:
        items=[n for n in nodes.values() if n["topic_id"]==topic]
        items.sort(key=lambda x:(sessions[x["session_id"]]["sequence"],
                                  x["start_seconds"],x["evidence_id"]))
        linked=[l for l in doc["cross_session_links"]
                if nodes[l["earlier_evidence_id"]]["topic_id"]==topic or
                   nodes[l["later_evidence_id"]]["topic_id"]==topic]
        topics.append({"topic_id":topic,
           "source_evidence_count":len(items),
           "session_ids_in_order":list(dict.fromkeys(n["session_id"] for n in items)),
           "source_evidence_ids_in_order":[n["evidence_id"] for n in items],
           "cross_session_connections":len(linked),
           "unverified_links":sum(l["review_status"]!="SOURCE_HUMAN_REVIEWED" for l in linked),
           "corrections_or_exceptions_not_reconciled":sum(
             l["relationship"] in ("CORRECTS","EXCEPTION","CONTRADICTS") and
             l["review_status"]!="SOURCE_HUMAN_REVIEWED" for l in linked),
           "complete_instructor_rule_certified":False})
    result={"schema":"artin_course_puzzle_summary_v1",
       "course_id":doc["course_id"],
       "registered_user_submitted_sessions":len(sessions),
       "session_sequence":[s["session_id"] for s in doc["registered_sessions"]],
       "all_sessions_received_confirmed_by_user":
          doc["all_sessions_received_confirmed_by_user"],
       "next_video_status":doc.get("next_intake_status"),
       "linked_cross_session_evidence_count":len(doc["cross_session_links"]),
       "registered_original_source_evidence":len(nodes),
       "topic_chains":topics,
       "no_unsupported_session_fabricated":True,
       "old_evidence_retained":True,
       "ready_to_issue_teacher_rules":False,
       "paper_or_live_trading_allowed":False,
       "current_status":"WAITING_FOR_NEXT_USER_VIDEO"
               if not doc["all_sessions_received_confirmed_by_user"]
               else "SOURCE_REVIEW_AND_CONSISTENCY_CHECK_REQUIRED"}
    return result


def hydrate_persistent_anchors(doc,root):
    """Hydrate source-anchored metadata from the actual private Makhzan hub.

    Catalogs contain timestamps, source hashes and evidence IDs only;
    never raw student chat, original teacher speech or model-only labels.
    """
    nxt=copy.deepcopy(doc)
    root=Path(root).resolve()
    catalogs=nxt.get("evidence_catalogs",[])
    _require(isinstance(catalogs,list),"Invalid persistent source catalog list")
    sessions,_=validate_course(nxt)
    used=set()
    for entry in catalogs:
        _require(isinstance(entry,str) and entry not in used,
                 "Duplicate or invalid source evidence catalog")
        used.add(entry)
        target=(root/entry).resolve()
        _require(target.is_relative_to(root) and target.is_file(),
                 "Registered permanent source evidence catalog is missing")
        item=json.loads(target.read_text(encoding="utf8"))
        _require(item.get("schema")=="artin_source_anchor_catalog_v1" and
                 item.get("contains_original_audio_or_classroom_chat_text") is False and
                 item.get("all_personal_content_excluded") is True,
                 "Source anchor catalog is not private-text safe")
        sid=item.get("session_id")
        _require(sid in sessions and
                 item.get("source_video_sha256")==sessions[sid]["source_sha256"],
                 "Permanent catalog source SHA/session identity mismatch")
        nodes=item.get("evidence_nodes")
        _require(isinstance(nodes,list) and bool(nodes),
                 "Permanent source anchor list is empty")
        nxt=append_evidence(nxt,nodes)
    return nxt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--registry",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    doc=json.loads(args.registry.read_text(encoding="utf-8"))
    doc=hydrate_persistent_anchors(doc,Path(__file__).resolve().parent.parent)
    report=course_puzzle(doc)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    safe={k:v for k,v in report.items() if k!="topic_chains"}
    print("ARTIN_MULTI_SESSION_PUZZLE="+json.dumps(safe,ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
