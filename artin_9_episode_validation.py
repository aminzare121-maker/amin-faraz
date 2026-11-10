#!/usr/bin/env python3
"""Independent, fail-closed integrity verification of two private Artin AV episodes.

This verifies source identity, time pairing and UI bindings only. It CANNOT
verify Persian words, teacher identity, decisions or permit financial trades.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import re
import wave
import zipfile
from pathlib import Path

EPISODES={19,21}
PAIR_IDS={2,3,5,7,9,10,12,13,14}

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()

def _num(x):return type(x) in (int,float) and math.isfinite(x)

def validate_report(report:dict)->dict:
    if not isinstance(report,dict):raise ValueError('report not object')
    groups=report.get('source_groups')
    pairs=report.get('pairs')
    if not isinstance(groups,list) or not isinstance(pairs,list):raise ValueError('missing groups or pairs')
    if len(groups)!=2 or {g.get('session') for g in groups}!=EPISODES:raise ValueError('wrong two original video sessions')
    if len(pairs)!=9 or {p.get('pair') for p in pairs}!=PAIR_IDS:raise ValueError('wrong nine comparison pairs')
    if any(report.get(k) is not False for k in ('original_Persian_words_independently_heard','speaker_identity_independently_verified','teacher_semantics_verified','same_chart_trade_situation_verified_for_any_pair','XAUUSD_transfer_from_EURUSD_authorized')):raise ValueError('unearned semantic/trading claim')
    if report.get('mt5_orders_authorized')!=0:raise ValueError('trade permission forbidden')
    if report.get('source_group_count')!=2 or report.get('nine_unique_speech_segments')!=9 or report.get('candidate_pairs')!=9:raise ValueError('summary count mismatch')
    utterances={}
    total_duration=0
    for g in groups:
        ss=g['session']; times=g.get('clip_seconds')
        if not isinstance(times,list) or len(times)!=2 or any(not _num(t) for t in times) or not 0<=times[0]<times[1]:raise ValueError('bad source clip interval')
        total_duration+=times[1]-times[0]
        if not isinstance(g.get('machine_speech'),list):raise ValueError('invalid speech list')
        old=-1
        for u in g['machine_speech']:
            sid=u.get('segment_id');a=u.get('start_seconds');b=u.get('end_seconds');f=u.get('source_frame_time')
            if not isinstance(sid,str) or sid in utterances:raise ValueError('duplicate or invalid speech id')
            if not all(_num(x) for x in [a,b,f]) or not(times[0]<=a<b<=times[1]) or not(a<=f<=b) or a<old:raise ValueError('invalid speech time or order')
            old=a
            if u.get('session')!=ss:raise ValueError('speech session mismatch')
            if abs(u.get('audio_relative_from_seconds',-999)-(a-times[0]))>.011 or abs(u.get('audio_relative_until_seconds',-999)-(b-times[0]))>.011:raise ValueError('wrong playable timestamp binding')
            if u.get('independently_heard') is not False or u.get('speaker_identity_verified') is not False:raise ValueError('unearned speech certification')
            if not isinstance(u.get('machine_text_unverified'),str) or not u['machine_text_unverified']:raise ValueError('no ASR reference')
            utterances[sid]=u
    if len(utterances)!=9 or abs(total_duration-103)>.01 or abs(report.get('total_duration_seconds',-1)-total_duration)>.01:raise ValueError('source timing or unique utterance count incorrect')
    for p in pairs:
        ids=p.get('utterance_ids',[])
        if not isinstance(ids,list) or len(ids)!=2 or ids[0]==ids[1] or any(x not in utterances for x in ids):raise ValueError('pair lacks two source utterances')
        if any(utterances[x]['session']!=p.get('session') for x in ids):raise ValueError('cross-video comparison mistaken for same episode')
        if [utterances[x]['start_seconds'] for x in ids]!=sorted(utterances[x]['start_seconds'] for x in ids):raise ValueError('pair not in original chronological order')
        if p.get('trade_authorized') is not False or p.get('semantic_verdict')!='UNRESOLVED_NOT_A_CONFIRMED_CONTRADICTION':raise ValueError('unearned pair certification')
        if len(p.get('relative_timing_seconds',[]))!=2:raise ValueError('missing pair playback alignment')
        group=next(g for g in groups if g['session']==p['session'])
        if any(abs(p['relative_timing_seconds'][i] - (utterances[sid]['start_seconds']-group['clip_seconds'][0]))>.011 for i,sid in enumerate(ids)):raise ValueError('pair playback binding wrong')
    return {'session_count':2,'pair_count':len(pairs),'unique_speech_count':len(utterances),'duration_seconds':total_duration,'certified_teacher_rules':0,'orders_authorized':0}

def validate_package(zip_path:Path,original_zip_path:Path|None=None)->dict:
    with zipfile.ZipFile(zip_path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or z.testzip() is not None:raise ValueError('duplicate or corrupt archive')
        if len(names)!=17 or 'review.json' not in names or 'index.html' not in names:raise ValueError('unexpected archive layout')
        media={n for n in names if n.endswith(('.jpg','.mp4','.wav'))}
        if len(media)!=15:raise ValueError('unexpected media assets')
        report=json.loads(z.read('review.json'))
        result=validate_report(report)
        page=z.read('index.html').decode('utf8')
        if page.count('onclick="playAt(')!=9:raise ValueError('UI playback controls not exactly matched')
        if page.count('<video controls')!=2 or page.count('<audio id="sound')!=2:raise ValueError('original A/V players missing')
        for group in report['source_groups']:
            audio=group['clip']; video=group['video_clip']
            if audio not in media or video not in media:raise ValueError('A/V file not present')
            wraw=z.read(audio)
            if sha(wraw)!=group['audio_excerpt_sha256'] or sha(z.read(video))!=group['video_excerpt_sha256']:raise ValueError('corrupt A/V source bytes')
            with wave.open(io.BytesIO(wraw),'rb') as w:
                if (w.getframerate(),w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('unexpected PCM source shape')
                frames=w.getnframes();actual=w.readframes(frames)
                if len(actual)!=frames*2 or abs(frames/16000 - (group['clip_seconds'][1]-group['clip_seconds'][0]))>.01:raise ValueError('truncated/wrong WAV source')
            for u in group['machine_speech']:
                name=u['source_frame']
                if name not in media or sha(z.read(name))!=u['source_frame_sha256']:raise ValueError('original video frame is missing/corrupt')
                button=f'onclick="playAt({group["session"]},{u["audio_relative_from_seconds"]},{u["audio_relative_until_seconds"]})"'
                if page.count(button)!=1:raise ValueError('wrong/missing playable segment binding')
                if u['machine_text_unverified'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;') not in page:raise ValueError('machine text not presented as unverified original')
        if original_zip_path is not None:
            data=Path(original_zip_path).read_bytes()
            if sha(data)!=report['original_packet_sha256']:raise ValueError('original media packet SHA mismatch')
            with zipfile.ZipFile(io.BytesIO(data)) as original:
                if original.testzip() is not None:raise ValueError('original ZIP CRC mismatch')
                original_media={n for n in original.namelist() if n.endswith(('.jpg','.mp4','.wav'))}
                if media!=original_media:raise ValueError('unexpected original media membership')
                for n in media:
                    if sha(z.read(n))!=sha(original.read(n)):raise ValueError('original media byte change: '+n)
        return {**result,'media_files':len(media),'source_byte_integrity_checked':original_zip_path is not None,'browser_runtime_verified':False,'Persian_words_independently_verified':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('--source',type=Path);x=p.parse_args()
    print(json.dumps(validate_package(x.package,x.source),ensure_ascii=False,indent=2))