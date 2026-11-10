"""Owner-approved three private audio excerpts. No ASR/OCR or trading."""
import hashlib,json,os,pathlib,subprocess,wave,zipfile
import imageio_ffmpeg
CASES={
19:(13691172465,"164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03",4458,4480),
21:(13691563117,"f63690d402f299d297110ff815b7fee9fcae8bb4927b9084e401488efaa3a1a3",532,590),
24:(13692025289,"7f82b19f0c19fd38daaf118e7bf5a53bf6aa9ac22f12e29a7f18ad4ad2f6f759",1108,1148)}
n=int(os.environ["SEQUENCE"]);aid,expected,start,end=CASES[n]
work=pathlib.Path("private");work.mkdir(exist_ok=True)
out=pathlib.Path("review_audio");out.mkdir(exist_ok=True)
with open(work/"source.zip","wb") as f:
 p=subprocess.run(["gh","api",f"repos/aminzare121-maker/amin-faraz/actions/artifacts/{aid}/zip"],stdout=f,stderr=subprocess.PIPE,timeout=600)
if p.returncode:raise RuntimeError("EXISTING_SOURCE_READ_FAILED")
h=hashlib.sha256()
with zipfile.ZipFile(work/"source.zip") as z:
 names=[s for s in z.namelist() if pathlib.PurePosixPath(s).name=="original.mp4"]
 if len(names)!=1:raise ValueError("ORIGINAL_NOT_UNIQUE")
 with z.open(names[0]) as src,open(work/"source.mp4","wb") as dst:
  for b in iter(lambda:src.read(4194304),b""):h.update(b);dst.write(b)
if h.hexdigest()!=expected:raise ValueError("SOURCE_SHA_MISMATCH")
audio=out/f"lesson{n}_{start}_{end}_original.wav"
p=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-nostdin","-v","error","-ss",str(start),"-i",str(work/"source.mp4"),"-t",str(end-start),"-map","0:a:0","-ac","1","-ar","16000","-c:a","pcm_s16le",str(audio)],capture_output=True,timeout=90)
if p.returncode or not audio.exists():raise RuntimeError("AUDIO_EXTRACT_FAILED")
with wave.open(str(audio),"rb") as w:
 duration=w.getnframes()/w.getframerate()
 if w.getnchannels()!=1 or w.getframerate()!=16000 or w.getsampwidth()!=2 or abs(duration-(end-start))>.1:raise ValueError("AUDIO_FORMAT_DURATION_MISMATCH")
receipt=dict(sequence=n,source_artifact_id=aid,source_sha256=expected,start_seconds=start,end_seconds=end,
 duration_seconds=duration,file=audio.name,audio_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
 models_executed=0,direct_listening_completed=False,semantic_verified=False,original_source_preserved=True,orders_placed=0)
(out/"audio_evidence_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
print(json.dumps(dict(sequence=n,source_sha_verified=True,audio_seconds=duration,models_executed=0,semantic_verified=False)))
