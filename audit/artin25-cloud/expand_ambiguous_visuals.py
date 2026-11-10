"""Expand only documented ambiguous visual references; no ASR/OCR or trading."""
import hashlib,json,os,pathlib,subprocess,zipfile
import imageio_ffmpeg
CASES={
10:(13689764605,"1f63842913a250bf1fe81bab3dc7dcc90f282c4026ee41ac88cc31687b8e65ea",[2448,2448.5,2449],"Verify final indicator timeframe selection without conflating it with entry chart timeframe"),
12:(13690508501,"200da08226639095044fb0ebb3f3508b7fd82ac770f81bfb87ec789578057805",[2335,2346,2401,2443],"Match explicit doubt and confidence labels to selected candles without inferring from engulf names"),
17:(13692620657,"4e66db074ee12a417d2152e53f83de94600592a0a0969bcdd5488fc2f27c464b",[518,528,535],"Verify example RR drawing at time of explanation instead of borrowing later edited coordinates"),
9:(13689564024,"dd78ff36ce267d4b1735aa6ce1d2a591371e82cd05461a6467d5589149908e8e",[3038,3046,3053,3085,3115],"Distinguish CPI and interest-rate charts during the spoken switch; do not relabel a CPI screenshot"),
23:(13692425864,"403dca1d3fc90f739a9d6fe0006c87606cd7ffa5f026f5f9cd3e8d5644b47e0a",[2649,2670,2697],"Introductory decision-tree branches and limits of later complete-tree promise"),
21:(13691563117,"f63690d402f299d297110ff815b7fee9fcae8bb4927b9084e401488efaa3a1a3",[541,547,553,556],"One-third stop origin, marked level and nearby FVG alternative"),
24:(13692025289,"7f82b19f0c19fd38daaf118e7bf5a53bf6aa9ac22f12e29a7f18ad4ad2f6f759",[1118,1125,1135],"Actual chart distance display during spoken unit disagreement"),
1:(13690841735,"b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff",[680,1230,1390,2195,3438,3452],"Legacy first-lesson transcript unclear roles and direction-entry distinction; no model re-execution"),
19:(13691172465,"164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03",[4235,4288,4304],"Three completed drawings and Star SELL half-leg ambiguity"),
20:(13690608979,"6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9",[4203,4209,4215,4221,4233,4235,4238],"Pointed Stop/Punch variants and between-zone exception"),
22:(13691432406,"8214f077a05969730c21015dc0f24c489835a9d1a9e9e3be4f73cca1000992ca",[4521,4525,4529,4533,4537,4541,4547],"Resolve documented near-versus-far gap selection using exact pointer context; prior Three frames are preserved")}
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
  member="original_0001.mp4" if n==1 else "original.mp4"
  names=[s for s in z.namelist() if pathlib.PurePosixPath(s).name==member]
  if len(names)!=1:raise ValueError("ORIGINAL_NOT_UNIQUE")
  with z.open(names[0]) as src,open(private/"source.mp4","wb") as dst:
   for b in iter(lambda:src.read(4194304),b""):h.update(b);dst.write(b)
 if h.hexdigest()!=expected:raise ValueError("SOURCE_SHA_MISMATCH")
 images=[]
 for t in times:
  name=f"expanded_t{t:08.3f}.png";out=review/name
  p=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-nostdin","-v","error","-ss",str(t),"-i",str(private/"source.mp4"),"-frames:v","1",str(out)],capture_output=True,timeout=90)
  if p.returncode or not out.is_file():raise RuntimeError("EXPANDED_FRAME_FAILED")
  images.append(dict(file=name,original_video_seconds=t,image_sha256=hashlib.sha256(out.read_bytes()).hexdigest()))
 (review/"expanded_context_PRIVATE.json").write_text(json.dumps(dict(sequence=n,source_sha256=expected,source_artifact_id=aid,selection_reason=reason,images=images,models_executed=0,semantic_verified=False,direct_listening=False),indent=2),encoding="utf-8")
 print(json.dumps(dict(sequence=n,images_prepared=len(images),source_sha_verified=True,semantic_verified=False)))
if __name__=="__main__":main()
