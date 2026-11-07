#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one immutable ordered batch from all *user-submitted* queued VIDEO-001 films.

A fresh push may coalesce GitHub pending runs, but this scheduler scans the
entire latest GitHub branch and ignores existing evidence-verified receipts.
Nothing is marked complete without the separate final full-film QA receipt.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from magazines import enumerate_magazines

ID=re.compile(r"video-q-([0-9]{4})-[a-z0-9-]{4,64}")
SHARE=re.compile(r"/p/[A-Za-z0-9_-]{3,80}/?")

def validate_entry(item,path):
    if item.get("schema")!="makhzan_video001_user_queue_entry_v1":
        raise ValueError("Queue entry schema invalid: "+path.name)
    ident=item.get("queue_id")
    match=ID.fullmatch(ident) if isinstance(ident,str) else None
    if not match or path.stem!=ident:
        raise ValueError("Queue entry identity mismatch: "+path.name)
    if item.get("submitted_by_user") is not True or item.get("status")!="PENDING_USER_AUTHORIZED":
        raise ValueError("Only an explicit user-submitted pending video may be queued")
    url=item.get("source_page")
    if not isinstance(url,str):
        raise ValueError("Missing original submitted share URL")
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname!="my.uupload.ir" or not SHARE.fullmatch(p.path) or p.username or p.password or p.query or p.fragment:
        raise ValueError("Only original user-supplied HTTPS Uupload share pages are allowed")
    sha=item.get("expected_sha256")
    if sha is not None and (not isinstance(sha,str) or not re.fullmatch(r"[a-f0-9]{64}",sha)):
        raise ValueError("No fabricated or malformed source hash allowed")
    return int(match.group(1)),{"queue_id":ident,"source_page":url,"expected_sha256":sha or ""}

def enumerate_queue(root):
    root=Path(root)
    entries=root/"entries"
    receipts=root/"receipts"
    rows=[]; seen_pages=set();seen_order=set()
    for path in sorted(entries.glob("video-q-*.json")):
        seq,item=validate_entry(json.loads(path.read_text(encoding="utf8")),path)
        if seq<3:
            raise ValueError("Queue sequence 1 and 2 are reserved for already submitted lessons")
        if seq in seen_order:raise ValueError("Two queued movies share a session position")
        seen_order.add(seq)
        if item["source_page"] in seen_pages:raise ValueError("Duplicate submitted film URL in queue")
        seen_pages.add(item["source_page"])
        receipt=receipts/(item["queue_id"]+".json")
        if receipt.exists():
            saved=json.loads(receipt.read_text(encoding="utf8"))
            if saved.get("queue_id")!=item["queue_id"] or saved.get("source_page")!=item["source_page"]:
                raise ValueError("Inconsistent queue receipt; refuse processing")
            if saved.get("status") not in ("COMPLETE_SOURCE_VERIFIED_SEMANTIC_REVIEW_REQUIRED","FAILED_NEEDS_REVIEW"):
                raise ValueError("Unknown queue receipt status; refuse processing")
            continue
        rows.append((seq,item))
    rows.sort(key=lambda pair:pair[0])
    return [item for _,item in rows]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("tools-makhzan/video_queue"))
    p.add_argument("--github-output",type=Path)
    args=p.parse_args()
    # New named-magazine queue is the canonical path; keep the old flat queue
    # validator available for migration tests, but never merge arbitrary films.
    items=enumerate_magazines(args.root)
    matrix={"include":items}
    if args.github_output:
        with args.github_output.open("a",encoding="utf8") as out:
            out.write("items="+json.dumps(matrix,separators=(',',':'))+"\n")
            out.write("count="+str(len(items))+"\n")
    print("VIDEO001_USER_SUBMITTED_SERIAL_QUEUE="+json.dumps({
        "pending":len(items),"queue_ids":[x["queue_id"] for x in items],
        "source_content_claims":"NONE",
        "independent_source_sha_required":True,
        "sequential_in_full_movie_order":True,
        "magazines":sorted(set(x["magazine_id"] for x in items)),
        "no_cross_magazine_evidence_links":True},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
