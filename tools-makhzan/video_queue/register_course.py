#!/usr/bin/env python3
"""Register a completed original-source VIDEO-001 film in the open Artin course.

Register in user submission order, never invent source labels, teacher identities,
rule confirmation, semantic corrections, or replacement of earlier lectures.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from course_stitcher import register_lesson,validate_course

COURSE_PATH="tools-makhzan/courses/artin/COURSE_REGISTRY.json"
BRANCH="tools-makhzan-hub"
REPO="aminzare121-maker/amin-faraz"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def session_from_original_evidence(sequence,source_page,summary,proof,run_id,queue_id):
    sha=summary.get("source_video_sha256")
    assert isinstance(sha,str) and re.fullmatch(r"[a-f0-9]{64}",sha), "Missing original movie SHA"
    assert proof["original_source_video_sha256"]==sha, "Video identity mismatch"
    assert proof["source_evidence_loss"]==0 and proof["independent_hash_and_time_evidence_complete"] is True
    assert proof["original_five_minute_audio_parts"]==summary["source_global_audio_chunks"]
    assert proof["original_ocr_screenshots_finished"]==summary["original_chat_images_selected"]
    assert proof["original_sampled_board_frames"]==summary["original_board_frames"]
    assert proof["original_screen_frames_scanned"]==summary["one_second_frames_scanned"]
    assert proof["teacher_semantic_accuracy_independently_verified"] is False
    from urllib.parse import urlsplit
    source_key=urlsplit(source_page).path.strip("/").split("/")[-1]
    assert re.fullmatch(r"[A-Za-z0-9_-]{3,80}",source_key)
    assert type(sequence) is int and sequence>=2
    url=f"https://github.com/{REPO}/actions/runs/{int(run_id)}"
    return {
        "session_id":f"ARTIN-SESSION-{sequence:03d}",
        "sequence":sequence,
        "source_label":f"Original submitted Uupload class {source_key} (filename not independently verified)",
        "submitted_by_user":True,
        "source_page":source_page,
        "source_sha256":sha,
        "duration_seconds":float(summary["original_duration_seconds"]),
        "chunks_5min":int(summary["source_global_audio_chunks"]),
        "evidence_status":"FULL_SOURCE_EVIDENCE_EXTRACTED_SEMANTIC_REVIEW_REQUIRED",
        "source_audio_run":url,
        "source_ocr_run":url,
        "source_qa_run":url,
        "source_queue_id":queue_id,
        "original_chat_ocr_screenshots":int(proof["original_ocr_screenshots_finished"]),
        "original_sampled_board_frames":int(proof["original_sampled_board_frames"]),
        "original_one_second_frame_checks":int(proof["original_screen_frames_scanned"]),
        "provisional_qa_groups":int(proof["provisional_chat_groups"]),
        "verified_strategy_rules":0,
        "topic_tags_candidate":[],
        "topic_tags_human_verified":False,
        "semantic_links_to_previous_sessions_verified":False
    }

def api(method,path,token,body=None):
    payload=json.dumps(body).encode("utf8") if body is not None else None
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "User-Agent":"VIDEO001-course-ordered-intake",
             "X-GitHub-Api-Version":"2022-11-28"}
    if payload is not None:headers["Content-Type"]="application/json"
    req=Request("https://api.github.com"+path,method=method,headers=headers,data=payload)
    with urlopen(req,timeout=30) as res:
        return json.load(res)

def record_session(session,token):
    url=f"/repos/{REPO}/contents/{quote(COURSE_PATH,safe='/')}"
    for attempt in range(4):
        old=api("GET",url+"?ref="+BRANCH,token)
        doc=json.loads(base64.b64decode(old["content"]).decode("utf8"))
        validate_course(doc)
        same_hash=next((x for x in doc["registered_sessions"] if x["source_sha256"]==session["source_sha256"]),None)
        if same_hash:
            if same_hash.get("source_page")!=session["source_page"] or same_hash["sequence"]!=session["sequence"]:
                raise ValueError("Duplicate source film or incorrect ordered session; refuse registering")
            return "ALREADY_REGISTERED"
        if len(doc["registered_sessions"])+1!=session["sequence"]:
            raise ValueError("Course has a missing prior video. Do not invent or skip it.")
        nextdoc=register_lesson(doc,session)
        body={"message":"Register source-verified user-submitted course session "+session["session_id"],
              "branch":BRANCH,"sha":old["sha"],
              "content":base64.b64encode((json.dumps(nextdoc,ensure_ascii=False,indent=2)+"\n").encode("utf8")).decode("ascii")}
        try:
            result=api("PUT",url,token,body)
            return result["commit"]["sha"]
        except HTTPError as exc:
            if exc.code not in (409,422) or attempt==3:raise
            time.sleep(2*(attempt+1))
    raise RuntimeError("Unable to commit course session after bounded retries")

def main():
    env=os.environ
    queue_id=env["VIDEO001_QUEUE_ID"]
    match=re.fullmatch(r"video-q-([0-9]{4})-[a-z0-9-]{4,64}",queue_id)
    if not match:raise ValueError("Invalid queue session ID")
    sequence=int(env.get("VIDEO001_SESSION_SEQUENCE",str(int(match.group(1)))))
    if sequence!=int(match.group(1)):
        raise ValueError("Session order cannot be different from its queue identity")
    session=session_from_original_evidence(
        sequence,
        env["VIDEO001_SOURCE_PAGE"],read(env["VIDEO001_SOURCE_SUMMARY"]),
        read(env["VIDEO001_SOURCE_PROOF"]),int(env["GITHUB_RUN_ID"]),
        env["VIDEO001_QUEUE_ID"])
    response=record_session(session,env["GH_TOKEN"])
    print("VIDEO001_SOURCE_SESSION_REGISTERED="+json.dumps({
        "session_id":session["session_id"],"queue_id":session["source_queue_id"],
        "sha256":session["source_sha256"],"original_chunks":session["chunks_5min"],
        "source_verified":True,"semantic_rules_verified":0,
        "git_commit":response
    }),flush=True)

if __name__=="__main__":main()
