#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VIDEO-001 magazine isolation: one named project, ordered user inputs, private receipts.

This module is pure validation / queue ordering. Creating a manifest or entry
requires an explicit user-supplied magazine name, media URL and submission.
Cross-magazine source/meaning links are forbidden by construction.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

MID = re.compile(r"[a-z][a-z0-9-]{2,50}\Z")
QID = re.compile(r"video-q-([0-9]{4})-[a-z0-9-]{4,64}\Z")
SRC = re.compile(r"/p/[A-Za-z0-9_-]{3,80}/?\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
SCHEMA = "video001_magazine_v1"
ENTRY_SCHEMA = "video001_magazine_user_entry_v1"
RECEIPT_OK = "COMPLETE_SOURCE_VERIFIED_SEMANTIC_REVIEW_REQUIRED"
RECEIPT_FAILED = "FAILED_NEEDS_REVIEW"
ARTIN_MAGAZINE = "artin-course-001"
ARTIN_COURSE = "tools-makhzan/courses/artin/COURSE_REGISTRY.json"

def _need(cond, text):
    if not cond:
        raise ValueError(text)

def source_url(url):
    _need(isinstance(url,str),"Video URL must be user supplied")
    p=urlsplit(url)
    _need(p.scheme=="https" and p.hostname=="my.uupload.ir" and
          bool(SRC.fullmatch(p.path)) and not p.username and not p.password and
          not p.query and not p.fragment and not p.port,
          "Only exact user-supplied Uupload HTTPS share pages are supported")
    return url

def validate_manifest(doc, dirname):
    _need(isinstance(doc,dict) and doc.get("schema")==SCHEMA,"Invalid magazine schema")
    mid=doc.get("magazine_id")
    _need(isinstance(mid,str) and bool(MID.fullmatch(mid)) and mid==dirname,
          "Invalid, untrusted or mismatched magazine ID")
    title=doc.get("title_fa")
    _need(isinstance(title,str) and 1<=len(title.strip())<=120,
          "Each magazine requires its own visible title")
    _need(doc.get("submitted_by_user") is True,"Never create a new magazine without user intent")
    mode=doc.get("session_mode")
    _need(mode in ("serial","single"),"Use one-film or sequential magazine")
    sequence=doc.get("start_sequence")
    _need(type(sequence) is int and 1<=sequence<=9999,"Invalid starting film number")
    target=doc.get("target_course_registry")
    _need(target is None or (mid==ARTIN_MAGAZINE and target==ARTIN_COURSE),
          "Do not attach an unrelated magazine to the teacher course")
    _need((mid!=ARTIN_MAGAZINE) or (mode=="serial" and sequence==3 and target==ARTIN_COURSE),
          "Artin magazine must follow already submitted lessons 1 and 2")
    if mode=="single":_need(sequence==1,"Standalone film starts at slot one")
    return mid

def validate_entry(doc,path,mid):
    _need(isinstance(doc,dict) and doc.get("schema")==ENTRY_SCHEMA,"Invalid queued film schema")
    _need(doc.get("magazine_id")==mid,"Cross-magazine film contamination forbidden")
    qid=doc.get("queue_id")
    match=QID.fullmatch(qid) if isinstance(qid,str) else None
    _need(match is not None and path.stem==qid,"Queue ID/filename mismatch")
    n=int(match.group(1))
    _need(doc.get("sequence")==n,"Film slot does not match queue ID")
    _need(doc.get("submitted_by_user") is True and doc.get("status")=="PENDING_USER_AUTHORIZED",
          "No implicit, invented or unapproved queued movies")
    url=source_url(doc.get("source_page"))
    expected=doc.get("expected_sha256")
    _need(expected is None or (isinstance(expected,str) and bool(SHA.fullmatch(expected))),
          "Incorrect or invented original file hash")
    label=doc.get("video_name_fa")
    _need(isinstance(label,str) and 1<=len(label.strip())<=160,
          "Each film needs its own distinguishable title")
    return n,{"magazine_id":mid,"queue_id":qid,"source_page":url,
              "expected_sha256":expected or "", "sequence":n}

def read_magazine(folder):
    root=Path(folder)
    manifest_path=root/"MANIFEST.json"
    _need(manifest_path.is_file(),"Magazine is missing its permanent manifest")
    manifest=json.loads(manifest_path.read_text(encoding="utf8"))
    mid=validate_manifest(manifest,root.name)
    rows=[];pages=set();positions=set()
    for path in sorted((root/"entries").glob("video-q-*.json")):
        seq,item=validate_entry(json.loads(path.read_text(encoding="utf8")),path,mid)
        _need(seq>=manifest["start_sequence"],"Queued film would overwrite earlier submitted session")
        _need(seq not in positions,"A magazine cannot contain two films at one position")
        _need(item["source_page"] not in pages,"A magazine cannot contain duplicate film links")
        positions.add(seq);pages.add(item["source_page"])
        rows.append((seq,item))
    rows.sort(key=lambda pair:pair[0])
    if manifest["session_mode"]=="single":
        _need(len(rows)<=1,"Standalone magazine may only contain one film")
    if rows:
        expected=list(range(manifest["start_sequence"],rows[-1][0]+1))
        _need([r[0] for r in rows]==expected,
              "Refusing to skip a missing user-submitted film in serialized magazine")
    outstanding=[]
    failed=False
    for seq,item in rows:
        receipt=root/"receipts"/(item["queue_id"]+".json")
        if not receipt.is_file():
            _need(not failed,"An earlier failed film blocked this serial magazine")
            outstanding.append(item)
            continue
        saved=json.loads(receipt.read_text(encoding="utf8"))
        _need(saved.get("magazine_id")==mid and
              saved.get("queue_id")==item["queue_id"] and
              saved.get("source_page")==item["source_page"],
              "A receipt from another magazine or video was encountered")
        status=saved.get("status")
        if status==RECEIPT_FAILED:
            failed=True
        elif status=="MACHINE_TEXT_ARCHIVED_UNVERIFIED":
            # Explicit user-authorized stage boundary: technical texts may
            # proceed to NEXT film without pretending teacher meaning is proved.
            # Every raw channel (speech, chat, board) must have source-backed,
            # SHA-verified text. This NEVER constitutes an executable rule.
            p=saved.get("source_evidence")
            _need(isinstance(p,dict) and p.get("all_raw_text_sha256_verified") is True
                  and p.get("source_video_sha256") and bool(SHA.fullmatch(p["source_video_sha256"]))
                  and isinstance(p.get("audio_parts"),int) and p["audio_parts"]>0
                  and isinstance(p.get("chat_ocr_source_frames"),int) and p["chat_ocr_source_frames"]>0
                  and isinstance(p.get("board_ocr_source_frames"),int) and p["board_ocr_source_frames"]>0
                  and p.get("raw_archive_sha256") and bool(SHA.fullmatch(p["raw_archive_sha256"]))
                  and saved.get("human_semantics_verified") is False
                  and saved.get("trading_permitted") is False
                  and saved.get("archive_private_library_path")=="/بهروز/بهروز.zip",
                  "Invalid evidence for raw machine text; cannot advance magazine")
        else:
            _need(status==RECEIPT_OK and saved.get("source_evidence") is not None,
                  "No verified receipt for queued source")
    _need(not failed,
          "One film failed: do not silently skip ahead to next film or mark source successful")
    return outstanding

def enumerate_magazines(root):
    root=Path(root)
    magazines=root/"magazines"
    if not magazines.exists():return []
    rows=[];names=set()
    for folder in sorted(magazines.iterdir()):
        if not folder.is_dir():continue
        _need(folder.name not in names,"Duplicate magazine identifier")
        names.add(folder.name)
        rows.extend(read_magazine(folder))
    return rows
