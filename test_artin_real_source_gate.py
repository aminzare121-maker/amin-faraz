"""Synthetic fail-closed regression tests; real archive audit runs separately."""
import hashlib, io, json, tempfile, unittest, zipfile
from pathlib import Path
from artin_real_source_gate import FIRST,LATER,CASES,FRAMES,audit
H="a"*64

def pack(path, members):
    with zipfile.ZipFile(path,"w") as z:
        for name,value in members.items():
            z.writestr(name,value if isinstance(value,bytes) else json.dumps(value).encode())

def fixture(folder):
    first={}
    for n in (1,2,3):
        prefix=f"DERIVED_NOT_RAW/VIDEO_{n:02d}/"
        first[prefix+"SPEECH_TIMELINE_MACHINE_UNVERIFIED.jsonl"]=json.dumps({
            "source_video_sha256":H,"start_seconds":1,"end_seconds":2,
            "teacher_rule_verified":False,"human_verified":False}).encode()
        first[prefix+"CHAT_OCR_FRAMES_MACHINE_UNVERIFIED.jsonl"]=b'{"human_verified": false}'
        first[prefix+"BOARD_OCR_MACHINE_UNVERIFIED.jsonl"]=json.dumps({
            "source_image_sha256":H,"human_verified":False}).encode()
    pack(folder/FIRST,first)
    later={}
    for n in range(4,26):
        later[f"session_{n:02d}_speech_visual_UNVERIFIED.jsonl"]=json.dumps({
            "sequence":n,"source_audio_sha256":H,"time_start":10,"time_end":12,
            "visual_candidates":[{"frame_sha256":H,"time":11}],
            "speaker_verified":False,"meaning_verified":False,
            "teacher_rule_approved":False,"cannot_trade":True}).encode()
    pack(folder/LATER,later)
    pixels=b"synthetic image for regression; NOT teacher visual evidence"
    images={}; cases=[]
    for n in (4,13,15,19,21,25):
        image_name=f"session_{n:02d}/frame.png";images[image_name]=pixels
        cases.append({"id":f"TEST-{n}","seq":n,
                      "proof":{"visual_manifest_frame_archive_path":image_name,
                               "visual_SHA256":hashlib.sha256(pixels).hexdigest()},
                      "strategy_rule_certified":False,"mt5_auto_order_allowed":False})
    pack(folder/CASES,{"six_semantic_source_cases.json":cases})
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w") as z:
        for name,data in images.items():z.writestr(name,data)
    pack(folder/FRAMES,{"66_original_source_frames.zip":buf.getvalue()})

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name);fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def test_complete_structure_is_not_semantic_proof(self):
        r=audit(self.root)
        self.assertTrue(r["source_integrity_pass"],r["errors"])
        self.assertEqual(r["source_sessions_inspected"],25)
        self.assertEqual(r["matched_case_image_hashes"],6)
        self.assertFalse(r["teacher_meaning_verified"])
        self.assertFalse(r["allow_mt5_trade"])
    def test_missing_session(self):
        with zipfile.ZipFile(self.root/LATER) as z:
            d={n:z.read(n) for n in z.namelist() if not n.startswith("session_25_")}
        pack(self.root/LATER,d)
        self.assertFalse(audit(self.root)["source_integrity_pass"])
    def test_tampered_original_frame_hash(self):
        with zipfile.ZipFile(self.root/CASES) as z:
            cases=json.loads(z.read("six_semantic_source_cases.json"))
        cases[0]["proof"]["visual_SHA256"]="0"*64
        pack(self.root/CASES,{"six_semantic_source_cases.json":cases})
        r=audit(self.root)
        self.assertFalse(r["source_integrity_pass"])
        self.assertEqual(r["matched_case_image_hashes"],5)
    def test_reject_claimed_teacher_semantics(self):
        with zipfile.ZipFile(self.root/CASES) as z:
            cases=json.loads(z.read("six_semantic_source_cases.json"))
        cases[0]["strategy_rule_certified"]=True
        pack(self.root/CASES,{"six_semantic_source_cases.json":cases})
        self.assertFalse(audit(self.root)["source_integrity_pass"])
    def test_reject_claimed_asr_meaning(self):
        with zipfile.ZipFile(self.root/LATER) as z:
            d={n:z.read(n) for n in z.namelist()}
        name="session_04_speech_visual_UNVERIFIED.jsonl"
        item=json.loads(d[name]);item["meaning_verified"]=True
        d[name]=json.dumps(item).encode()
        pack(self.root/LATER,d)
        self.assertFalse(audit(self.root)["source_integrity_pass"])

if __name__=="__main__":unittest.main()
