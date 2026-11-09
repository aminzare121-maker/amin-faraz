#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V13 active remote-source receiver using the tested one-pass image preparation mode.

SOURCE ONCE. Stream original bytes, verify MP4 header and SHA256; no re-encode,
redirection to arbitrary hosts or silent substitution. Never print raw media,
teacher speech or student chat; no production data mutation.
"""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import time
import urllib.parse
import urllib.request
from artin_ephemeral_remote_ingest import get_direct_url
from video001_v13_source_once import prepare

MAX_BYTES=600*1024*1024

def _allowed_https(url):
    p=urllib.parse.urlsplit(url)
    host=(p.hostname or '').lower()
    if p.scheme!='https' or not (
        host=='my.uupload.ir' or
        (host.startswith('s') and host.endswith('.uupload.ir'))):
        raise ValueError('Only HTTPS original video URLs from user-supplied Uupload domain')
    if p.username or p.password or p.port not in (None,443):
        raise ValueError('Unexpected movie-host credentials/port')
    return p

class SourceRedirectSafe(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        _allowed_https(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download_once(original,output):
    """Stream original user movie once; do not use read_bytes() for a 200MB video."""
    _allowed_https(original)
    request=urllib.request.Request(original,headers={'User-Agent':'Mozilla/5.0'})
    opener=urllib.request.build_opener(SourceRedirectSafe)
    h=hashlib.sha256()
    total=0
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with opener.open(request,timeout=120) as response, output.open('wb') as out:
        if response.status!=200:
            raise RuntimeError('Full original MP4 download did not return HTTP 200')
        claimed=response.headers.get('Content-Length')
        if claimed and int(claimed)>MAX_BYTES:
            raise ValueError('Original film exceeds safe runner capacity: no truncation')
        first=response.read(64)
        if b'ftyp' not in first[:24]:
            raise ValueError('Original server returned non-MP4 bytes: refusing source')
        out.write(first);h.update(first);total=len(first)
        while True:
            part=response.read(1024*1024)
            if not part:break
            total+=len(part)
            if total>MAX_BYTES:
                raise ValueError('Original film too large: no truncation')
            out.write(part);h.update(part)
    if total<1024 or claimed and int(claimed)!=total:
        raise ValueError('Incomplete original MP4 download')
    return total,h.hexdigest()

def remote_prepare(request_file,out):
    job=json.loads(Path(request_file).read_text(encoding='utf8'))
    if job.get('schema')!='video001_fast_source_request_v1':
        raise ValueError('Source request schema mismatch')
    share=job.get('source_page')
    if not isinstance(share,str) or not share:
        raise ValueError('User-provided original movie URL required')
    p=_allowed_https(share)
    expected=job.get('expected_sha256')
    if expected is not None and (
        not isinstance(expected,str) or len(expected)!=64 or
        any(c not in '0123456789abcdef' for c in expected)):
        raise ValueError('User-specified expected source hash must be SHA256 or null')
    # The public share page may expire. Never silently switch to a different
    # movie when there is no valid source: report explicit SOURCE_UNAVAILABLE.
    if p.hostname=='my.uupload.ir':
        # Intermittent Uupload share pages sometimes omit the actual MP4 link.
        # Retry only this transient lookup. Never substitute a different movie,
        # alter the expected SHA, or mislabel missing media as a successful run.
        direct=None
        for attempt in range(4):
            try:
                direct,_=get_direct_url(share)
                _allowed_https(direct)
                break
            except (ValueError,OSError) as exc:
                if attempt==3:
                    raise RuntimeError(
                        'SOURCE_UNAVAILABLE: user video page supplied no usable '
                        'original MP4 after four source-verified attempts') from exc
                pause=(2,5,10)[attempt]
                print('VIDEO001_SOURCE_LINK_RETRY='+json.dumps({
                    'attempt':attempt+1,'next_delay_seconds':pause,
                    'status':'TRANSIENT_SOURCE_LINK_UNAVAILABLE'}),flush=True)
                time.sleep(pause)
    else:
        direct=share
    _allowed_https(direct)
    out=Path(out).resolve()
    film=out/'private_original_user_movie.mp4'
    try:
        size,sha=download_once(direct,film)
        if expected is not None and expected!=sha:
            raise ValueError('User-supplied MP4 source SHA differs from registered version')
        result=prepare(film,out/'prepared',expected_sha=sha,
            audio_workers=int(job.get('audio_workers',17)),
            ocr_workers=int(job.get('ocr_workers',16)),
            sample_seconds=int(job.get('sample_seconds',30)))
        print('VIDEO001_REMOTE_SOURCE_ONCE_OK='+json.dumps({
            'sha256':sha,'bytes':size,'prep_seconds':result['elapsed_seconds'],
            'all_original_evidence_present':result['source_integrity_verified'],
            'v13_one_pass_visual_enabled':result['v13_one_pass_visual_enabled'],
            'legacy_archives_untouched':result['v13_legacy_archives_overwritten'] is False,
            'same_original_mp4_used_for_audio_images':True}),flush=True)
        return result
    finally:
        # Private original is not retained in GitHub Actions artifacts.
        film.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--request',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    remote_prepare(a.request,a.out)

if __name__=='__main__':main()
