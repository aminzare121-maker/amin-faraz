#!/usr/bin/env python3
"""Read original-machine-text archives for Artin course sequences 4..25.
Creates time-indexed speech/OCR candidates and provisional cross-session links.
No trades, no human/teacher semantic certification, no original modifications.
"""
import bisect, collections, hashlib, io, json, os, pathlib, re, subprocess, sys, zipfile
OUT=pathlib.Path("artin25_semantic_output")
REPO="aminzare121-maker/amin-faraz"
RUNS={
4:42581509064,5:42582773628,6:42584076860,7:42585143164,
8:42587012605,9:42589898892,10:42597293832,11:42599131963,
12:42602054376,13:42603963161,14:42605730024,15:42607235228,
16:42608711460,17:42611072346,18:42614226886,19:42618004424,
20:42620094527,21:42623860053,22:42627673993,23:42629789714,
24:42631530339,25:42633228325}
TOPICS={
"entry":["ورود","وارد","پوزیشن","معامله","خرید","فروش"],
"exit":["خروج","بستن","استاپ","حد سود","تارگت","حد ضرر"],
"risk":["ریسک","استاپ","حد ضرر","حجم","سرمایه"],
"pattern":["کندل","پیوت","پیووت","اف وی جی","fvg","پولبک","شکست","حمایت","مقاومت","روند"],
"cross_session":["جلسه قبل","جلسه قبلی","دفعه قبل","گفتم","اصلاح","اشتباه","برخلاف","استثنا"]
}
def norm(t):
    return str(t).replace("ي","ی").replace("ك","ک").replace("\u200c"," ").lower().strip()
def sha(b):return hashlib.sha256(b).hexdigest()
def sec(x):
    if isinstance(x,(float,int)) and not isinstance(x,bool):return float(x)
    if isinstance(x,str):
        try:return float(x)
        except ValueError:pass
        if re.fullmatch(r"\\d+:\\d\\d(?::\\d\\d(?:\\.\\d+)?)?",x):
            parts=[float(y) for y in x.split(":")];return sum(v*(60**i) for i,v in enumerate(parts[::-1]))
    return None
def api_json(path):
    p=subprocess.run(["gh","api",path],capture_output=True,timeout=120)
    if p.returncode:raise RuntimeError("API "+path+" "+p.stderr.decode("utf8","replace")[:150])
    return json.loads(p.stdout)
def api_zip(artifact_id):
    p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],capture_output=True,timeout=360)
    if p.returncode:raise RuntimeError("DOWNLOAD "+str(artifact_id)+" "+p.stderr.decode("utf8","replace")[:150])
    if not zipfile.is_zipfile(io.BytesIO(p.stdout)):raise RuntimeError("NOT_ZIP "+str(artifact_id))
    return p.stdout
def walk_zip(blob,prefix,depth=0):
    if depth>2:return
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        if z.testzip() is not None:raise RuntimeError("ZIP_CRC")
        for entry in z.infolist():
            if entry.is_dir():continue
            if entry.file_size>45_000_000:continue
            path=prefix+entry.filename
            if entry.filename.lower().endswith(".zip") and depth<2:
                yield from walk_zip(z.read(entry),path+"!/",depth+1)
            elif entry.filename.lower().endswith(".json"):
                try: yield path,json.loads(z.read(entry))
                except (ValueError,UnicodeError): continue
def topic_map(text):
    t=norm(text)
    return {k:[term for term in terms if norm(term) in t] for k,terms in TOPICS.items() if any(norm(term) in t for term in terms)}
def save_json(f,d):f.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf8")
def save_lines(f,rows):
    with f.open("w",encoding="utf8") as h:
        for x in rows:h.write(json.dumps(x,ensure_ascii=False)+"\n")
def load_one(seq,run):
    art=api_json(f"repos/{REPO}/actions/runs/{run}/artifacts?per_page=100")
    choices=[x for x in art.get("artifacts",[]) if x.get("name","").endswith("-TEXT-ONLY") and not x.get("expired")]
    if len(choices)!=1:raise RuntimeError(f"TEXT_ONLY_ARTIFACT_COUNT_{seq}_{len(choices)}")
    a=choices[0];raw=api_zip(a["id"])
    speeches=[];chats=[];boards=[];file_index=[];sha_zip=sha(raw)
    for path,doc in walk_zip(raw,f"artifact_{a['id']}/"):
        file_index.append(path)
        if isinstance(doc,dict) and path.endswith("ASR_REVIEW_UNVERIFIED.json"):
            for item in doc.get("speech_lines",[]):
                if not isinstance(item,dict):continue
                speeches.append({"start":sec(item.get("start")),"end":sec(item.get("end")),
                    "text":item.get("text",""),"speaker":item.get("speaker","UNKNOWN"),
                    "verified_speaker":bool(item.get("speaker_verified",False)),
                    "id":item.get("id"),"audio_sha256":item.get("source_audio_sha256"),
                    "source":path})
        if isinstance(doc,dict) and path.endswith("full_chat_ocr_candidates_PRIVATE.json"):
            for item in doc.get("results",[]):
                if not isinstance(item,dict):continue
                chats.append({"time":sec(item.get("time_original_video_seconds")),
                    "text":item.get("text_lines",[]),"id":item.get("frame_id"),
                    "frame_sha256":item.get("source_frame_sha256"),"kind":"student_chat",
                    "source":path})
        if isinstance(doc,dict) and path.endswith("board_ocr_candidates_PRIVATE.json"):
            for item in doc.get("results",[]):
                if not isinstance(item,dict):continue
                boards.append({"time":sec(item.get("time_original_video_seconds")),
                    "text":item.get("machine_text_raw",""),"id":item.get("frame_id"),
                    "frame_sha256":item.get("source_frame_sha256"),"kind":"board",
                    "source":path})
    # Source transcript must be identifiable exactly once; duplicates are fatal rather than silently counted.
    if not speeches:raise RuntimeError("MISSING_MERGED_ASR_TEXT")
    if not chats and not boards:raise RuntimeError("MISSING_ORIGINAL_OCR_TEXT")
    stamped=sorted([(v["time"],v) for v in chats+boards if v["time"] is not None],key=lambda x:x[0])
    times=[v[0] for v in stamped]
    n_exact=n_near=n_unmatched=0;sample=[];candidates=[]
    for i,s in enumerate(speeches):
        start,end=s["start"],s["end"];links=[]
        if start is not None:
            if end is not None and end>=start:
                lo=bisect.bisect_left(times,start);hi=bisect.bisect_right(times,end)
                for j in range(lo,min(hi,lo+5)):
                    v=stamped[j][1]
                    links.append({"kind":v["kind"],"visual_id":v["id"],"time":v["time"],
                      "relation":"WITHIN_SPEECH_INTERVAL","source":v["source"],
                      "frame_sha256":v["frame_sha256"],"ocr_raw":v["text"]})
            if not links:
                p=bisect.bisect_left(times,start)
                near=sorted((abs(times[j]-start),j) for j in range(max(0,p-5),min(len(times),p+6)))
                for delta,j in near:
                    if delta>6 or len(links)>=3:break
                    v=stamped[j][1]
                    links.append({"kind":v["kind"],"visual_id":v["id"],"time":v["time"],
                      "delta_seconds":round(delta,3),"relation":"NEAR_6_SECONDS",
                      "source":v["source"],"frame_sha256":v["frame_sha256"],"ocr_raw":v["text"]})
        if links:
            if links[0]["relation"]=="WITHIN_SPEECH_INTERVAL":n_exact+=1
            else:n_near+=1
        else:n_unmatched+=1
        tags=topic_map(s["text"])
        if not tags:continue
        context=[{"time_start":speeches[j]["start"],"text":speeches[j]["text"]}
                 for j in range(max(0,i-2),min(len(speeches),i+3))]
        rec={"sequence":seq,"video_queue_name":f"film-{seq-2}" if seq>2 else f"session-{seq}",
             "speech_index":i,"time_start":start,"time_end":end,
             "speech_exact":s["text"],"speech_source_id":s["id"],
             "source_audio_sha256":s["audio_sha256"],"context":context,
             "topics_lexical_only":tags,"visual_candidates":links,
             "speaker_verified":s["verified_speaker"],
             "meaning_verified":False,"teacher_rule_approved":False,
             "cannot_trade":True}
        candidates.append(rec)
    stats={"sequence":seq,"run_id":run,"artifact_id":a["id"],"artifact_zip_sha256":sha_zip,
       "source_json_files":len(file_index),"speech":len(speeches),"chat_ocr":len(chats),
       "board_ocr":len(boards),"with_visual_same_interval":n_exact,
       "with_visual_near_6s":n_near,"without_visual_6s":n_unmatched,
       "lexical_candidates":len(candidates),"teacher_rules_approved":0,
       "source_level":"machine_ASR_OCR_UNVERIFIED"}
    save_lines(OUT/f"session_{seq:02d}_speech_visual_UNVERIFIED.jsonl",candidates)
    return stats,candidates
def main():
    OUT.mkdir(exist_ok=True)
    reports=[];fail=[];refs=[]
    for seq,run in RUNS.items():
        try:
            s,rows=load_one(seq,run);reports.append(s)
            for row in rows:
                if "cross_session" in row["topics_lexical_only"]:
                    refs.append({"sequence":seq,"time":row["time_start"],"text":row["speech_exact"],
                      "context":row["context"],"topics":list(row["topics_lexical_only"]),
                      "not_validated":True})
            print("ARTIN_SESSION_SOURCE_SCAN="+json.dumps(s,ensure_ascii=False),flush=True)
        except Exception as e:
            fail.append({"sequence":seq,"run":run,"error":str(e)[:300]})
            print("ARTIN_SESSION_FAILURE="+json.dumps(fail[-1],ensure_ascii=False),flush=True)
    total={"source_sequences_checked":len(RUNS),"successful":len(reports),"failed":fail,
       "speech_total":sum(x["speech"] for x in reports),
       "ocr_total":sum(x["chat_ocr"]+x["board_ocr"] for x in reports),
       "with_same_interval":sum(x["with_visual_same_interval"] for x in reports),
       "near_six_seconds":sum(x["with_visual_near_6s"] for x in reports),
       "without_visual":sum(x["without_visual_6s"] for x in reports),
       "lexical_candidates":sum(x["lexical_candidates"] for x in reports),
       "cross_session_reference_candidates":len(refs),
       "rules_approved":0,"teacher_semantic_verified":False,
       "tests":{"row_time_totals_consistent":all(x["speech"]==x["with_visual_same_interval"]+x["with_visual_near_6s"]+x["without_visual_6s"] for x in reports),
                "never_certifies_lexical_matches":all(x["teacher_rules_approved"]==0 for x in reports),
                "every_registered_source_processed":len(reports)==len(RUNS)}}
    save_json(OUT/"session_coverage_summary.json",total)
    save_json(OUT/"session_receipts.json",reports)
    save_json(OUT/"cross_session_mentions_NOT_VERIFIED.json",refs)
    print("ARTIN25_GROUP_SOURCE_AUDIT="+json.dumps(total,ensure_ascii=False),flush=True)
    if fail or not all(total["tests"].values()):sys.exit(2)
if __name__=="__main__":main()
