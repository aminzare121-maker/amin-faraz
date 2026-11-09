#!/usr/bin/env python3
"""Build evidence-grounded classroom learning/replay cases from ordered sessions.
Input JSON: {"sessions":[{"session_id":"...","speech":[{"start":0,"end":2,"text":"..."}],"questions":[{"time_seconds":0,"text":"..."}]}]}
This DOES NOT authorize automated trades or invent teacher decisions.
"""
import argparse, hashlib, json, re
from pathlib import Path

TOPICS = {
 "execution": ("ورود","خروج","بخر","بفروش","خرید","فروش","پوزیشن","معامله"),
 "risk": ("حد ضرر","حد سود","ریسک","استاپ","ضرر","سود","سرمایه"),
 "tools": ("متاتریدر","بروکر","چارت","نمودار","لات","تتر","حساب"),
 "psychology": ("روان","ترس","طمع","صبر","انضباط"),
}
QUESTION_WORDS=("چرا","چطور","چگونه","یعنی","آیا","میشه","می شه","سؤال","سوال","؟","?")
NEGATIONS=("نکن","نخرید","نفروش","نباید","نمی","هرگز")
def norm(t):
 return re.sub(r"\s+"," ",str(t or "").replace("ي","ی").replace("ك","ک")).strip()
def tokens(t):
 return {w for w in re.findall(r"[\wآ-ی]+",norm(t)) if len(w)>=4 and w not in {"استاد","میشه","یعنی","چطور","گفتید","برای","اینجا","میکنم","داریم"}}
def build(sessions):
 out={"schema":"artin_classroom_to_engine_v1","sessions":[],"cross_session_links":[],"replay_cases":[],"verified_executable_rules":[],"unresolved":[],"policy":"DO_NOT_TRADE_FROM_UNVERIFIED_TEXT"}
 prior=[]
 for session in sessions:
  sid=session["session_id"]
  speech=sorted([dict(x,start=float(x["start"]),text=norm(x.get("text"))) for x in session.get("speech",[]) if norm(x.get("text"))],key=lambda x:x["start"])
  qs=sorted(session.get("questions",[]),key=lambda q:float(q.get("time_seconds",q.get("start",0))))
  cases=[]
  for i,s in enumerate(speech):
   topic=[key for key,terms in TOPICS.items() if any(t in s["text"] for t in terms)]
   question=any(w in s["text"] for w in QUESTION_WORDS)
   if not topic and not question:continue
   ref=f"{sid}:{s['start']:.2f}:{i}"
   case={"case_id":hashlib.sha256(ref.encode()).hexdigest()[:16],"session_id":sid,"time_seconds":s["start"],
      "speech_evidence":s,"prior_context":speech[max(0,i-2):i],
      "following_context":speech[i+1:i+5],"topics":topic,
      "question_candidate":question,"negation_review_required":any(w in s["text"] for w in NEGATIONS),
      "expected_decision":None,"engine_decision":None,
      "replay_status":"BLOCKED_UNVERIFIED_TEACHER_EXAMPLE"}
   cases.append(case)
   if "execution" in topic:
    out["unresolved"].append({"session_id":sid,"time_seconds":s["start"],"case_id":case["case_id"],"reason":"Teacher/board evidence not independently verified"})
  question_records=[]
  for q in qs:
   t=float(q.get("time_seconds",q.get("start",0)))
   text=norm(q.get("text",q.get("candidate_text",q.get("question_text_ocr",""))))
   if not text:continue
   following=[s for s in speech if t<=s["start"]<=t+90][:12]
   question_records.append({"time_seconds":t,"question":text,"following_speech_candidates":following,"speaker_verified":False,"teacher_answer_verified":False})
   for old in prior:
    shared=tokens(text)&tokens(old["text"])
    if len(shared)>=2:
     out["cross_session_links"].append({"prior_session":old["session_id"],"current_session":sid,"prior_question":old["text"][:200],"current_question":text[:200],"shared_terms":sorted(shared),"meaning_verified":False})
   prior.append({"session_id":sid,"text":text})
  out["sessions"].append({"session_id":sid,"speech_segments":len(speech),"question_candidates":len(question_records),"question_context":question_records,"replay_case_count":len(cases),"teacher_semantics_verified":False,"engine_ready":False})
  out["replay_cases"].extend(cases)
 return out
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("input");parser.add_argument("output")
 args=parser.parse_args()
 source=json.loads(Path(args.input).read_text(encoding="utf-8"))
 sessions=source["sessions"]
 if not sessions or len({s["session_id"] for s in sessions})!=len(sessions):
  raise SystemExit("Missing or duplicate session")
 out=build(sessions)
 Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps({"sessions":len(out["sessions"]),"speech_counts":[x["speech_segments"] for x in out["sessions"]],"replay_candidates":len(out["replay_cases"]),"verified_rules":len(out["verified_executable_rules"])},ensure_ascii=False))
if __name__=="__main__":main()
