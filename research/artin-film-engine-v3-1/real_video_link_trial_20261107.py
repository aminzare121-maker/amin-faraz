"""Try the user's UUpload shared link with the existing Artin V3.2 splitter.
Ephemeral GitHub runner ONLY: never commits or uploads original media, frames, or transcript.
"""
from __future__ import annotations
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

MAX_BYTES=650*1024*1024
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"

def allowed(url: str) -> bool:
    parsed=urllib.parse.urlparse(url)
    host=(parsed.hostname or "").lower()
    return parsed.scheme=="https" and (host=="uupload.ir" or host.endswith(".uupload.ir"))

def source_candidates(page: str, base: str) -> list[str]:
    page=html.unescape(page).replace("\\/","/")
    found=[]
    expressions=[
        r'''(?:href|src|content|file|url)\s*[:=]\s*["']([^"']+)["']''',
        r'''https?://[^\s"'<>\\]+''',
    ]
    for pattern in expressions:
        for m in re.finditer(pattern,page,re.I):
            raw=m.group(1) if m.lastindex else m.group(0)
            candidate=urllib.parse.urljoin(base,raw.strip())
            if allowed(candidate) and (".mp4" in urllib.parse.urlparse(candidate).path.lower()
                                       or "/files/" in urllib.parse.urlparse(candidate).path.lower()):
                if candidate not in found:
                    found.append(candidate)
    return found[:20]

def fetch_to_file(url: str, file: Path, *, referer: str | None = None) -> dict:
    if not allowed(url):
        raise ValueError("Disallowed media host")
    headers={"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"]=referer
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=50) as r:
        final_url=r.geturl()
        if not allowed(final_url):
            raise ValueError("Unexpected redirect host")
        ct=(r.headers.get("Content-Type") or "").lower()
        initial=r.read(2048)
        if "text/html" in ct or initial.lstrip().startswith(b"<!DOCTYPE") or initial.lstrip().startswith(b"<html"):
            page=(initial+r.read(2*1024*1024)).decode("utf-8","replace")
            return {"type":"html","status":r.status,"candidates":source_candidates(page,final_url)}
        is_mp4=b"ftyp" in initial[:128] or "video/" in ct or "application/octet-stream" in ct
        if not is_mp4:
            return {"type":"unknown","status":r.status,"content_type":ct}
        n=0
        with file.open("wb") as f:
            f.write(initial); n+=len(initial)
            while True:
                chunk=r.read(1024*1024)
                if not chunk:
                    break
                n+=len(chunk)
                if n>MAX_BYTES:
                    raise ValueError("Media exceeds size safety limit")
                f.write(chunk)
        return {"type":"video","bytes":n,"status":r.status}

def process(source_url: str, root: Path) -> dict:
    media=root/"source.mp4"
    first=fetch_to_file(source_url,media)
    print("SHARE_PROBE:",first["type"],"status",first.get("status"))
    if first["type"]=="video":
        receipt=first
    elif first["type"]=="html":
        urls=first["candidates"]
        print("HTML_MEDIA_CANDIDATES:",len(urls))
        receipt=None
        for candidate in urls:
            try:
                test=fetch_to_file(candidate,media,referer=source_url)
                if test["type"]=="video":
                    receipt=test
                    break
            except Exception as e:
                print("MEDIA_CANDIDATE_BLOCKED:",type(e).__name__)
        if receipt is None:
            raise RuntimeError("No downloadable original MP4 could be extracted from share page")
    else:
        raise RuntimeError("Source URL returned neither an MP4 nor a share page")
    print("ORIGINAL_BYTES:",receipt["bytes"])
    command=[sys.executable,"artin_film_pipeline.py","prepare","--video",str(media),
             "--out",str(root/"result"),"--workers","2","--frames-per-chunk","0",
             "--chunk-seconds","300"]
    subprocess.run(command,check=True)
    subprocess.run([sys.executable,"artin_film_pipeline.py","remux","--out",
                    str(root/"result"),"--video-output",str(root/"chapters.mp4")],check=True)
    manifest=json.loads((root/"result"/"manifest.json").read_text(encoding="utf-8"))
    verified=json.loads((root/"result"/"chunk_order_verified.json").read_text(encoding="utf-8"))
    chunks=manifest["chunks"]
    n=len(chunks)
    batches=verified.get("batches") or manifest.get("batches") or []
    print("ARTIN_REAL_MEDIA_SPLIT_SUCCESS")
    print("GLOBAL_CHUNKS:",n)
    print("BATCHES:",len(batches) if batches else (n+17)//18)
    print("LAST_CHUNK_CORE_SECONDS:",round(chunks[-1]["core_end"]-chunks[-1]["core_start"],3))
    print("VERIFICATION:",verified.get("no_missing_or_duplicate_numbers"))
    assert verified.get("no_missing_or_duplicate_numbers") is True
    return {"original_bytes":receipt["bytes"],"chunks":n,
            "batches":len(batches) if batches else (n+17)//18,
            "last_chunk_seconds":round(chunks[-1]["core_end"]-chunks[-1]["core_start"],3),
            "verified":True,"analysis_of_speech_or_trading":"NOT_RUN"}

def main() -> int:
    config=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    url=config["share_url"]
    if not allowed(url):
        raise ValueError("Only HTTPS uupload.ir share links allowed")
    with tempfile.TemporaryDirectory(prefix="artin_ephemeral_") as tmp:
        try:
            result=process(url,Path(tmp))
        except Exception as e:
            print("ARTIN_REAL_MEDIA_TRIAL_BLOCKED:",type(e).__name__,str(e)[:240])
            summary=os.environ.get("GITHUB_STEP_SUMMARY")
            if summary:
                with open(summary,"a",encoding="utf-8") as f:
                    f.write("## Real-media trial: BLOCKED\nOriginal media was not successfully split; no processing claim.\n")
            return 1
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:
            f.write("## Artin V3.2 real-video technical split: PASS\n\n")
            f.write("| Metric | Observed |\n|---|---|\n")
            for key,value in result.items():
                f.write("| "+str(key)+" | "+str(value)+" |\n")
            f.write("\nOriginal video and derived clips stayed in ephemeral runner storage and were deleted. No speech/vision model or trading engine ran.\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
