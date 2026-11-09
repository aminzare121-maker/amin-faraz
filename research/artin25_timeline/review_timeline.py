#!/usr/bin/env python3
"""Cumulative evidence map, NOT teacher semantic certification or a strategy."""
from collections import defaultdict
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import zipfile

REPO="aminzare121-maker/amin-faraz"
ARTIFACT=13693901511
OUT=Path("artin25_timeline_output")
OUT.mkdir(exist_ok=True)
TOPICS={
  "bid_ask_spread":["اسک","بید","اسپرد","bid","ask"],
  "stop_breakeven":["ریسک فری","ریسکفیری","ریسک فیری","استاپ","استاپلاس","حد ضرر","بریک ایون"],
  "targets":["تارگت","تی پی","tp","هدف دوم","تارگت دو"],
  "pivot_liquidity":["پیوت","پیووت","نقدینگی","liquidity","liq","اوردر بلاک","اردر بلاک"],
  "candle_entry":["کندل","کلوز","شکست","مدل ورود","مودل ورود","پولبک","fvg","اف وی جی"]
}
EXAMPLE=["مثلا","مثلاً","برای مثال","به عنوان مثال","فرض کن","فرض کنید"]
REVISION=["جلسه قبل","جلسه قبلی","دفعه قبل","اشتباه گفتم","اصلاح میکنم","تصحیح","اون چیزی که گفتم"]
NEGATIONS=["نکن","نباید","ممنوع","اشتباه","نمی‌","نمی "]
def norm(s):
    return str(s).replace("ي","ی").replace("ك","ک").replace("\u200c"," ").lower().strip()
def contains(t,w):
    t,w=norm(t),norm(w)
    if len(w)<=3: return re.search(r"(?<!\w)"+re.escape(w)+r"(?!\w)",t) is not None
    return w in t
def save(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")
def download_artifact():
    result=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{ARTIFACT}/zip"],capture_output=True,timeout=180)
    if result.returncode:
        raise RuntimeError("GitHub download failed: "+result.stderr.decode("utf8","replace")[:200])
    if not zipfile.is_zipfile(io.BytesIO(result.stdout)):raise RuntimeError("Artifact not a ZIP")
    return result.stdout

data=download_artifact()
source_zip_hash=hashlib.sha256(data).hexdigest()
with zipfile.ZipFile(io.BytesIO(data)) as z:
    if z.testzip() is not None:raise RuntimeError("Source ZIP CRC failed")
    names={Path(k).name:k for k in z.namelist() if not k.endswith("/")}
    all_rows={}
    for seq in range(4,26):
        n=f"session_{seq:02d}_speech_visual_UNVERIFIED.jsonl"
        if n not in names:raise RuntimeError("No archive: "+n)
        all_rows[seq]=[json.loads(x) for x in z.read(names[n]).decode("utf8").splitlines() if x.strip()]
    if len(all_rows)!=22:raise RuntimeError("Expected 22 sequence archives")

timeline=defaultdict(list)
for seq,rows in all_rows.items():
    for r in rows:
        spoken=r.get("speech_exact","")
        context=r.get("context") or []
        context_text=" ".join(str(x.get("text","")) for x in context)
        visuals=r.get("visual_candidates") or []
        exact=[v for v in visuals if v.get("relation")=="WITHIN_SPEECH_INTERVAL"]
        for topic,words in TOPICS.items():
            matched=[w for w in words if contains(spoken,w)]
            if not matched:continue
            entry={
                "sequence":seq,
                "time_s":r.get("time_start"),
                "source_speech_id":r.get("speech_source_id"),
                "source_audio_sha256":r.get("source_audio_sha256"),
                "exact_ASR_text":spoken,
                "context_source_lines":context,
                "matched_lexical_terms":matched,
                "has_example_phrase_in_context":any(contains(context_text,x) for x in EXAMPLE),
                "has_explicit_prior_class_reference":any(contains(context_text,x) for x in REVISION),
                "negation_cues": [x for x in NEGATIONS if contains(context_text,x)],
                "same_interval_visuals":[{
                    "category":v.get("kind"),
                    "time_s":v.get("time"),
                    "frame_sha256":v.get("frame_sha256"),
                    "source_original_file":v.get("source"),
                    "ocr_original":str(v.get("ocr_raw",""))[:1400]
                } for v in exact[:2]],
                "speaker_role_teacher_verified":False,
                "instructor_rule_semantics_verified":False,
                "supersedes_any_prior_rule":False,
                "trade_permitted":False
            }
            timeline[topic].append(entry)
summary={"schema":"artin25_cumulative_topic_index_v1",
         "source_sequences":list(range(4,26)),
         "not_in_this_source_index":[1,2,3],
         "source_artifact":ARTIFACT,"source_zip_sha256":source_zip_hash,
         "topic_counts":{},
         "cross_session_topics":{},
         "chronological_revision_certification":False,
         "approved_mt5_entry_rules":0,"approved_mt5_exit_rules":0,
         "all_original_speech_and_frame_sources_unchanged":True}
for topic,entries in sorted(timeline.items()):
    entries.sort(key=lambda r:(r["sequence"],r["time_s"] if r["time_s"] is not None else 0))
    sessions=sorted(set(r["sequence"] for r in entries))
    sample=[r for r in entries if r["same_interval_visuals"]][:3]
    save(OUT/f"{topic}_chronological_source_trace.json",{
        "schema":"artin25_topic_trace_source_only",
        "topic":topic,"number_of_source_mentions":len(entries),
        "sessions_present":sessions,
        "potential_prior_lesson_reference_count":sum(bool(x["has_explicit_prior_class_reference"]) for x in entries),
        "illustrative_example_cue_count":sum(bool(x["has_example_phrase_in_context"]) for x in entries),
        "sample_with_same_interval_visual":sample,
        "entries":entries,
        "WARNING":"Words in common do not establish an amendment, contradiction, or teacher rule."
    })
    summary["topic_counts"][topic]=len(entries)
    summary["cross_session_topics"][topic]=sessions

# An intentionally non-executable contract for later MT5 implementation.
model={"schema":"artin_strategy_semantics_contract_v1",
       "source_sessions_covered":list(range(4,26)),
       "needs_sessions":[1,2,3],
       "source_role_verified":False,
       "entry_condition":None,"exit_condition":None,
       "risk_calculation_condition":None,
       "entry_examples_with_instructor_expected_decisions":[],
       "later_session_precedence_resolved":False,
       "teacher_method_validated":False,
       "allow_trade":False}
save(OUT/"MT5_PROOF_GATE_NOT_READY.json",model)
summary["tests"]={
 "all_22_sessions_present":set(all_rows)==set(range(4,26)),
 "no_teacher_rule_certified":all(not x["instructor_rule_semantics_verified"] for v in timeline.values() for x in v),
 "no_trade_allowed":model["allow_trade"] is False,
 "topic_chronology_sorted":all(v==sorted(v,key=lambda r:(r["sequence"],r["time_s"] if r["time_s"] is not None else 0)) for v in timeline.values())
}
save(OUT/"summary.json",summary)
print("ARTIN_CUMULATIVE_TOPIC_RESULT="+json.dumps(summary,ensure_ascii=False),flush=True)
if not all(summary["tests"].values()):raise SystemExit(2)
