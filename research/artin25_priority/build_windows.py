#!/usr/bin/env python3
"""Prioritize literal speech plus OCR excerpts from the independent 22-session audit."""
import io,json,os,re,zipfile,subprocess,pathlib,collections
OUT=pathlib.Path("artin25_priority_output");OUT.mkdir(exist_ok=True)
ID=13693901511;REPO="aminzare121-maker/amin-faraz"
p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{ID}/zip"],capture_output=True,timeout=180)
if p.returncode:raise RuntimeError(p.stderr.decode("utf8","replace")[:200])
with zipfile.ZipFile(io.BytesIO(p.stdout)) as z:
    print("ARTIN_SOURCE_ZIP_FILE_COUNT=",len(z.namelist()),flush=True)
    source={n.split("/")[-1]:z.read(n) for n in z.namelist() if not n.endswith("/")}
reviews=[];coverage=[]
for session in range(4,26):
    name=f"session_{session:02d}_speech_visual_UNVERIFIED.jsonl"
    names=[key for key in source if key.endswith(name)]
    if len(names)!=1:raise RuntimeError("MISSING_OR_DUPLICATE "+name)
    rows=[json.loads(s) for s in source[names[0]].decode("utf8").splitlines() if s.strip()]
    candidates=[]
    for x in rows:
        tags=x.get("topics_lexical_only",{})
        visuals=x.get("visual_candidates",[])
        same=[v for v in visuals if v.get("relation")=="WITHIN_SPEECH_INTERVAL"]
        board=[v for v in same if v.get("kind")=="board"]
        full=" ".join(str(v.get("text","")) for v in x.get("context",[]))
        conditional=bool(re.search(r"اگر|وقتی|به شرط|در صورت|تا زمانی",full))
        score=(4 if "entry" in tags and "pattern" in tags else 0)+(4 if "exit" in tags and "risk" in tags else 0)
        score+=(3 if "cross_session" in tags and len(tags)>1 else 0)+(3 if board else 0)
        score+=(2 if same else 0)+(2 if conditional else 0)+len(tags)
        candidates.append((score,x))
    candidates.sort(key=lambda item:(-item[0],item[1].get("time_start") if item[1].get("time_start") is not None else 1e12))
    picked=[]
    for score,x in candidates[:3]:
        context=x["context"]
        raw_ocr=[{"kind":v.get("kind"),"relation":v.get("relation"),
                  "time":v.get("time"),"text":str(v.get("ocr_raw"))[:500]} for v in x.get("visual_candidates",[])[:2]]
        picked.append({"session":session,"score_for_review_only":score,
          "speech_index":x["speech_index"],"time":x["time_start"],
          "speech":x["speech_exact"],"context":context,
          "tags":list(x.get("topics_lexical_only",{})),
          "visual_text_from_ocr":raw_ocr,"certified_rule":False})
    reviews.extend(picked)
    coverage.append({"session":session,"candidates":len(rows),"picked":len(picked)})
OUT.joinpath("priority_review.json").write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding="utf8")
OUT.joinpath("priority_coverage.json").write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding="utf8")
print("ARTIN_PRIORITY_COUNT=",len(reviews),flush=True)
for x in reviews:
    # Human-readable sample with exact source words and context, never a certified teacher rule.
    print("ARTIN_SEMANTIC_SOURCE_WINDOW="+json.dumps(x,ensure_ascii=False),flush=True)
assert len(reviews)==66
assert all(not x["certified_rule"] for x in reviews)
