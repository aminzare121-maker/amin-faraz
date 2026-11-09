#!/usr/bin/env python3
"""Read a bounded sample of actual original board frames from GitHub Actions (no reinterpretation)."""
import os,subprocess,io,zipfile,json,re,sys,pathlib,base64
ARTIFACTS={12:13666352041,14:13667767654,18:13671883841,24:13682220643}
target={12:2294.42,14:973.8,18:822.99,24:3610.07}
for sequence,artifact in ARTIFACTS.items():
    p=subprocess.run(["gh","api",f"repos/aminzare121-maker/amin-faraz/actions/artifacts/{artifact}/zip"],capture_output=True,timeout=300)
    if p.returncode:
        print("BOARD_FETCH_ERROR",sequence,p.stderr.decode("utf8","replace")[:300],flush=True);continue
    z=zipfile.ZipFile(io.BytesIO(p.stdout))
    names=[i.filename for i in z.infolist() if i.filename.lower().endswith((".jpg",".jpeg",".png",".webp"))]
    print("BOARD_MEMBERS",json.dumps({"seq":sequence,"artifact":artifact,"count":len(names),"sample":names[:6],"last":names[-4:]}),flush=True)
    if not names:continue
    candidates=[]
    for n in names:
        # Avoid inferring timestamps unless an explicit numeric time can be parsed from the exact filename.
        all_nums=re.findall(r"_t(\d{10,12})_",pathlib.Path(n).stem)
        times=[int(num)/1000 for num in all_nums if int(num)/1000<8000]
        if times:
            candidates.append((min(abs(t-target[sequence]) for t in times),n))
    selection=[name for _,name in sorted(candidates)[:2]] if candidates else names[:2]
    print("FRAME_SELECTED",json.dumps({"seq":sequence,"time_target":target[sequence],"heuristic_only":True,"paths":selection}),flush=True)
    # Log only base64 of downsized JPEGs, not full confidential source data.
    from PIL import Image
    for idx,n in enumerate(selection):
        b=z.read(n)
        im=Image.open(io.BytesIO(b)).convert("RGB"); im.thumbnail((960,590))
        out=io.BytesIO();im.save(out,format="JPEG",quality=71,optimize=True)
        print("FRAME_BASE64="+json.dumps({"seq":sequence,"path":n,"dimensions":im.size,"base64":base64.b64encode(out.getvalue()).decode("ascii")}),flush=True)
