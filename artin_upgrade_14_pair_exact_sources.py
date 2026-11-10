#!/usr/bin/env python3
"""Upgrade original-MP4-derived 14-pair review to exact archived source WAV identity.

Only source AUDIO SHA-256 and speech-window coverage are certified. Neither
ASR words, teacher/student roles, example meaning, nor trades are certified.
"""
from __future__ import annotations
import argparse, hashlib, io, json, re, wave, zipfile
from pathlib import Path

SHA_OLD_WAV_TO_SOURCE={
  '0efe686fad25071c0116250072dfb555d74cff65640f33f59e44dbfc7fac81e1':('s19_0efe_EXACT_SHA_MATCH.wav',3588.0,3912.0),
  'b96434bd9989bce5096fe24ae7c4d8419475d0a23235aea6022bfaddec65ab20':('s19_b964_EXACT_SHA_MATCH.wav',4188.0,4512.0),
  'd3ea03e2be921aa3db944ab3d2f43402cf85639345bd32d53497d0259f1f3df2':('s21_d3ea_EXACT_SHA_MATCH.wav',1788.0,2112.0),
  'b071b5ba121ade3771a3048150b4361fec2755cee9788e7424e52d422eab00f8':('source_original_part12.wav',3288.0,3612.0)
}


def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()


def verified_source(data:bytes, expected_sha:str, cut_start:float, cut_end:float):
    if sha(data)!=expected_sha:raise ValueError('EXACT_ORIGINAL_WAV_SHA_MISMATCH')
    with wave.open(io.BytesIO(data),'rb') as w:
        if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):
            raise ValueError('ORIGINAL_WAV_SHAPE_MISMATCH')
        actual=w.readframes(w.getnframes())
        if len(actual)!=w.getnframes()*2:raise ValueError('ORIGINAL_WAV_PCM_TRUNCATED')
        duration=w.getnframes()/w.getframerate()
    if abs(duration-(cut_end-cut_start))>0.015:raise ValueError('ORIGINAL_WAV_TIMEBASE_MISMATCH')
    return duration


def slice_verified(source:bytes, cut_start:float, cut_end:float, start:float, end:float)->bytes:
    if not(cut_start<=start<end<=cut_end):raise ValueError('EXCERPT_OUTSIDE_PINNED_ORIGINAL_WAV')
    with wave.open(io.BytesIO(source),'rb') as w:
        hz=w.getframerate()
        i=round((start-cut_start)*hz)
        n=round((end-start)*hz)
        w.setpos(i)
        pcm=w.readframes(n)
        if len(pcm)!=n*w.getnchannels()*w.getsampwidth():raise ValueError('TRUNCATED_EXCERPT')
        out=io.BytesIO()
        with wave.open(out,'wb') as z:
            z.setnchannels(w.getnchannels());z.setsampwidth(w.getsampwidth());z.setframerate(hz)
            z.writeframes(pcm)
    return out.getvalue()


def upgrade(private_review_zip:Path, recovered_source_dir:Path, s20_source_archive:Path, output:Path):
    original_sources={}
    for h,(name,a,b) in SHA_OLD_WAV_TO_SOURCE.items():
        if name=='source_original_part12.wav':
            with zipfile.ZipFile(s20_source_archive) as z:
                src=z.read('audio/batch_001/part_12.wav')
        else:src=(recovered_source_dir/name).read_bytes()
        verified_source(src,h,a,b)
        original_sources[h]=(src,a,b)
    with zipfile.ZipFile(private_review_zip) as z:
        names=z.namelist();old=json.loads(z.read('manifest.json'))
        if len(old['sources'])!=4 or len(old['pairs'])!=14:raise ValueError('unexpected original review manifest')
        originals={name:z.read(name) for name in names}
    new=json.loads(json.dumps(old,ensure_ascii=False))
    replacement={}
    for group in new['sources']:
        h=group['historical_original_wav_sha256']
        src,cut_a,cut_b=original_sources[h]
        clip_a,clip_b=group['clip_seconds']
        data=slice_verified(src,cut_a,cut_b,clip_a,clip_b)
        group['old_new_pcm_equality_checked']=False
        # A decoded MP4 clip is not the same provenance as an exact archived WAV.
        group['original_wav_sha256_exact_match']=True
        group['source_wav_sha256_verified']=h
        group['historical_original_wav_available_now']=True
        group['source_original_wav_cut_seconds']=[cut_a,cut_b]
        group['review_clip_sha256']=sha(data)
        group['review_clip_origin']='BYTE_EXCERPT_FROM_EXACT_SHA_VERIFIED_HISTORICAL_SOURCE_WAV'
        replacement[group['clip']]=data
    new['schema']='artin_14_pairs_exact_historical_wav_review_v2'
    new['all_four_original_wav_sha_exact_matched']=True
    new['verified_historical_source_audio_groups']=4
    new['unique_candidate_pair_count']=14
    new['independent_teacher_speech_verified']=False
    new['speaker_verified']=False
    new['chart_action_semantics_verified']=False
    new['orders_authorized']=0
    new['old_original_wav_sha_not_claimed']=False
    # v1 declared historical WAV SHA not claimed in page prose. Update visibly.
    html=originals['index.html'].decode('utf-8')
    old_intro='منبع MP4 با رسید SHA-256 تایید شده، اما WAV جدید با هش تاریخی WAV یکسان اعلام نمی‌شود.'
    new_intro='هر چهار منبع WAV اصلی اکنون با هش تاریخی SHA-256 دقیق تأیید شده و دکمه‌ها از همان منبع برش خورده‌اند.'
    if html.count(old_intro)!=1:raise ValueError('review HTML provenance notice mismatch')
    html=html.replace(old_intro,new_intro)
    for group in new['sources']:
        # Avoid misleading adjacent labels displaying "newly decoded" WAV hash.
        old_label='صوت WAV بازاستخراج شده: <code>'+group['newly_decoded_wav_sha256']+'</code>'
        new_label='صوت WAV تاریخیِ منطبق: <code>'+group['source_wav_sha256_verified']+'</code>'
        if html.count(old_label)!=1:raise ValueError('review source hash label missing')
        html=html.replace(old_label,new_label)
    manifest_bytes=(json.dumps(new,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in names:
            if name=='manifest.json':data=manifest_bytes
            elif name=='index.html':data=html.encode('utf-8')
            else:data=replacement.get(name,originals[name])
            z.writestr(name,data)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('zip integrity failure')
        if len(z.namelist())!=len(names):raise ValueError('zip entries lost')
        for s in new['sources']:
            if sha(z.read(s['clip']))!=s['review_clip_sha256']:raise ValueError('clip changed after archive write')
    return new


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--old',type=Path,required=True)
    p.add_argument('--recovered-dir',type=Path,required=True)
    p.add_argument('--s20-original',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--manifest-out',type=Path,required=True)
    a=p.parse_args()
    d=upgrade(a.old,a.recovered_dir,a.s20_original,a.out)
    a.manifest_out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'sha_verified_source_wavs':d['verified_historical_source_audio_groups'],'unique_pairs':len(d['pairs']),'original_video_frames':sum(len(s['sampled_original_mp4_images']) for s in d['sources']),'zip':str(a.out),'certified_semantics':False}))
if __name__=='__main__':main()