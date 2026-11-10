"""Expand only documented ambiguous visual references; no ASR/OCR or trading."""
import hashlib,json,os,pathlib,subprocess,zipfile
import imageio_ffmpeg
CASES={
2:(13691146531,"60e909d7a3acb57a5e80b689e6dac576db479c04795afc413229d7492afc7748",[926,935,1513,1518,1523,3918,3930,3948],"Check nominal-value examples and the explicit position-size formula correction without replacing speech with arithmetic guesses"),
18:(13693801002,"5b896a56747b6e1d5ab5c01c6d01dcce7ed396a471dfa170cbad3193aaecd6ed",[3084,3090,3093,3140],"Separate prior zone formation from later touch and fill in the same bullish FVG; keep the later different example distinct"),
7:(13690343720,"ae50c37d83ca2b92ea0c27ba429247878e5edd01a44c0596ca50d85cac335ce1",[4315,4337,4353],"Match the live EURUSD and DXY chart switch; prior PDF frames do not show this example"),
8:(13689654008,"0b55bcbf9714ff586d232abbd0b2d1070231bb055a5775a62347cd146253a2f8",[4218,4298,4337,4399],"Check written comparison bases and wage equality during transcript direction disagreement; do not infer unheard speech"),
10:(13689764605,"1f63842913a250bf1fe81bab3dc7dcc90f282c4026ee41ac88cc31687b8e65ea",[2448,2448.5,2449],"Verify final indicator timeframe selection without conflating it with entry chart timeframe"),
12:(13690508501,"200da08226639095044fb0ebb3f3508b7fd82ac770f81bfb87ec789578057805",[2335,2346,2401,2443],"Match explicit doubt and confidence labels to selected candles without inferring from engulf names"),
17:(13692620657,"4e66db074ee12a417d2152e53f83de94600592a0a0969bcdd5488fc2f27c464b",[518,528,535],"Verify example RR drawing at time of explanation instead of borrowing later edited coordinates"),
9:(13689564024,"dd78ff36ce267d4b1735aa6ce1d2a591371e82cd05461a6467d5589149908e8e",[2299,2320,2629,2749,2772],"Match inflation level versus change in increments in the classroom role-play; do not infer exact weights or unheard speech"),
23:(13692425864,"403dca1d3fc90f739a9d6fe0006c87606cd7ffa5f026f5f9cd3e8d5644b47e0a",[2649,2670,2697],"Introductory decision-tree branches and limits of later complete-tree promise"),
21:(13691563117,"f63690d402f299d297110ff815b7fee9fcae8bb4927b9084e401488efaa3a1a3",[524,526,528,530,532],"Identify the explicitly pointed origin of the Punch impulse before stop-tool editing; later stop coordinates do not prove leg endpoints"),
24:(13692025289,"7f82b19f0c19fd38daaf118e7bf5a53bf6aa9ac22f12e29a7f18ad4ad2f6f759",[1118,1125,1135],"Actual chart distance display during spoken unit disagreement"),
1:(13690841735,"b23c618eb63af8c91c77d9a451411091bf7f5a57edbc0b6fdc20e01b86bcc8ff",[4225,4287,4324],"Match three newly recovered exact text-and-time anchored relative-strength examples; no speech models or repeated OCR"),
19:(13691172465,"164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03",[4235,4288,4304],"Three completed drawings and Star SELL half-leg ambiguity"),
20:(13690608979,"6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9",[4203,4209,4215,4221,4233,4235,4238],"Pointed Stop/Punch variants and between-zone exception"),
22:(13691432406,"8214f077a05969730c21015dc0f24c489835a9d1a9e9e3be4f73cca1000992ca",[4873,4878,4881,4883,4885],"Resolve the changed Three window and the reported half-leg failure; existing sparse frames do not identify the selected triplet")}
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
  if n in (2,18) and not names:
   # Some recovered source archives use a different member basename.
   # Require one MP4 only; the immutable expected source SHA below remains mandatory.
   names=[s for s in z.namelist() if pathlib.PurePosixPath(s).suffix.lower()==".mp4"]
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
