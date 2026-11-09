#!/usr/bin/env python3
"""ARTIN VIDEO 20: evidence-only recovery on a GitHub runner.
No teacher rule certification or trading. Preserve original ZIP payload bytes.
"""
from __future__ import annotations
import bisect
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT=Path("artin20_recovery")
RAW=ROOT/"original_downloads"
OUT=ROOT/"private_results"
RUN=42620094527
REPO="aminzare121-maker/amin-faraz"
ARTIFACTS={
    "text":13677326457,
    "temporal":13676457226,
    "chat_index":13676872132,
    "board":13676801616,
    "board_ocr":13675289012,
    "source_summary":13676411887,
    "proof":13677326507
}
IMGEXT={".png",".jpg",".jpeg",".webp",".bmp"}
TEXT_KEYS=("text","transcript","recognized_text","asr_text","ocr_text","recognized","utterance","content","raw_text")
TIME_START=("start_s","start_seconds","start_sec","start_time","start","timestamp_seconds","frame_second","timestamp","time_s","second","time")
TIME_END=("end_s","end_seconds","end_sec","end_time","end")

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def download(name,artifact_id):
    RAW.mkdir(parents=True,exist_ok=True)
    path=RAW/f"{name}.zip"
    if path.exists() and zipfile.is_zipfile(path):return path
    with path.open("wb") as fd:
        p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],stdout=fd,stderr=subprocess.PIPE,timeout=600)
    if p.returncode:
        raise RuntimeError("GITHUB_ARTIFACT_DOWNLOAD_FAILURE_"+name+":"+p.stderr.decode("utf8","replace")[:200])
    if not zipfile.is_zipfile(path):raise RuntimeError("INVALID_ZIP_"+name)
    return path

def iterate(archive:zipfile.ZipFile,prefix:str,level=0):
    if level>3:raise ValueError("NESTED_ARCHIVE_DEPTH")
    for item in archive.infolist():
        if item.is_dir():continue
        if item.file_size>400*1024*1024:
            yield {"path":prefix+item.filename,"size":item.file_size,"skipped":"OVER_PER_MEMBER_LIMIT"}
            continue
        data=archive.read(item)
        record={"path":prefix+item.filename,"size":len(data),"sha256":sha(data),"data":data}
        yield record
        if item.filename.lower().endswith(".zip") and len(data)<100*1024*1024:
            with zipfile.ZipFile(io.BytesIO(data)) as nested:
                if nested.testzip() is not None:raise RuntimeError("BAD_NESTED_ARCHIVE_CRC")
                yield from iterate(nested,prefix+item.filename+"!/",level+1)

def described(obj):
    if isinstance(obj,dict):
        result={"kind":"dict","keys":list(obj)[:45]}
        for key,value in obj.items():
            if isinstance(value,list) and value:
                first=value[0]
                result["sample_list_"+key]= {"len":len(value),"first_keys":list(first.keys())[:30] if isinstance(first,dict) else type(first).__name__}
            if len(json.dumps(result))>1800:break
        return result
    if isinstance(obj,list):
        return {"kind":"list","count":len(obj),"first_keys":list(obj[0])[:30] if obj and isinstance(obj[0],dict) else []}
    return {"kind":type(obj).__name__}

def firstval(d,keys):
    for k in keys:
        v=d.get(k)
        if v is None:continue
        if isinstance(v,(str,int,float)) and not isinstance(v,bool):
            return v,k
    return None,None

def seconds(v):
    if isinstance(v,(int,float)) and not isinstance(v,bool):return float(v)
    if not isinstance(v,str):return None
    v=v.strip()
    try:return float(v)
    except ValueError:pass
    if re.fullmatch(r"\d{1,2}:\d\d(?::\d\d(?:\.\d+)?)?",v):
        a=[float(x) for x in v.split(":")]
        if len(a)==3:return a[0]*3600+a[1]*60+a[2]
        return a[0]*60+a[1]
    return None

def iterate_text_rows(obj,base_path,category,max_depth=12):
    seq=[(obj,"",0)]
    seen=0
    while seq:
        cur,loc,depth=seq.pop()
        if depth>max_depth:continue
        if isinstance(cur,list):
            for i,x in enumerate(cur):
                if isinstance(x,(dict,list)):seq.append((x,loc+"/"+str(i),depth+1))
            continue
        if not isinstance(cur,dict):continue
        v,k=firstval(cur,TEXT_KEYS)
        if v is not None and isinstance(v,str) and len(v.strip())>2 and len(v)<20000:
            t,tk=firstval(cur,TIME_START)
            u,uk=firstval(cur,TIME_END)
            t=seconds(t);u=seconds(u)
            if t is None:
                for nested_time in ("timing","time","segment","metadata"):
                    if isinstance(cur.get(nested_time),dict):
                        tv,tt=firstval(cur[nested_time],TIME_START)
                        t=seconds(tv)
                        if t is not None:tk=nested_time+"."+str(tt);break
            seen+=1
            yield {
                "source_file":base_path,
                "source_json_path":loc,
                "category":category,
                "text":v,
                "time_start":t,
                "time_end":u,
                "time_key":tk,
                "end_key":uk,
                "timestamp_basis":"UNVERIFIED_GLOBAL_CLOCK",
                "teacher_role":"UNVERIFIED",
                "semantic_verification":False
            }
        for key,value in cur.items():
            if isinstance(value,(list,dict)):
                seq.append((value,loc+"/"+str(key),depth+1))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    summary={"schema":"artin20_isolated_source_recovery_v1","queue_sequence":20,
             "video_name":"فیلم ۱۸ در خشاب، ردیف ۲۰",
             "github_original_run":RUN,"original_source_mutated":False,
             "teacher_semantic_verified":False,"rules_ready_for_mt5":0,
             "source_archives":[],"content_inventory":[],"speech_records":0,
             "chat_ocr_records":0,"board_ocr_records":0,"image_files":0,
             "temporal_matches":0,"unmatched_speech":0}
    all_rows={"speech":[],"student_chat":[],"board":[]}
    try:
        for name,artifact_id in ARTIFACTS.items():
            path=download(name,artifact_id)
            with zipfile.ZipFile(path) as z:
                if z.testzip() is not None:raise ValueError("ARTIFACT_ZIP_CRC_FAILURE_"+name)
                summary["source_archives"].append({"category":name,"artifact_id":artifact_id,
                    "download_bytes":path.stat().st_size,"zip_sha256":sha(path.read_bytes()),"members":len(z.infolist())})
                for item in iterate(z,name+"/"):
                    if "skipped" in item:
                        summary["content_inventory"].append({k:v for k,v in item.items() if k!="data"})
                        continue
                    src=item["path"];suffix=Path(src).suffix.lower()
                    if suffix in IMGEXT:
                        summary["image_files"]+=1
                        if summary["image_files"]<=5:
                            summary.setdefault("image_examples",[]).append(src)
                        continue
                    if suffix not in (".json",".jsonl",".srt",".vtt",".txt"):
                        continue
                    content=item["data"]
                    if len(content)>60*1024*1024:continue
                    if suffix not in (".json",".jsonl"):continue
                    try:
                        if suffix==".json":
                            doc=json.loads(content)
                        else:
                            doc=[json.loads(s) for s in content.splitlines() if s.strip()]
                    except (UnicodeError,json.JSONDecodeError):
                        continue
                    category=("speech" if "/speech_asr_raw/" in "/"+src or "/asr" in "/"+src
                              else ("board" if "/board_ocr_raw/" in "/"+src or "board_ocr" in src
                                    else ("student_chat" if "/student_chat_ocr_raw/" in "/"+src or "/ocr" in src else "misc")))
                    summary["content_inventory"].append({"file":src,"size":len(content),"sha256":sha(content),
                                                         "category":category,"schema":described(doc)})
                    # Use the canonical merged transcript once. Individual ASR shard
                    # rows include overlap and must not be double-counted.
                    if ("/verified_export_and_review_text_only/ASR_REVIEW_UNVERIFIED.json" in src
                        and isinstance(doc,dict)):
                        for rec in doc.get("speech_lines",[]):
                            if not isinstance(rec,dict):continue
                            t=seconds(rec.get("start"));e=seconds(rec.get("end"))
                            all_rows["speech"].append({
                                "source_file":src,"source_id":rec.get("id"),
                                "source_audio_sha256":rec.get("source_audio_sha256"),
                                "category":"speech","text":rec.get("text",""),
                                "time_start":t,"time_end":e,
                                "timestamp_basis":"SOURCE_MERGED_REVIEW_CLOCK",
                                "speaker_role":rec.get("speaker","UNKNOWN"),
                                "speaker_verified":rec.get("speaker_verified",False),
                                "semantic_verification":False})
                    # Original student-chat machine OCR: each result is one
                    # time-indexed frame, even if its OCR text is empty.
                    elif ("/student_chat_ocr_raw/worker-" in src
                          and src.endswith("/full_chat_ocr_candidates_PRIVATE.json")
                          and isinstance(doc,dict)):
                        for rec in doc.get("results",[]):
                            if not isinstance(rec,dict):continue
                            all_rows["student_chat"].append({
                                "source_file":src,"source_id":rec.get("frame_id"),
                                "source_frame_sha256":rec.get("source_frame_sha256"),
                                "category":"student_chat",
                                "text":rec.get("text_lines",[]),
                                "possible_typed_questions":rec.get("possible_typed_questions",[]),
                                "time_start":seconds(rec.get("time_original_video_seconds")),
                                "time_end":None,
                                "timestamp_basis":"ORIGINAL_VIDEO_SECONDS",
                                "speaker_role":"UNKNOWN",
                                "teacher_answer_verified":False,"semantic_verification":False})
                    # Original teacher-board machine OCR; preserve raw OCR field.
                    elif ("/board_ocr_raw/board_ocr_candidates_PRIVATE.json" in src
                          and isinstance(doc,dict)):
                        for rec in doc.get("results",[]):
                            if not isinstance(rec,dict):continue
                            all_rows["board"].append({
                                "source_file":src,"source_id":rec.get("frame_id"),
                                "source_frame_sha256":rec.get("source_frame_sha256"),
                                "category":"board",
                                "text":rec.get("machine_text_raw",""),
                                "time_start":seconds(rec.get("time_original_video_seconds")),
                                "time_end":None,
                                "timestamp_basis":"ORIGINAL_VIDEO_SECONDS",
                                "speaker_role":"UNKNOWN",
                                "teacher_rule_verified":False,"semantic_verification":False})
        diagnostic={}
        for item in summary["content_inventory"]:
            cat=item.get("category","no_category")
            if cat not in diagnostic:diagnostic[cat]={"count":0,"samples":[]}
            diagnostic[cat]["count"]+=1
            if len(diagnostic[cat]["samples"])<7:
                diagnostic[cat]["samples"].append({"file":item.get("file",""),"schema":item.get("schema",{})})
        print("ARTIN20_SCHEMA_DIAGNOSTIC="+json.dumps(diagnostic,ensure_ascii=False),flush=True)
        # Avoid claiming time alignment unless clocks are explicitly usable:
        # match only by numeric time, never infer that words describe the image.
        speech=all_rows["speech"];visual=all_rows["board"]+all_rows["student_chat"]
        summary["speech_records"]=len(speech)
        summary["board_ocr_records"]=len(all_rows["board"])
        summary["chat_ocr_records"]=len(all_rows["student_chat"])
        timed_visual=sorted((r["time_start"],i) for i,r in enumerate(visual) if r["time_start"] is not None)
        timestamps=[x[0] for x in timed_visual]
        OUT.joinpath("speech_source_rows_UNVERIFIED.jsonl").write_text(
            "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in speech),encoding="utf8")
        OUT.joinpath("visual_source_rows_UNVERIFIED.jsonl").write_text(
            "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in visual),encoding="utf8")
        summary["exact_interval_matches"]=0
        summary["nearby_only_matches"]=0
        with OUT.joinpath("temporal_candidates_NOT_SEMANTIC.jsonl").open("w",encoding="utf8") as o:
            for i,r in enumerate(speech):
                hits=[]
                t=r["time_start"];end=r["time_end"]
                if t is not None:
                    if end is not None and end>=t:
                        a=bisect.bisect_left(timestamps,t)
                        b=bisect.bisect_right(timestamps,end)
                        for j in range(a,min(b,a+10)):
                            hits.append({"visual_index":timed_visual[j][1],
                                         "delta_seconds":0.0,
                                         "relation":"WITHIN_SPEECH_INTERVAL"})
                    if not hits:
                        pos=bisect.bisect_left(timestamps,t)
                        for j in range(max(pos-4,0),min(pos+5,len(timestamps))):
                            delta=abs(timed_visual[j][0]-t)
                            if delta<=6:
                                hits.append({"visual_index":timed_visual[j][1],
                                             "delta_seconds":round(delta,3),
                                             "relation":"NEAR_START_WITHIN_6_SECONDS"})
                hits=sorted(hits,key=lambda h:h["delta_seconds"])[:5]
                if hits:
                    summary["temporal_matches"]+=1
                    if hits[0]["relation"]=="WITHIN_SPEECH_INTERVAL":
                        summary["exact_interval_matches"]+=1
                    else:summary["nearby_only_matches"]+=1
                else:summary["unmatched_speech"]+=1
                o.write(json.dumps({"speech_index":i,"speech_time_start":t,
                  "speech_time_end":end,"visual_candidates":hits,
                  "time_only_not_semantic":True,"speaker_role_unverified":True},ensure_ascii=False)+"\n")
        summary["status"]=("SOURCE_EXTRACTED_AND_TEMPORAL_CANDIDATES_CREATED"
                            if speech and visual else "SOURCE_ARCHIVED_BUT_REQUIRED_ROWS_UNAVAILABLE")
        if not speech or not visual:summary["blocker"]="NO_MACHINE_SPEECH_OR_VISUAL_TEXT_ROWS_FOUND; inspect schema details."
        OUT.joinpath("content_inventory.json").write_text(json.dumps(summary["content_inventory"],ensure_ascii=False,indent=2),encoding="utf8")
    except Exception as exc:
        summary["status"]="RECOVERY_FAILED"
        summary["error_type"]=type(exc).__name__
        summary["error_message"]=str(exc)[:300]
        raise
    finally:
        OUT.joinpath("summary.json").write_text(json.dumps({k:v for k,v in summary.items() if k!="content_inventory"},ensure_ascii=False,indent=2),encoding="utf8")
        print("ARTIN20_SOURCE_EXTRACTION_REPORT="+json.dumps({
          k:v for k,v in summary.items() if k in ("status","source_archives","speech_records",
          "chat_ocr_records","board_ocr_records","image_files","temporal_matches","exact_interval_matches","nearby_only_matches","unmatched_speech","blocker")
        },ensure_ascii=False),flush=True)
    if not speech or not visual:sys.exit(2)

if __name__=="__main__":main()
