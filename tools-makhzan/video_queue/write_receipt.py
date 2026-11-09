#!/usr/bin/env python3
"""Record VIDEO-001 queued movie outcome from real GitHub Actions evidence.

Never label a source complete based only on ASR/OCR worker success.
A successful receipt requires the full original-source independent verification,
private legacy V12 export artifact, source SHA and zero loss.
"""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT="https://api.github.com"
VALID_ID=re.compile(r"video-q-[0-9]{4}-[a-z0-9-]{4,64}")
MAGAZINE_ID=re.compile(r"[a-z][a-z0-9-]{2,50}")
EXPECTED_SHA=re.compile(r"[a-f0-9]{64}")
PROOF_ARTIFACT="makhzan-VIDEO-001-V12-FAST-complete-source-PRIVATE"

def load(path):
    return json.loads(Path(path).read_text(encoding="utf8"))

def get_evidence(base,success):
    if not success:
        return None
    evidence=load(Path(base)/"proof"/"private_fast_verify_summary.json")
    source=load(Path(base)/"source"/"safe_source_prep_summary.json")
    sha=evidence.get("original_source_video_sha256")
    assert isinstance(sha,str) and EXPECTED_SHA.fullmatch(sha), "No valid source SHA"
    assert sha==source.get("source_video_sha256"),"Source identity mismatch"
    assert evidence.get("source_evidence_loss")==0,"Loss of original evidence"
    assert evidence.get("independent_hash_and_time_evidence_complete") is True
    assert source.get("source_integrity_verified") is True
    assert source.get("all_original_audio_parts_assigned_once") is True
    assert source.get("all_original_chat_images_assigned_once") is True
    # New V13 path must also supply the board text-candidate coverage.
    board_summary_path=Path(base)/"board"/"board_ocr_safe_summary.json"
    if board_summary_path.exists():
        board=load(board_summary_path)
        assert board.get("schema")=="V13_BOARD_TEXT_OCR_ALL_SAMPLED_SOURCE_FRAMES_V1", "No board OCR proof"
        assert board.get("source_video_sha256")==sha, "Board source mismatch"
        assert board.get("frames_processed")==source["original_board_frames"], "Board OCR missing frames"
        assert board.get("missing_frames")==0 and board.get("human_verified") is False, "Unsafe board OCR state"

    assert evidence["original_five_minute_audio_parts"]==source["source_global_audio_chunks"]
    assert evidence["original_screen_frames_scanned"]==source["one_second_frames_scanned"]
    assert evidence["source_chat_highres_screenshots"]==source["original_chat_images_selected"]
    assert evidence["original_sampled_board_frames"]==source["original_board_frames"]
    assert evidence["source_chat_highres_screenshots"]==evidence["original_ocr_screenshots_finished"]
    assert evidence.get("teacher_semantic_accuracy_independently_verified") is False
    assert evidence.get("trading_allowed") is False
    return {"original_video_sha256":sha,
            "board_ocr_all_sampled_frames_machine_extracted":board_summary_path.exists(),
            "original_duration_seconds":source["original_duration_seconds"],
            "audio_parts":source["source_global_audio_chunks"],
            "one_second_frames_scanned":source["one_second_frames_scanned"],
            "ocr_source_images":source["original_chat_images_selected"],
            "board_frames":source["original_board_frames"],
            "provisional_qa_groups":evidence["provisional_chat_groups"],
            "teacher_meaning_verified":False,
            "original_source_evidence_loss":0}

def build_receipt(queue_id,source_page,run_id,job_results,proof_folder=None,magazine_id="artin-course-001"):
    if not isinstance(magazine_id,str) or not MAGAZINE_ID.fullmatch(magazine_id):
        raise ValueError("Unsafe or missing independent magazine ID")
    if not VALID_ID.fullmatch(queue_id):
        raise ValueError("Unsafe queue ID")
    from urllib.parse import urlsplit
    page=urlsplit(source_page)
    if page.scheme!="https" or page.hostname!="my.uupload.ir" or not re.fullmatch(r"/p/[A-Za-z0-9_-]{3,80}/?",page.path) or page.query or page.fragment or page.username or page.password:
        raise ValueError("Source URL not user-approved Uupload share page")
    success=all(v=="success" for v in job_results.values())
    evidence=get_evidence(proof_folder,success)
    data={
        "schema":"makhzan_video001_queue_receipt_v1",
        "magazine_id":magazine_id,
        "queue_id":queue_id,
        "source_page":source_page,
        "github_run_id":int(run_id),
        "github_run_url":f"https://github.com/aminzare121-maker/amin-faraz/actions/runs/{int(run_id)}",
        "job_results":job_results,
        "status":"COMPLETE_SOURCE_VERIFIED_SEMANTIC_REVIEW_REQUIRED" if success else "FAILED_NEEDS_REVIEW",
        "source_evidence":evidence,
        "failure_attempts":0 if success else 1,
        "verified_teacher_rules":0,
        "trading_permitted":False,
        "retry_policy":"SOURCE_FETCH_4_BOUNDED_ATTEMPTS; WORKER_FAILURES_NEVER_SILENTLY_SKIP",
        "note":"This receipt does not certify speech words, teaching meaning, speaker roles or executable trades."
    }
    return data

def github_put_json(path,document,repo,branch,token):
    from urllib.parse import quote
    if not repo or not token:
        raise RuntimeError("GitHub repository/token are required to persist queue receipt")
    url=ROOT+"/repos/"+repo+"/contents/"+quote(path,safe="/")
    headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28","User-Agent":"VIDEO001-verified-queue"}
    existing=None
    try:
        with urlopen(Request(url+"?ref="+branch,headers=headers),timeout=25) as response:
            existing=json.load(response)
    except HTTPError as exc:
        if exc.code!=404:raise
    encoded=base64.b64encode((json.dumps(document,ensure_ascii=False,indent=2)+"\n").encode("utf8")).decode("ascii")
    payload={"message":"VIDEO001 serial queued film receipt "+document["queue_id"],
             "content":encoded,"branch":branch}
    if existing:
        content=base64.b64decode(existing.get("content","")).decode("utf8") if existing.get("encoding")=="base64" else ""
        if content:
            prior=json.loads(content)
            if prior==document:
                return "EXISTS_IDENTICAL"
            # Only replace a failed attempt with later fully verified proof
            # for the identical magazine, queue item and original source.
            if (prior.get("status")=="FAILED_NEEDS_REVIEW"
                and document.get("status") in ("FAILED_NEEDS_REVIEW","COMPLETE_SOURCE_VERIFIED_SEMANTIC_REVIEW_REQUIRED")
                and prior.get("queue_id")==document.get("queue_id")
                and prior.get("magazine_id")==document.get("magazine_id")
                and prior.get("source_page")==document.get("source_page")
                and (document.get("source_evidence") is not None or
                     (document.get("status")=="FAILED_NEEDS_REVIEW" and
                      type(prior.get("failure_attempts",1)) is int and
                      1<=prior.get("failure_attempts",1)<3))
                and int(document.get("github_run_id",0))>int(prior.get("github_run_id",0))):
                document["failure_attempts"]=(0 if document["status"]!="FAILED_NEEDS_REVIEW"
                                              else prior.get("failure_attempts",1)+1)
                encoded=base64.b64encode((json.dumps(document,ensure_ascii=False,indent=2)+"\n").encode("utf8")).decode("ascii")
                payload["content"]=encoded
                payload["sha"]=existing["sha"]
            else:
                raise ValueError("Refusing to replace a verified or mismatched queue receipt")
        else:
            raise ValueError("Cannot verify existing queue receipt content")
    request=Request(url,method="PUT",headers={**headers,"Content-Type":"application/json"},
                    data=json.dumps(payload).encode("utf8"))
    with urlopen(request,timeout=35) as response:
        result=json.load(response)
    if not result.get("commit",{}).get("sha"):
        raise RuntimeError("GitHub did not confirm queue receipt commit")
    return result["commit"]["sha"]

def main():
    env=os.environ
    results={k:env["VIDEO001_"+k.upper()+"_RESULT"]
             for k in ("source","asr","ocr","verify")}
    if "VIDEO001_BOARD_RESULT" in env:
        results["board"]=env["VIDEO001_BOARD_RESULT"]
        if results["verify"]=="success" and results["board"]=="success" and not (Path(env.get("VIDEO001_EVIDENCE_DIR",""))/"board"/"board_ocr_safe_summary.json").is_file():
            raise ValueError("MISSING_MANDATORY_V13_BOARD_OCR_PROOF")
    receipt=build_receipt(env["VIDEO001_QUEUE_ID"],env["VIDEO001_SOURCE_PAGE"],
                          env["GITHUB_RUN_ID"],results,
                          env.get("VIDEO001_EVIDENCE_DIR"),
                          env["VIDEO001_MAGAZINE_ID"])
    repo=env["GITHUB_REPOSITORY"]
    path=("tools-makhzan/video_queue/magazines/"+receipt["magazine_id"]+
          "/receipts/"+receipt["queue_id"]+".json")
    sha=github_put_json(path,receipt,repo,"tools-makhzan-hub",env["GH_TOKEN"])
    print("VIDEO001_QUEUE_RECEIPT_COMMITTED="+json.dumps({
        "queue_id":receipt["queue_id"],"magazine_id":receipt["magazine_id"],
        "state":receipt["status"],
        "receipt_path":path,"commit":sha,
        "source_verified":receipt["source_evidence"] is not None
    }),flush=True)

if __name__=="__main__":
    main()
