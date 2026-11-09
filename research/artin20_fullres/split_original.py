#!/usr/bin/env python3
"""Lossless member-wise recovery of oversize Artin queue-20 fullres-chat source.
Original GitHub artifact ZIP is immutable; output is independently verifiable shards.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys,zipfile

REPO="aminzare121-maker/amin-faraz"
ARTIFACT_ID=13676681984
ROOT=Path("artin20_fullres_recovery")
OUT=ROOT/"private_shards"
SHARD_MAX=120*1024*1024
MAX_SHARDS=16

def sha_file(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for block in iter(lambda:f.read(2*1024*1024),b""):h.update(block)
    return h.hexdigest()

def main():
    ROOT.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    src=ROOT/"ORIGINAL_FULLRES_CHAT_GITHUB_ARTIFACT.zip"
    if not src.exists():
        with src.open("wb") as out:
            r=subprocess.run(["gh","api",f"repos/{REPO}/actions/artifacts/{ARTIFACT_ID}/zip"],
              stdout=out,stderr=subprocess.PIPE,timeout=900)
        if r.returncode:raise RuntimeError("ORIGINAL_ARTIFACT_FETCH_FAILED_"+str(r.returncode)+" "+r.stderr.decode("utf8","replace")[:100])
    report={"schema":"ARTIN_20_FULLRES_RECOVERY_PARTS_V1",
        "artifact_id":ARTIFACT_ID,"original_archive_bytes":src.stat().st_size,
        "original_archive_sha256":sha_file(src),
        "original_files_unmodified":True,"sha256_per_original_file_verified":True,
        "original_members":[],"shards":[]}
    active=None;archive=None;sum_current=0;partno=-1;current_meta=None
    def new_shard():
        nonlocal active,archive,sum_current,partno,current_meta
        if active is not None:
            active.close()
            if zipfile.ZipFile(archive).testzip() is not None:raise RuntimeError("SHARD_CRC_ERROR")
            current_meta["size_bytes"]=archive.stat().st_size
            current_meta["zip_sha256"]=sha_file(archive)
            report["shards"].append(current_meta)
        partno+=1
        if partno>=MAX_SHARDS:raise RuntimeError("TOO_MANY_SHARDS")
        archive=OUT/f"part_{partno:02d}.zip"
        active=zipfile.ZipFile(archive,mode="w",compression=zipfile.ZIP_STORED,allowZip64=True)
        current_meta={"part":partno,"name":archive.name,"members":0,"source_uncompressed_bytes":0}
        sum_current=0
    try:
        with zipfile.ZipFile(src) as z:
            names=[i for i in z.infolist() if not i.is_dir()]
            if not names:raise ValueError("NO_ORIGINAL_IMAGES_OR_FILES_FOUND")
            for item in names:
                if item.file_size>SHARD_MAX:raise ValueError("SINGLE_ORIGINAL_IMAGE_EXCEEDS_SHARD_LIMIT")
                if active is None or (sum_current+item.file_size>SHARD_MAX and sum_current>0):new_shard()
                contents=z.read(item) # Validates original ZIP CRC
                digest=hashlib.sha256(contents).hexdigest()
                active.writestr(item.filename,contents)
                item_meta={"path":item.filename,"size_bytes":len(contents),
                           "sha256":digest,"part":partno}
                report["original_members"].append(item_meta)
                sum_current+=len(contents)
                current_meta["members"]+=1
                current_meta["source_uncompressed_bytes"]+=len(contents)
    finally:
        if active is not None:
            active.close()
            if archive and archive.exists() and (not report["shards"] or report["shards"][-1].get("name")!=archive.name):
                if zipfile.ZipFile(archive).testzip() is not None:raise RuntimeError("LAST_SHARD_CRC_ERROR")
                current_meta["size_bytes"]=archive.stat().st_size
                current_meta["zip_sha256"]=sha_file(archive)
                report["shards"].append(current_meta)
    # Test every exact source file sha256 against output shards.
    for part in report["shards"]:
        with zipfile.ZipFile(OUT/part["name"]) as z:
            if z.testzip() is not None:raise RuntimeError("SPLIT_ZIP_CORRUPTION")
            checks=[m for m in report["original_members"] if m["part"]==part["part"]]
            for m in checks:
                if hashlib.sha256(z.read(m["path"])).hexdigest()!=m["sha256"]:
                    raise RuntimeError("SOURCE_MEMBER_SHA_MISMATCH")
    report["original_member_count"]=len(report["original_members"])
    report["part_count"]=len(report["shards"])
    report["source_uncompressed_bytes"]=sum(x["size_bytes"] for x in report["original_members"])
    report["original_images_and_files_preserved"]=len(report["original_members"])
    report["teacher_semantic_verified"]=False
    (ROOT/"fullres_split_manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print("ARTIN20_FULLRES_SPLIT_REPORT="+json.dumps({
        "status":"SOURCE_EXACT_BYTES_REASSEMBLABLE",
        "source_archive_sha256":report["original_archive_sha256"],
        "original_archive_bytes":report["original_archive_bytes"],
        "original_member_count":report["original_member_count"],
        "part_count":report["part_count"],
        "source_uncompressed_bytes":report["source_uncompressed_bytes"],
        "shards":[{"name":s["name"],"bytes":s["size_bytes"],"members":s["members"]} for s in report["shards"]]
    }),flush=True)

if __name__=="__main__":main()
