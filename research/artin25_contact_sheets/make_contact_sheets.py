#!/usr/bin/env python3
"""Contact sheets from original bytes in Artin 66 frame archive (not generated image approximations)."""
import io,os,json,base64,zipfile,hashlib,subprocess,pathlib,math
from PIL import Image,ImageDraw,ImageFont
OUT=pathlib.Path("artin25_contact_sheets_output");OUT.mkdir(exist_ok=True)
REPO="aminzare121-maker/amin-faraz";ART=13693914107
p=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{ART}/zip"],capture_output=True,timeout=300)
if p.returncode:raise RuntimeError(p.stderr.decode("utf8","replace")[:200])
with zipfile.ZipFile(io.BytesIO(p.stdout)) as z:
    n=[x for x in z.namelist() if x.endswith("66_original_source_frames.zip")]
    if len(n)!=1:raise RuntimeError("Nested original frame ZIP missing")
    nested=z.read(n[0])
with zipfile.ZipFile(io.BytesIO(nested)) as z:
    manifest=json.loads(z.read("frame_window_manifest.json"))
    if len(manifest)!=66:raise RuntimeError("Must have exactly 66 windows")
    index=[]
    for k,rec in enumerate(manifest):
        frame=next((x for x in rec["frames"] if x["source_original_path"].startswith("board/")),rec["frames"][0])
        b=z.read(frame["archive_path"])
        if hashlib.sha256(b).hexdigest()!=frame["source_image_sha256"]:raise RuntimeError("source image SHA mismatch")
        im=Image.open(io.BytesIO(b)).convert("RGB")
        index.append({"global_position":k+1,"seq":rec["session"],"time":rec["speech_time_seconds"],
           "original_source_path":frame["source_original_path"],
           "image_sha256":frame["source_image_sha256"],
           "image_delta":frame["abs_delta_seconds"],
           "speech_exact":rec["speech_exact"],"image":im})
    SHEET_W,SHEET_H=1380,720
    CW,CH=460,360
    n=0
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",20)
    for i in range(0,len(index),6):
        group=index[i:i+6]
        sheet=Image.new("RGB",(SHEET_W,SHEET_H),(250,250,250))
        draw=ImageDraw.Draw(sheet)
        for j,r in enumerate(group):
            x=(j%3)*CW;y=(j//3)*CH
            label=f"{r['global_position']:02d}  Seq {r['seq']:02d}   time {r['time']:.1f}s   distance {r['image_delta']:.1f}s"
            draw.rectangle((x,y,x+CW,y+CH),outline=(110,110,110),width=1)
            draw.text((x+8,y+4),label,font=font,fill=(20,20,20))
            im=r.pop("image")
            im.thumbnail((CW-16,CH-45))
            xx=x+int((CW-im.width)/2);yy=y+35+int((CH-45-im.height)/2)
            sheet.paste(im,(xx,yy))
        name=f"Artin_frames_atlas_{i//6+1:02d}.jpg"
        buf=io.BytesIO();sheet.save(buf,format="JPEG",quality=78,optimize=True)
        data=buf.getvalue()
        (OUT/name).write_bytes(data)
        print("ARTIN_CONTACT_SHEET="+json.dumps({"sheet":i//6+1,"window_ids":[x["global_position"] for x in group],"base64":base64.b64encode(data).decode("ascii")}),flush=True)
        n+=1
    (OUT/"contact_sheet_index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding="utf8")
    summary={"original_windows":len(index),"contact_sheets":n,
      "all_sha256_verified":True,"semantic_rules_certified":0,
      "original_frame_artifact_id":ART,
      "source_speech_has_provenance":True}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print("ARTIN_ATLAS_SUMMARY="+json.dumps(summary),flush=True)
