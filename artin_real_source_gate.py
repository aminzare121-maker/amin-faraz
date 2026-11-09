#!/usr/bin/env python3
"""Fail-closed integrity audit of private Artin archives; NOT a semantic verdict.

Run: python artin_real_source_gate.py --root /path/to/private/zips --out report.json
No original media or private transcript is committed to public GitHub.
"""
import argparse, hashlib, io, json, re, sys, zipfile
from pathlib import Path

FIRST="بهروز.zip"
LATER="Artin_22_Sessions_Speech_OCR_Review_20261109.zip"
CASES="Artin_Six_Source_Semantic_Cases_20261109.zip"
FRAMES="Artin_66_Original_Frames_SourceLinked_20261109.zip"
SHA=re.compile(r"^[a-f0-9]{64}$")

def sha_ok(value):
    return isinstance(value,str) and SHA.fullmatch(value) is not None

def records(z,member):
    with z.open(member) as f:
        for line_number,line in enumerate(f,1):
            if line.strip():
                try: yield json.loads(line)
                except (ValueError,UnicodeDecodeError) as e:
                    raise ValueError(f"{member}:{line_number}: invalid JSONL: {e}") from e

def audit(root):
    root=Path(root)
    errors=[]; sessions={}
    with zipfile.ZipFile(root/FIRST) as z:
        names=set(z.namelist())
        for n in (1,2,3):
            p=f"DERIVED_NOT_RAW/VIDEO_{n:02d}/"
            paths=[p+x for x in ("SPEECH_TIMELINE_MACHINE_UNVERIFIED.jsonl",
                                  "CHAT_OCR_FRAMES_MACHINE_UNVERIFIED.jsonl",
                                  "BOARD_OCR_MACHINE_UNVERIFIED.jsonl")]
            if not all(path in names for path in paths):
                errors.append(f"session {n}: missing ASR, chat, or board evidence");continue
            a=c=b=0
            for row in records(z,paths[0]):
                a+=1;s=row.get("start_seconds");e=row.get("end_seconds")
                if not sha_ok(row.get("source_video_sha256")) or not (type(s) in (int,float) and type(e) in (int,float) and 0<=s<=e):
                    errors.append(f"session {n} ASR {a}: invalid anchor")
                if row.get("teacher_rule_verified") is not False or row.get("human_verified") is not False:
                    errors.append(f"session {n} ASR {a}: unsupported approval")
            for row in records(z,paths[1]):
                c+=1
                if row.get("human_verified") is not False:
                    errors.append(f"session {n} chat {c}: unsupported approval")
            for row in records(z,paths[2]):
                b+=1
                if not sha_ok(row.get("source_image_sha256")) or row.get("human_verified") is not False:
                    errors.append(f"session {n} board {b}: invalid anchor/approval")
            if not min(a,c,b):errors.append(f"session {n}: empty evidence modality")
            sessions[n]={"session":n,"speech_rows":a,"chat_rows":c,"board_rows":b,
                         "teacher_semantics_verified":False}
    with zipfile.ZipFile(root/LATER) as z:
        names=set(z.namelist())
        for n in range(4,26):
            path=f"session_{n:02d}_speech_visual_UNVERIFIED.jsonl"
            if path not in names:errors.append(f"session {n}: missing evidence");continue
            rows=visuals=aligned=near=0
            for row in records(z,path):
                rows+=1;s=row.get("time_start");e=row.get("time_end")
                if row.get("sequence")!=n or not sha_ok(row.get("source_audio_sha256")):
                    errors.append(f"session {n} row {rows}: source mismatch")
                if not (type(s) in (int,float) and type(e) in (int,float) and 0<=s<=e):
                    errors.append(f"session {n} row {rows}: bad timestamp");continue
                if any(row.get(k) is not False for k in ("speaker_verified","meaning_verified","teacher_rule_approved")) or row.get("cannot_trade") is not True:
                    errors.append(f"session {n} row {rows}: unsupported semantic/trade approval")
                matches=row.get("visual_candidates")
                if not isinstance(matches,list):errors.append(f"session {n} row {rows}: malformed visuals");continue
                for frame in matches:
                    visuals+=1
                    if not isinstance(frame,dict) or not sha_ok(frame.get("frame_sha256")) or type(frame.get("time")) not in (int,float):
                        errors.append(f"session {n} row {rows}: invalid image anchor");continue
                    t=frame["time"]
                    if s<=t<=e:aligned+=1
                    elif min(abs(t-s),abs(t-e))<=6.01:near+=1
                    else:errors.append(f"session {n} row {rows}: image outside 6s window")
            if rows==0:errors.append(f"session {n}: empty speech evidence")
            sessions[n]={"session":n,"speech_rows":rows,"linked_visuals":visuals,
                         "overlap_visuals":aligned,"near_visuals":near,
                         "teacher_semantics_verified":False}
    checks=[]
    with zipfile.ZipFile(root/CASES) as cz,zipfile.ZipFile(root/FRAMES) as outer:
        cases=json.loads(cz.read("six_semantic_source_cases.json"))
        with zipfile.ZipFile(io.BytesIO(outer.read("66_original_source_frames.zip"))) as frames:
            names=set(frames.namelist())
            for case in cases:
                proof=case.get("proof",{})
                name=proof.get("visual_manifest_frame_archive_path")
                expected=proof.get("visual_SHA256")
                actual=hashlib.sha256(frames.read(name)).hexdigest() if name in names else None
                ok=sha_ok(expected) and expected==actual
                checks.append({"case_id":case.get("id"),"session":case.get("seq"),"image_sha256_match":ok})
                if not ok:errors.append(f"case {case.get('id')}: original image/hash mismatch")
                if case.get("seq") not in sessions:errors.append("case refers to missing session")
                if case.get("strategy_rule_certified") is not False or case.get("mt5_auto_order_allowed") is not False:
                    errors.append(f"case {case.get('id')}: unsupported trading approval")
    if sorted(sessions)!=list(range(1,26)):errors.append("missing one or more sessions")
    return {"schema":"artin_real_source_gate_v1","source_integrity_pass":not errors,
            "source_sessions_inspected":len(sessions),
            "speech_rows_total":sum(s["speech_rows"] for s in sessions.values()),
            "case_images_inspected":len(checks),
            "matched_case_image_hashes":sum(bool(c["image_sha256_match"]) for c in checks),
            "teacher_meaning_verified":False,"verified_executable_trade_rules":0,
            "allow_mt5_trade":False,"sessions":[sessions[n] for n in sorted(sessions)],
            "frame_checks":checks,"errors":errors,
            "scope_limit":"Machine ASR/OCR anchors and selected source PNG bytes only; NOT listening to teacher audio, semantic review, or motor decision comparison"}

def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    try:result=audit(args.root)
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        result={"source_integrity_pass":False,"teacher_meaning_verified":False,
                "allow_mt5_trade":False,"errors":[str(exc)]}
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result.get(k) for k in ("source_integrity_pass",
         "source_sessions_inspected","speech_rows_total","matched_case_image_hashes",
         "case_images_inspected","teacher_meaning_verified","allow_mt5_trade","errors")},ensure_ascii=False))
    return 0 if result["source_integrity_pass"] else 2

if __name__=="__main__":sys.exit(main())
