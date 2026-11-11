#!/usr/bin/env python3
"""Fail-closed adapter for timestamped Artin evidence; no semantic or trading approval."""
import argparse, hashlib, json
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def adapt(manifest,root):
    if manifest.get("entry")!="0010" or manifest.get("course")!="artin-course-001":
        raise ValueError("Unexpected course/entry")
    sources=manifest.get("sources")
    if not isinstance(sources,dict) or not all(k in sources for k in ("speech","chat","board","frames")):
        raise ValueError("All four original evidence streams required")
    records={}
    for kind,entry in sources.items():
        relative=entry["path"]
        p=(root/relative).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file():raise ValueError("Missing/unsafe source: "+kind)
        if digest(p)!=entry["sha256"]:raise ValueError("SHA256 mismatch: "+kind)
        records[kind]=json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(records[kind],list):raise ValueError("Expected timestamped list: "+kind)
        for item in records[kind]:
            if not isinstance(item,dict) or not isinstance(item.get("start"),(int,float)) or item["start"]<0:
                raise ValueError("Invalid time: "+kind)
    speech=[{"start":x["start"],"end":x.get("end",x["start"]),"text":x.get("text","")} for x in records["speech"]]
    if not speech:raise ValueError("Empty speech evidence")
    # OCR is evidence, not independently verified student questions or teacher decisions.
    return {"session_id":"artin-course-001-0010","speech":speech,"questions":[],
            "evidence_streams":{k:{"sha256":sources[k]["sha256"],"path":sources[k]["path"],"count":len(records[k])} for k in sources},
            "unverified_ocr":{"chat":records["chat"],"board":records["board"]},
            "frame_index":records["frames"],"teacher_semantics_verified":False,
            "verified_executable_rules":[],"status":"AWAITING_INDEPENDENT_SEMANTIC_REVIEW"}

def main():
    p=argparse.ArgumentParser();p.add_argument("manifest");p.add_argument("root");p.add_argument("output");a=p.parse_args()
    manifest=json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    session=adapt(manifest,Path(a.root))
    Path(a.output).write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__":main()
