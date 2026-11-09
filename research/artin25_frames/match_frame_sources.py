#!/usr/bin/env python3
"""Select 66 authentic frame files from source artifacts at corresponding video times.
Preserves the original image bytes, archive artifact id, SHA and timing difference.
This performs no semantic or trading-rule certification.
"""
import collections,hashlib,io,json,os,pathlib,re,subprocess,sys,zipfile
RUNS={4:42581509064,5:42582773628,6:42584076860,7:42585143164,
8:42587012605,9:42589898892,10:42597293832,11:42599131963,12:42602054376,
13:42603963161,14:42605730024,15:42607235228,16:42608711460,
17:42611072346,18:42614226886,19:42618004424,20:42620094527,
21:42623860053,22:42627673993,23:42629789714,24:42631530339,25:42633228325}
REPO="aminzare121-maker/amin-faraz"
OUT=pathlib.Path("artin25_frames_output");OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def get_json(api):
    r=subprocess.run(["gh","api",api],capture_output=True,timeout=160)
    if r.returncode:raise RuntimeError(api+":"+r.stderr.decode("utf8","replace")[:250])
    return json.loads(r.stdout)
def load_zip_file(api):
    r=subprocess.run(["gh","api",api],capture_output=True,timeout=360)
    if r.returncode:raise RuntimeError(api+":"+r.stderr.decode("utf8","replace")[:250])
    if not zipfile.is_zipfile(io.BytesIO(r.stdout)):raise RuntimeError("ZIP_INVALID:"+api)
    return r.stdout
def extract_time(name):
    m=re.search(r"_t(\d{10,12})_",name)
    return int(m.group(1))/1000.0 if m else None
priority_bytes=load_zip_file(f"repos/{REPO}/actions/artifacts/13693183892/zip")
with zipfile.ZipFile(io.BytesIO(priority_bytes)) as z:
    j=[n for n in z.namelist() if n.endswith("priority_review.json")]
    if len(j)!=1:raise RuntimeError("priority_review.json missing")
    priority=json.loads(z.read(j[0]))
if len(priority)!=66:raise RuntimeError("priority_count_not_66")
by_seq=collections.defaultdict(list)
for r in priority:by_seq[r["session"]].append(r)
results=[];errors=[];total_bytes=0
output_zip=OUT/"66_original_source_frames.zip"
with zipfile.ZipFile(output_zip,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=2) as save:
  for seq,run in RUNS.items():
    try:
      art=get_json(f"repos/{REPO}/actions/runs/{run}/artifacts?per_page=100")
      items=[a for a in art.get("artifacts",[]) if a.get("name","").endswith("-original-board") and not a.get("expired")]
      if len(items)!=1:raise RuntimeError("original-board-artifact-missing count="+str(len(items)))
      meta=items[0]
      blob=load_zip_file(f"repos/{REPO}/actions/artifacts/{meta['id']}/zip")
      with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=[n for n in z.namelist() if n.lower().endswith((".png",".jpeg",".jpg",".webp")) and not n.endswith("/")]
        candidates=[(extract_time(n),n) for n in names if extract_time(n) is not None and n.startswith("board/")]
        if not candidates:candidates=[(extract_time(n),n) for n in names if extract_time(n) is not None]
        if not candidates:raise RuntimeError("No timestamped original image frames")
        for k,row in enumerate(by_seq[seq]):
          target=float(row["time"])
          selected=sorted(candidates,key=lambda x:(abs(x[0]-target),x[0]))[:2]
          frames=[]
          for j,(ft,name) in enumerate(selected):
            data=z.read(name)
            suffix=pathlib.Path(name).suffix.lower()
            output_name=f"session_{seq:02d}/window_{k+1:02d}_frame_{j+1:02d}{suffix}"
            save.writestr(output_name,data)
            total_bytes+=len(data)
            frames.append({"source_original_path":name,"source_time_seconds":ft,
                  "speech_time_seconds":target,"abs_delta_seconds":round(abs(ft-target),3),
                  "archive_path":output_name,"source_image_sha256":sha(data),
                  "source_artifact_id":meta["id"],"is_same_speech_interval":False,
                  "semantic_verified":False})
          results.append({"session":seq,"priority_rank_in_session":k+1,
              "speech_time_seconds":target,"speech_exact":row["speech"],
              "context":row["context"],"topics":row["tags"],
              "source_artifact_id":meta["id"],"frames":frames,
              "teacher_rule_verified":False})
      print("FRAME_MATCHED_SESSION="+json.dumps({"sequence":seq,"source_artifact":meta["id"],
           "source_frames_count":len(names),"windows":len(by_seq[seq]),"status":"IMAGES_EXTRACTED_NOT_SEMANTICALLY_VERIFIED"}),flush=True)
    except Exception as exc:
      errors.append({"sequence":seq,"error":type(exc).__name__+":"+str(exc)[:250]})
      print("FRAME_MATCH_ERROR="+json.dumps(errors[-1]),flush=True)
  save.writestr("frame_window_manifest.json",json.dumps(results,ensure_ascii=False,indent=2))
  save.writestr("errors.json",json.dumps(errors,ensure_ascii=False,indent=2))
summary={"expected_window_count":66,"matched_window_count":len(results),
   "image_count":sum(len(r["frames"]) for r in results),
   "source_image_original_bytes":total_bytes,
   "sessions_matched":len(set(r["session"] for r in results)),
   "max_delta_seconds":max((f["abs_delta_seconds"] for r in results for f in r["frames"]),default=None),
   "errors":errors,"semantic_verified":False,
   "sha256_zip":sha(output_zip.read_bytes()),
   "success_all_source_frames":len(results)==66 and not errors}
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")
print("ARTIN25_FRAME_SOURCE_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
if errors or len(results)!=66:sys.exit(2)
