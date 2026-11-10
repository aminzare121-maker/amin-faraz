"""Self-contained test; public CI does not need private teacher audio/ASR."""
import copy
import io
import json
import unittest
import zipfile
from artin_24_full_context_integrity import check_and_build, EXPECTED_ROUTES

def sample():
    routes=sorted(EXPECTED_ROUTES)
    citations=[]
    rows=[]
    for index in range(24):
        row={"source_segment_id":f"s{index}","start_seconds":float(index*10),
             "end_seconds":float(index*10+2),"machine_text_unverified":f"example {index}",
             "source_audio_sha256":f"fake_{index}","record_id":f"rec_{index}"}
        rows.append(row)
        citations.append({"citation_index":index+1,"route_id":routes[index%13],
            "session":1,"start_seconds":row["start_seconds"],"end_seconds":row["end_seconds"],
            "expected_machine_asr_rows":1,
            "excerpts":[{"asr_segment_id":row["source_segment_id"],
              "start":row["start_seconds"],"end":row["end_seconds"],
              "text_unverified":row["machine_text_unverified"],
              "original_audio_sha256":row["source_audio_sha256"],"record_id":row["record_id"]}]})
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        z.writestr("session_01_unified_machine_speech_UNVERIFIED.jsonl",
           "\n".join(json.dumps(r) for r in rows))
    buf.seek(0)
    return buf,{"citations":citations}

class TestMembership(unittest.TestCase):
    def test_valid(self):
        z,d=sample()
        x=check_and_build(z,d)
        self.assertEqual((x["citation_count"],x["mt5_orders_authorized"]),(24,0))
    def test_duplicate_excerpts_rejected(self):
        z,d=sample()
        # Add two source rows within one interval to reproduce the real bug.
        rows=[{"source_segment_id":"a","start_seconds":0.0,"end_seconds":1.0,
               "machine_text_unverified":"a","source_audio_sha256":"fake","record_id":"a"},
              {"source_segment_id":"b","start_seconds":1.0,"end_seconds":2.0,
               "machine_text_unverified":"b","source_audio_sha256":"fake","record_id":"b"}]
        with zipfile.ZipFile(z,"r") as original:
            src=[json.loads(x) for x in original.read("session_01_unified_machine_speech_UNVERIFIED.jsonl").decode().splitlines()]
        src=[r for r in src if r["source_segment_id"]!="s0"]+rows
        z=io.BytesIO()
        with zipfile.ZipFile(z,"w") as out:
            out.writestr("session_01_unified_machine_speech_UNVERIFIED.jsonl","\n".join(json.dumps(x) for x in src))
        z.seek(0)
        target=d["citations"][0]
        target["end_seconds"]=2.0
        target["expected_machine_asr_rows"]=2
        a={"asr_segment_id":"a","start":0.0,"end":1.0,"text_unverified":"a",
           "original_audio_sha256":"fake","record_id":"a"}
        target["excerpts"]=[a,copy.deepcopy(a)]
        with self.assertRaisesRegex(ValueError,"duplicate cited"):
            check_and_build(z,d)
    def test_citation_id_repeated(self):
        z,d=sample()
        d["citations"][0]["citation_index"]=2
        with self.assertRaisesRegex(ValueError,"citation index"):
            check_and_build(z,d)
    def test_forged_route_rejected(self):
        z,d=sample()
        d["citations"][0]["route_id"]="FORGED"
        with self.assertRaises(ValueError):
            check_and_build(z,d)
if __name__=="__main__":unittest.main()
