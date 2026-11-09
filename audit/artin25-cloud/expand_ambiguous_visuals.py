"""Expand only documented ambiguous visual references; no ASR/OCR or trading."""
import hashlib,json,os,pathlib,subprocess,zipfile
CASES={
19:(13691172465,"164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03",[3668,3680,3695,3955,3980,4005,4410,4430,4468,4480],"Three completed drawings and Star SELL half-leg ambiguity"),
20:(13690608979,"6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9",[3948,4000,4038,4116,4204,4218,4236],"Pointed Stop/Punch variants and between-zone exception"),
22:(13691432406,"8214f077a05969730c21015dc0f24c489835a9d1a9e9e3be4f73cca1000992ca",[1405,3546,3584,4755,4874,4887],"Pre-existing-zone requirement, confirmation line and rejected Three")}
def main():
 n=int(os.environ["SEQUENCE"]);aid,expected,times,reason=CASES[n]
 if len(expected)!=64 or len(set(times))!=len(times) or any(t<0 for t in times):raise ValueError("INVALID_PLAN")
 private=pathlib.Path("private");private.mkdir(exist_ok=True)
 review=pathlib.Path("review");review.mkdir(exist_ok=True)
 with open(private/"source.zip","wb") as f:
  p=subprocess.run(["gh","api",f"repos/aminzare121-maker/amin-faraz/actions/artifacts/{aid}/zip"],stdout=f,stderr=subprocess.PIPE,timeout=600)
 if p.returncode:raise RuntimeError("EXISTING_SOURCE_READ_FAILED")
 h=hashlib.sha256()
 with zipfile.ZipFile(private/"source.zip") as z:
  names=[s for s in z.namelist() if pathlib.PurePosixPath(s).name=="original.mp4"]
  if len(names)!=1:raise ValueError("ORIGINAL_NOT_UNIQUE")
  with z.open(names[0]) as src,open(private/"source.mp4","wb") as dst:
   for b in iter(lambda:src.read(4194304),b""):h.update(b);dst.write(b)
 if h.hexdigest()!=expected:raise ValueError("SOURCE_SHA_MISMATCH")
 images=[]
 for t in times:
  name=f"expanded_t{t:08.3f}.png";out=review/name
  p=subprocess.run(["ffmpeg","-nostdin","-v","error","-ss",str(t),"-i",str(private/"source.mp4"),"-frames:v","1",str(out)],capture_output=True,timeout=90)
  if p.returncode or not out.is_file():raise RuntimeError("EXPANDED_FRAME_FAILED")
  images.append(dict(file=name,original_video_seconds=t,image_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
 (review/"expanded_context_PRIVATE.json").write_text(json.dumps(dict(sequence=n,source_sha256=expected,source_artifact_id=aid,selection_reason=reason,images=images,models_executed=0,semantic_verified=False,direct_listening=False),indent=2),encoding="utf-8")
 print(json.dumps(dict(sequence=n,images_prepared=len(images),source_sha_verified=True,semantic_verified=False)))
if __name__=="__main__":main()
