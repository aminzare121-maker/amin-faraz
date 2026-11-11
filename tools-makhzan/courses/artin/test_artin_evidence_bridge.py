import hashlib,json,tempfile,unittest
from pathlib import Path
from artin_evidence_bridge import adapt
class BridgeTests(unittest.TestCase):
 def test_fail_closed_and_valid(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t); sources={}
   for k in ("speech","chat","board","frames"):
    p=root/(k+".json");p.write_text(json.dumps([{"start":0,"text":"نمونه"}]),encoding="utf-8")
    sources[k]={"path":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
   m={"entry":"0010","course":"artin-course-001","sources":sources}
   result=adapt(m,root)
   self.assertEqual(result["verified_executable_rules"],[])
   self.assertFalse(result["teacher_semantics_verified"])
   self.assertEqual(result["questions"],[])
   (root/"chat.json").write_text("[]",encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):adapt(m,root)
   del sources["board"]
   with self.assertRaisesRegex(ValueError,"four original"):adapt(m,root)
if __name__=="__main__":unittest.main()
