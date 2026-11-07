#!/usr/bin/env python3
"""Ephemeral access to a user-supplied Uupload video for the private Artin pipeline.
Never commit or publish the video, audio, names, or original transcripts.
"""
from __future__ import annotations
import hashlib
import html.parser
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

LIMIT=600*1024*1024

class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag not in ("a","source","video"):return
        at=dict(attrs); u=at.get("href") or at.get("src")
        if u:self.links.append(u)

def get_direct_url(page):
    req=urllib.request.Request(page,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=35) as response:
        if "html" not in (response.headers.get("Content-Type") or "").lower():
            raise ValueError("Expected Uupload download HTML page, not direct bytes")
        html=response.read(1_000_000).decode("utf-8","replace")
        base=response.url
    parser=Links();parser.feed(html)
    candidates=[]
    for link in parser.links:
        u=urllib.parse.urljoin(base,link)
        sp=urllib.parse.urlsplit(u)
        if sp.scheme!="https" or not (sp.hostname or "").endswith(".uupload.ir"):
            continue
        if (sp.hostname or "").startswith("s") and re.search(r"\.mp4(?:$|\?)",u,re.I):
            candidates.append(u)
    for url in dict.fromkeys(candidates):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Range":"bytes=0-63"})
        with urllib.request.urlopen(req,timeout=30) as q:
            magic=q.read(64)
            if b"ftyp" in magic[:24]:
                return url, q.headers.get("Content-Range")
    raise ValueError("No real MP4 link found in the Uupload page")

def download(url, dest):
    h=hashlib.sha256(); size=0
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(request,timeout=110) as response,open(dest,"wb") as out:
        if response.status!=200:
            raise ValueError(f"Need status 200 for full download; got {response.status}")
        header_len=response.headers.get("Content-Length")
        if header_len and int(header_len)>LIMIT:raise ValueError("Video too large for this isolated runner")
        while True:
            piece=response.read(1024*1024)
            if not piece:break
            size+=len(piece)
            if size>LIMIT:raise ValueError("Video exceeded size safety cap")
            out.write(piece);h.update(piece)
    if size<1024 or b"ftyp" not in Path(dest).read_bytes()[:24]:
        raise ValueError("Downloaded payload is not an MP4")
    return size,h.hexdigest()

def main():
    page=os.environ.get("TEACHER_VIDEO_PAGE")
    if not page or not page.startswith("https://my.uupload.ir/p/"):
        raise ValueError("Only supplied Uupload share pages are accepted")
    output=Path(os.environ.get("ARTIN_PRIVATE_RUNNER_DIR","/tmp/artin_teacher_private"))
    output.mkdir(parents=True,exist_ok=True)
    direct,range_header=get_direct_url(page)
    video=output/"source.mp4"
    size,digest=download(direct,video)
    proc=subprocess.run(["ffprobe","-v","error","-show_entries",
                    "format=duration:stream=codec_type,width,height,codec_name",
                    "-of","json",str(video)],check=True,capture_output=True,text=True)
    probe=json.loads(proc.stdout)
    duration=float(probe["format"]["duration"])
    result={"source":"USER_SUPPLIED_UUPLOAD","file_bytes":size,"video_sha256":digest,
            "duration_seconds":round(duration,3),"streams":probe.get("streams",[]),
            "media_download":"FULL_FILE_VERIFIED_EPHEMERAL_ONLY",
            "teacher_rules_verified":False}
    (output/"source_probe.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("ARTIN_FULL_VIDEO_PROBE="+json.dumps(result,ensure_ascii=False),flush=True)
    script=Path(__file__).parent/"artin_film_pipeline.py"
    chunks=output/"processed"
    subprocess.run([sys.executable,str(script),"prepare","--video",str(video),
                    "--out",str(chunks),"--workers","4","--frames-per-chunk","2"],check=True)
    m=json.loads((chunks/"manifest.json").read_text(encoding="utf8"))
    result.update({"parts":len(m["chunks"]),"batch_count":m["batch_count"],
                   "batches":[{"batch":b["batch"],"slots":b["slots_in_order"],
                              "global_indices":b["global_indices"]} for b in m["batches"]],
                   "parts_ready":m["parts_ready"],
                   "short_final_seconds":round(m["chunks"][-1]["core_end"]-
                                                m["chunks"][-1]["core_start"],3),
                   "all_hashed":all("clip_sha256" in c for c in m["chunks"]),
                   "frames":sum(len(c.get("frames",[])) for c in m["chunks"]),
                   "speech_transcribed":False,"visual_semantics_verified":False})
    print("ARTIN_PRIVATE_VIDEO_EXTRACTION="+json.dumps(result,ensure_ascii=False),flush=True)
    (output/"extraction_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    # Trim private paths / source URL from artifact outputs.
    m.pop("video_path_private",None)
    (output/"artifact_manifest_redacted.json").write_text(
        json.dumps(m,ensure_ascii=False,indent=2),encoding="utf8")

if __name__=="__main__":
    main()
