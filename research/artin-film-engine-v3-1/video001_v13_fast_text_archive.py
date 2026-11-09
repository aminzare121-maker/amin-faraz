#!/usr/bin/env python3
"""Append-safe, byte-preserving, text-only archiver for Artin V13 output.
Does NOT claim completeness of transcription/OCR/visual semantics. This starts
only when source text outputs are already available; it does NOT process video.
"""
from __future__ import annotations
import argparse, hashlib, json, time, zipfile
from pathlib import Path

ACCEPT={'.json','.jsonl','.txt','.md','.csv','.tsv','.srt','.vtt'}
def hash_bytes(data):return hashlib.sha256(data).hexdigest()

def archive_video(source_zip:Path, derived_zip:Path, video_number:int, destination:Path):
    source_zip=source_zip.resolve(); derived_zip=derived_zip.resolve();destination=destination.resolve()
    if not (source_zip.is_file() and derived_zip.is_file()):raise FileNotFoundError('SOURCE_ARCHIVE_MISSING')
    if destination.exists():raise FileExistsError('NEVER_OVERWRITE_PREVIOUS_BEHROOZ_ARCHIVE')
    if video_number not in range(1,10000):raise ValueError('INVALID_VIDEO_ID')
    begin=time.monotonic(); out_entries=[]
    temp=destination.with_name(destination.name+'.partial')
    if temp.exists():raise FileExistsError('STAGED_ARCHIVE_ALREADY_EXISTS')
    temp.parent.mkdir(parents=True,exist_ok=True)
    try:
        with zipfile.ZipFile(source_zip) as raw, zipfile.ZipFile(derived_zip) as dr, zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as target:
            # Preserve every original raw extracted *text* file byte-for-byte.
            names=raw.namelist()
            if len(names)!=len(set(names)) or raw.testzip():raise ValueError('CORRUPT_OR_DUPLICATE_RAW_MEMBER')
            if not names:raise ValueError('EMPTY_RAW_ARCHIVE')
            for name in names:
                if name.endswith('/'):continue
                ext=Path(name).suffix.lower()
                if ext not in ACCEPT:raise ValueError('NON_TEXT_SOURCE_MEMBER:'+name)
                data=raw.read(name)
                entry='RAW_UNMODIFIED/'+name
                target.writestr(entry,data)
                out_entries.append({'path':entry,'bytes':len(data),'sha256':hash_bytes(data),'kind':'raw'})
            prefix=f'DERIVED_NOT_RAW/VIDEO_{video_number:02d}/'
            deriv=[n for n in dr.namelist() if n.startswith(prefix) and not n.endswith('/')]
            if not deriv:raise ValueError('MISSING_SEPARATE_DERIVED_TEXT_SIDECARS')
            for name in deriv:
                if Path(name).suffix.lower() not in ACCEPT:raise ValueError('NON_TEXT_DERIVED_MEMBER:'+name)
                data=dr.read(name);target.writestr(name,data)
                out_entries.append({'path':name,'bytes':len(data),'sha256':hash_bytes(data),'kind':'derived_not_raw'})
            receipt={'schema':'BEHROOZ_V13_ARCHIVE_TEXT_ONLY_NONDESTRUCTIVE_V1','video':video_number,
              'raw_sha256':hash_bytes(source_zip.read_bytes()),'raw_file_count':len(names),
              'derived_file_count':len(deriv),'source_semantics_human_verified':False,
              'runtime_limit_seconds':60,'entries':out_entries}
            target.writestr('ARCHIVE_PROVENANCE_MANIFEST.json',json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf-8'))
        # Read the output back and verify that every raw byte is identical.
        with zipfile.ZipFile(temp) as z:
            if z.testzip():raise ValueError('FINAL_ZIP_CRC_FAILED')
            for x in out_entries:
                if hash_bytes(z.read(x['path']))!=x['sha256']:raise ValueError('FINAL_ZIP_SHA256_FAILED:'+x['path'])
        temp.replace(destination)
    finally:
        if temp.exists():temp.unlink()
    duration=round(time.monotonic()-begin,4)
    return {'video':video_number,'seconds':duration,'met_under_60_seconds':duration<60,
            'raw_files_kept':len(names),'derived_files_kept':len(deriv),
            'zip_bytes':destination.stat().st_size,'zip_sha256':hash_bytes(destination.read_bytes()),
            'coverage_verified':False,'no_media_in_archive':True,'no_original_rewritten':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True)
    p.add_argument('--derived',type=Path,required=True)
    p.add_argument('--video',type=int,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(archive_video(a.raw,a.derived,a.video,a.out),ensure_ascii=False))