"""Artin 24-citation source membership verifier. Integrity only; never semantic approval."""
import json
import math
import zipfile
from collections import Counter

EXPECTED_ROUTES=frozenset("""BREAK_STRONG BREAK_VERY_STRONG_RETEST BREAK_WEAK_FULLBODY_EXCEPTION BREAK_WEAK_PIVOT PULLBACK_STANDARD REVERSAL_CLASSIC REVERSAL_STAR REVERSAL_THREE STOPPUNCH_DOJI_AHEAD STOPPUNCH_DOJI_TIED STOPPUNCH_OPPOSITE_CONFIRMATION STOPPUNCH_S22_SELL_CONFIRMED_PAUSE STOPPUNCH_SAME_COLOUR""".split())

def check_and_build(archive,citation_doc,margin=45.0):
    if not isinstance(citation_doc,dict) or not isinstance(citation_doc.get("citations"),list):
        raise ValueError("missing citations")
    citations=citation_doc["citations"]
    if len(citations)!=24 or {c["route_id"] for c in citations}!=EXPECTED_ROUTES:
        raise ValueError("expected exactly 24 citations across 13 routes")
    if sorted(c.get("citation_index") for c in citations)!=list(range(1,25)):
        raise ValueError("citation index must be exactly 1..24")
    if type(margin) not in (int,float) or not math.isfinite(margin) or not 0<=margin<=300:
        raise ValueError("invalid context margin")
    cases=[];shared=Counter();sessions={}
    with zipfile.ZipFile(archive) as z:
        for session in {c["session"] for c in citations}:
            if type(session) is not int or not 1<=session<=25:
                raise ValueError("invalid session")
            name=f"session_{session:02d}_unified_machine_speech_UNVERIFIED.jsonl"
            rows=[json.loads(line) for line in z.read(name).decode("utf-8").splitlines() if line.strip()]
            ids={}
            for row in rows:
                key=row["source_segment_id"]
                if key in ids:raise ValueError("duplicate original segment id")
                ids[key]=row
            sessions[session]=(rows,ids)
        for c in citations:
            session=c["session"];start,end=c["start_seconds"],c["end_seconds"]
            if not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end)) or not 0<=start<end:
                raise ValueError("invalid citation time")
            rows,ids=sessions[session]
            intersects=[r for r in rows if r["start_seconds"]<=end and r["end_seconds"]>=start]
            excerpts=c["excerpts"]
            if len(intersects)!=len(excerpts) or len(excerpts)!=c["expected_machine_asr_rows"]:
                raise ValueError("source citation count discrepancy")
            original_ids=[r["source_segment_id"] for r in intersects]
            supplied_ids=[e["asr_segment_id"] for e in excerpts]
            if len(set(supplied_ids))!=len(supplied_ids):
                raise ValueError("duplicate cited ASR segment")
            if set(supplied_ids)!=set(original_ids):
                raise ValueError("citation source membership mismatch")
            for ex in excerpts:
                r=ids[ex["asr_segment_id"]]
                for a,b in (("start","start_seconds"),("end","end_seconds"),
                  ("text_unverified","machine_text_unverified"),("original_audio_sha256","source_audio_sha256"),
                  ("record_id","record_id")):
                    if ex[a]!=r[b]:raise ValueError("source citation content changed: "+a)
                shared[(session,ex["asr_segment_id"])]+=1
            around=[r for r in rows if r["end_seconds"]>=start-margin and r["start_seconds"]<=end+margin]
            cases.append({"citation_index":c["citation_index"],"route_id":c["route_id"],
              "session":session,"start_seconds":start,"end_seconds":end,
              "context_segment_count":len(around),"source_excerpt_count":len(excerpts),
              "machine_context":[{"source_segment_id":r["source_segment_id"],
               "start_seconds":r["start_seconds"],"end_seconds":r["end_seconds"],
               "machine_text_unverified":r["machine_text_unverified"],
               "source_audio_sha256":r["source_audio_sha256"]} for r in around],
              "teacher_meaning_verified":False,"trade_authorized":False})
    return {"schema":"artin_24_full_context_integrity_v2","route_count":13,
      "citation_count":24,"source_excerpt_occurrences":sum(c["source_excerpt_count"] for c in cases),
      "source_unique_segment_keys":len(shared),"shared_segment_keys":sum(v>1 for v in shared.values()),
      "cases":cases,"teacher_semantics_certified":False,"mt5_orders_authorized":0}

def main():
    """Run a read-only integrity review against the original private archive."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", help="original private 25-session ZIP")
    parser.add_argument("citations", help="original 24-citation private JSON")
    parser.add_argument("output", help="destination JSON report")
    parser.add_argument("--margin", type=float, default=45.0)
    args = parser.parse_args()
    result = check_and_build(args.archive,
        json.loads(Path(args.citations).read_text(encoding="utf-8")), args.margin)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"},
                     ensure_ascii=False))

if __name__ == "__main__":
    main()
