#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Actions execution gateway for tools-makhzan/REGISTRY.json.

Only allowlisted actions: status, build_review, source_ingest.
This is an ACTUAL GitHub tool entrypoint: an assistant can update the
private tools-makhzan/requests/current.json to execute a job remotely.

Never claim assistant can refresh GitHub auth or infer teacher rules.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

REPO="aminzare121-maker/amin-faraz"
SOURCE="TEACHER_J2_2026_11_07"
ACTIONS={"status","build_review","source_ingest","course_status"}
ROOT=Path(__file__).resolve().parent.parent
REQUEST=ROOT/"tools-makhzan"/"requests"/"current.json"
REGISTRY=ROOT/"tools-makhzan"/"REGISTRY.json"


def validate(request,registry):
    if request.get("schema")!="makhzan_tool_execution_request_v1":
        raise ValueError("Invalid tool invocation schema")
    if request.get("tool_id")!="VIDEO-001":
        raise ValueError("Unknown/unsupported tool ID")
    action=request.get("action")
    if action not in ACTIONS:raise ValueError("Action not allowlisted")
    job=request.get("job_id")
    if not isinstance(job,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,70}",job):
        raise ValueError("Unsafe job request ID")
    extra=set(request)-{"schema","tool_id","action","job_id","source_id",
                       "source_url","expected_sha256","ingest_mode"}
    if extra:raise ValueError("Unapproved request keys: "+str(sorted(extra)))
    if registry.get("schema")!="makhzan_tools_registry_v1" or registry.get("hub_ref")!="tools-makhzan-hub":
        raise ValueError("Canonical tool registry missing")
    tool=next((x for x in registry.get("tools",[]) if x.get("id")=="VIDEO-001"),None)
    if tool is None:raise ValueError("VIDEO-001 not registered")
    code=tool.get("code",{})
    if code.get("repository")!=REPO or code.get("ref")!="review/artin-fidelity-audit-v7-20261107":
        raise ValueError("Unrecognized code source version; requires reviewed hub upgrade")
    if action!="source_ingest":
        if request.get("source_id")!=SOURCE:
            raise ValueError("Must use an explicitly registered source ID")
        if any(k in request for k in ("source_url","expected_sha256","ingest_mode")):
            raise ValueError("Source link cannot be changed for existing source job")
    else:
        url=request.get("source_url")
        from urllib.parse import urlsplit
        if not isinstance(url,str) or len(url)>300:raise ValueError("Missing user supplied video source")
        u=urlsplit(url)
        if (u.scheme!="https" or u.hostname!="my.uupload.ir" or
            not re.fullmatch(r"/p/[A-Za-z0-9_-]{3,80}/?",u.path) or
            u.username or u.password or u.query or u.fragment):
            raise ValueError("Only explicit https my.uupload.ir user share pages")
        # Deliberately no new-source trading tasks.
        if request.get("ingest_mode") not in ("SOURCE_AND_FAST_AUDIO","SOURCE_AUDIO_AND_CHAT"):
            raise ValueError("Source mode is not evidence-only")
        h=request.get("expected_sha256")
        if h is not None and not re.fullmatch("[a-f0-9]{64}",str(h)):
            raise ValueError("Malformed original source SHA")
    return action


def api_get(path,token):
    import urllib.parse
    if not path.startswith(f"/repos/{REPO}/"):
        raise ValueError("Disallowed API path")
    url="https://api.github.com"+path
    headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"Artin-Makhzan-Private-Executor"}
    with urlopen(Request(url,headers=headers),timeout=24) as r:
        return json.load(r)


def status(registry,request,out):
    token=os.environ.get("GH_TOKEN","")
    if not token:raise ValueError("GitHub token unavailable in the workflow environment")
    tool=next(x for x in registry["tools"] if x["id"]=="VIDEO-001")
    refs=[("full_audio_17_parts",42382408395),
          ("source_image_ocr_161",42391720989),
          ("student_question_audio_join",42393181420),
          ("source_image_ocr_276",42395611419),
          ("mobile_review_delivery",42396381577)]
    runs=[]
    for label,run_id in refs:
        info=api_get(f"/repos/{REPO}/actions/runs/{run_id}",token)
        runs.append({"label":label,"run_id":run_id,"status":info.get("status"),
                     "conclusion":info.get("conclusion"),
                     "url":info.get("html_url"),"head_sha":info.get("head_sha")})
    pr=api_get(f"/repos/{REPO}/pulls/54",token)
    result={"schema":"makhzan_VIDEO-001_execution_status_v1",
       "execution_job_id":request["job_id"],"tool_id":"VIDEO-001",
       "registry_branch":registry["hub_ref"],
       "code_ref":tool["code"]["ref"],
       "pull_request":{"number":54,"state":pr.get("state"),"draft":pr.get("draft"),
                       "merged":pr.get("merged",False)},
       "original_video_source_sha256":tool["known_sources"][0]["sha256"],
       "source_run_results":runs,
       "original_video_technical_evidence_verified":all(x["conclusion"]=="success" for x in runs),
       "teacher_meaning_verified":False,
       "trading_rules_approved":0,
       "can_execute_trading":False,
       "state":"OPERATIONAL_GITHUB_EXECUTOR_NOT_AUTONOMOUS_TEACHER_STRATEGY"}
    out.mkdir(parents=True,exist_ok=True)
    (out/"status.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    print("MAKHZAN_EXECUTOR_STATUS="+json.dumps({"job_id":request["job_id"],
      "tool_id":"VIDEO-001","runs":len(runs),
      "all_evidence_jobs_succeeded":result["original_video_technical_evidence_verified"],
      "teacher_rules_verified":0},ensure_ascii=False),flush=True)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--validate",action="store_true")
    p.add_argument("--execute-status",action="store_true")
    p.add_argument("--execute-course",action="store_true")
    p.add_argument("--emit-job",action="store_true")
    p.add_argument("--out",type=Path,default=Path("/tmp/makhzan_exec"))
    p.add_argument("--github-output",type=Path)
    a=p.parse_args()
    req=json.loads(REQUEST.read_text(encoding="utf8"))
    reg=json.loads(REGISTRY.read_text(encoding="utf8"))
    action=validate(req,reg)
    if a.github_output:
        with a.github_output.open("a",encoding="utf8") as f:
            f.write("action="+action+"\n")
            f.write("job_id="+req["job_id"]+"\n")
    if a.emit_job:
        if action!="source_ingest":raise ValueError("Only source_ingest emits new job")
        job={"schema":"artin_private_video_job_v6",
             "job_id":req["job_id"],
             "source_url":req["source_url"],
             "mode":req["ingest_mode"]}
        if req.get("expected_sha256"):job["expected_sha256"]=req["expected_sha256"]
        a.out.mkdir(parents=True,exist_ok=True)
        (a.out/"ingest_request.json").write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding="utf8")
    if a.execute_status:
        if action!="status":raise ValueError("Only status action permitted")
        status(reg,req,a.out)
    if a.execute_course:
        if action!="course_status":raise ValueError("Only course_status can inspect the course puzzle")
        from course_stitcher import course_puzzle,hydrate_persistent_anchors
        course=json.loads((ROOT/"tools-makhzan"/"courses"/"artin"/"COURSE_REGISTRY.json").read_text(encoding="utf8"))
        course=hydrate_persistent_anchors(course,ROOT)
        report=course_puzzle(course)
        a.out.mkdir(parents=True,exist_ok=True)
        (a.out/"course_puzzle_status.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        print("MAKHZAN_COURSE_TOOL_EXECUTED="+json.dumps({
            "course_id":report["course_id"],
            "registered_source_videos":report["registered_user_submitted_sessions"],
            "persisted_original_evidence_anchors":report["registered_original_source_evidence"],
            "next_video_status":report["current_status"],
            "cross_session_links":report["linked_cross_session_evidence_count"],
            "rules_ready":report["ready_to_issue_teacher_rules"],
            "fake_source_count":0},ensure_ascii=False),flush=True)
    if a.validate:
        print("MAKHZAN_EXECUTOR_REQUEST_VALIDATED="+json.dumps({"tool_id":req["tool_id"],"action":action,
             "job_id":req["job_id"],"registry_ref":reg["hub_ref"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
