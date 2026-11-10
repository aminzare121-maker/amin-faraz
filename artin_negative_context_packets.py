"""Build read-only review contexts from the original private 25-session ASR archive.
Does NOT verify speaker identity, teacher intent, or authorize trading.
"""
import json
import zipfile

def build(archive_path,cases_doc,radius_seconds=30):
    if not isinstance(radius_seconds,(int,float)) or radius_seconds<=0 or radius_seconds>300:
        raise ValueError("invalid review radius")
    cases=cases_doc["cases"]
    output=[]
    with zipfile.ZipFile(archive_path) as z:
        rows={}
        for session in {c["session"] for c in cases}:
            name=f"session_{session:02d}_unified_machine_speech_UNVERIFIED.jsonl"
            rows[session]=sorted((json.loads(x) for x in z.read(name).decode().splitlines() if x.strip()),key=lambda x:x["start_seconds"])
        for c in cases:
            a=[r for r in rows[c["session"]] if r["source_segment_id"]==c["segment_id"]]
            if len(a)!=1:raise ValueError("source identity mismatch")
            target=a[0]
            if (target["start_seconds"]!=c["start_seconds"] or target["end_seconds"]!=c["end_seconds"]
                    or target["machine_text_unverified"]!=c["text_unverified"]
                    or target["source_audio_sha256"]!=c["audio_source_sha256"]):
                raise ValueError("original source mismatch")
            around=[{"id":r["source_segment_id"],"start":r["start_seconds"],"end":r["end_seconds"],
                "text_unverified":r["machine_text_unverified"]} for r in rows[c["session"]]
                if r["end_seconds"]>=target["start_seconds"]-radius_seconds
                and r["start_seconds"]<=target["end_seconds"]+radius_seconds]
            output.append({"session":c["session"],"segment_id":c["segment_id"],
                "start_seconds":c["start_seconds"],"routes":c["assigned_routes"],
                "context":around,"visual_metadata":target.get("visual_source_nearby",[]),
                "teacher_meaning_verified":False,"action":"NO_TRADE"})
    return {"case_count":len(output),"cases":output,"semantic_certifications":0,
        "orders_authorized":0}
