#!/usr/bin/env python3
"""Private, read-only integration of 25 machine-ASR inventories + six recovered citations.

Does NOT verify teacher meaning, speaker attribution, chart causation or trades.
The original archives are never edited. Standard-library only.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

# Exact S0 original research `entry_engine.py` SOURCES, blob
# 2998d66f933f1edad4eccf7fb574b9f14007cf35. Original session IDs are 2..26;
# they map to current queue video old_session-1 (candidate mapping audited separately).
LEGACY_RULE_SOURCES = {
    'STOPPUNCH_S22_SELL_CONFIRMED_PAUSE': ((22,1888.1,1952.66),),
    'PULLBACK_STANDARD': ((16,615,854),(16,1003,1109)),
    'REVERSAL_CLASSIC': ((20,2188.86,2306.84),(20,2660.22,3255.4)),
    'REVERSAL_THREE': ((20,2660.22,3255.4),(20,3440.82,4048.72)),
    'REVERSAL_STAR': ((20,3440.82,4048.72),(20,4117.72,4483.72)),
    'BREAK_STRONG': ((21,2105.04,2261),(21,2274,2649.38)),
    'BREAK_WEAK_PIVOT': ((21,2770.48,3153.16),),
    'BREAK_WEAK_FULLBODY_EXCEPTION': ((21,2770.48,3153.16),),
    'BREAK_VERY_STRONG_RETEST': ((21,3162.56,3473.88),),
    'STOPPUNCH_SAME_COLOUR': ((21,3947,3975),(21,4201.30,4208.84),(21,4597,4661)),
    'STOPPUNCH_DOJI_AHEAD': ((21,3984.88,4068.98),(21,4210.14,4214.52)),
    'STOPPUNCH_DOJI_TIED': ((21,3984.88,4068.98),(21,4210.14,4214.52)),
    'STOPPUNCH_OPPOSITE_CONFIRMATION': ((21,4100,4133),(21,4214.52,4223.26),(23,4694,4728)),
}
ORIGINAL_FILE = 'ARTIN_RESTORED_SIX_AUDIO_AND_MACHINE_SPEECH_PRIVATE.json'
MANIFEST_FILE = 'ARCHIVE_MANIFEST.json'
BASE_MANIFEST = 'MANIFEST.json'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_zip(source: Path, max_total=45_000_000, max_files=100):
    with zipfile.ZipFile(source, 'r') as z:
        members=z.infolist()
        if len(members)>max_files or sum(f.file_size for f in members)>max_total:
            raise ValueError('source archive exceeded size limits')
        for f in members:
            name=f.filename
            if f.is_dir() or name.startswith('/') or '..' in Path(name).parts or '\\' in name or f.flag_bits&1:
                raise ValueError('unsafe member '+name)
        return {f.filename:z.read(f) for f in members}


def load_sources(inventory: Path, recovered: Path):
    original=parse_zip(inventory)
    recovery=parse_zip(recovered)
    manifest=json.loads(original[BASE_MANIFEST])
    rec_manifest=json.loads(recovery[MANIFEST_FILE])
    if manifest.get('machine_speech_rows_covered') != 10235 or manifest.get('session_count')!=25:
        raise ValueError('original inventory is not the pinned 25-session reference')
    for filename, info in rec_manifest.get('contents',{}).items():
        if filename not in recovery or sha(recovery[filename])!=info['sha256'] or len(recovery[filename])!=info['size_bytes']:
            raise ValueError('restored archive member hash/size mismatch: '+filename)
    rec=json.loads(recovery[ORIGINAL_FILE]); windows=rec['private_review_windows']
    if rec.get('restored_citation_windows')!=6 or len(windows)!=6:
        raise ValueError('recovery window receipt mismatch')
    sessions={}; total=0
    for entry in manifest['files']:
        n=entry['session']; filename=entry['file']; data=original.get(filename)
        if not data or sha(data)!=entry['sha256']:
            raise ValueError('original inventory member hash mismatch: '+str(n))
        rows=[json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
        if len(rows)!=entry['rows'] or not all(row['session']==n for row in rows):
            raise ValueError('original row count/session mismatch: '+str(n))
        if n in sessions:raise ValueError('duplicate session')
        sessions[n]=rows;total+=len(rows)
    if set(sessions)!=set(range(1,26)) or total!=10235:
        raise ValueError('missing 25 sessions or incorrect original count')
    return sessions,windows,original,recovery,manifest,rec


def merge_records(sessions, windows):
    output={k:list(v) for k,v in sessions.items()}
    seen={};window_refs=defaultdict(list)
    for w in windows:
        video=w['queue_video'];w_id=w['source_window_id']
        if video not in (20,22) or w.get('semantic_rule_verified',False):
            raise ValueError('unsupported restored window provenance')
        lo,hi=w['start_seconds'],w['end_seconds']
        if not (0<=lo<=hi):raise ValueError('invalid window time')
        segments=w['recovered_machine_asr_segments']
        if not segments:raise ValueError('window has no actual ASR segments')
        for s in segments:
            sid=s['asr_id'];start=s['start'];end=s['end']
            if not (isinstance(sid,str) and isinstance(s.get('text_unverified'),str)
                    and isinstance(start,(int,float)) and isinstance(end,(int,float))
                    and 0<=start<=end and start<=hi and end>=lo):
                raise ValueError('invalid ASR segment')
            key=(video,sid)
            if key in seen:
                row=seen[key]
                if any((row['start_seconds']!=start,row['end_seconds']!=end,
                        row['machine_text_unverified']!=s['text_unverified'],
                        row['source_audio_sha256']!=w['source_audio_sha256'])):
                    raise ValueError('same ASR segment has contradictory evidence')
            else:
                canonical=f'{video}|{sid}|{start:.6f}|{end:.6f}|{w["source_audio_sha256"]}'
                row={
                    'record_id':'ARTIN-RESTORED-'+sha(canonical.encode())[:24],
                    'session':video,'start_seconds':start,'end_seconds':end,
                    'machine_text_unverified':s['text_unverified'],
                    'source_segment_id':sid,'source_audio_sha256':w['source_audio_sha256'],
                    'source_video_sha256_if_available':w['video_sha256'],
                    'evidence_origin':'RECOVERED_ORIGINAL_ASR_SHARD',
                    'original_audio_artifact_id':w['original_audio_artifact_id'],
                    'original_asr_artifact_id':w['original_asr_artifact_id'],
                    'speaker_status':'UNKNOWN',
                    'teacher_meaning_verified':False,
                    'independent_speaker_and_wording_review_passed':False,
                    'engine_decision_compared_to_teacher':False,
                    'trade_permitted':False,
                    'status':'NOT_SEMANTICALLY_REVIEWED',
                    'source_window_ids':[],
                }
                seen[key]=row;output[video].append(row)
            if w_id not in row['source_window_ids']:
                row['source_window_ids'].append(w_id)
            window_refs[w_id].append(row['record_id'])
    for n in output:
        output[n].sort(key=lambda r:(r['start_seconds'],r['end_seconds'],r['record_id']))
    return output,seen,window_refs


def citation_coverage(original, merged):
    summary=[]
    for rule,cites in LEGACY_RULE_SOURCES.items():
        for old,a,b in cites:
            video=old-1
            def hits(rows):return [r for r in rows if r['start_seconds']<=b and r['end_seconds']>=a]
            h0=hits(original[video]);h1=hits(merged[video])
            summary.append({'route_id':rule,'legacy_session':old,'queue_video':video,
                            'start_seconds':a,'end_seconds':b,
                            'original_speech_rows':len(h0),'unified_speech_rows':len(h1),
                            'restored_speech_rows':sum(r.get('evidence_origin')=='RECOVERED_ORIGINAL_ASR_SHARD' for r in h1),
                            'machine_asr_present':bool(h1),
                            'teacher_speaker_verified':False,'teacher_semantics_certified':False})
    return summary


def run(inventory,recovered,output):
    sessions,windows,raw,reczip,manifest,rec=load_sources(inventory,recovered)
    merged,new,window_ids=merge_records(sessions,windows)
    coverage=citation_coverage(sessions,merged)
    if len(coverage)!=24 or len(LEGACY_RULE_SOURCES)!=13 or len(new)!=37:
        raise ValueError('expected 13/24 original source windows and 37 restored ASR segments')
    if (sum(not x['original_speech_rows'] for x in coverage)!=6
            or sum(not x['unified_speech_rows'] for x in coverage)!=0):
        raise ValueError('source windows not faithfully covered after restoration')
    report={'schema':'artin_unified_25_session_timed_machine_asr_v1',
      'source_archives':{
        'original_zip_sha256':sha(inventory.read_bytes()),
        'recovered_zip_sha256':sha(recovered.read_bytes())},
      'original_rows':sum(map(len,sessions.values())),'new_unique_asr_segments':len(new),
      'unified_rows':sum(map(len,merged.values())),'sessions':25,
      'legacy_entry_route_ids':13,'legacy_time_citations':24,
      'original_citations_with_asr':18,'recovered_citations':6,'unified_citations_with_asr':24,
      'source_map':'old_lesson_minus_1_as_candidate_source_map; teacher identity not independently certified',
      'machine_text_only':True,'original_source_zip_untouched':True,
      'spoken_words_independently_verified':False,'teacher_meaning_verified':False,
      'trade_signals_authorized':0,'orders_sent':0,
      'source_window_review':coverage,
      'restored_window_ids':{k:list(dict.fromkeys(v)) for k,v in window_ids.items()}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,rows in sorted(merged.items()):
            content='\n'.join(json.dumps(r,ensure_ascii=False,separators=(',',':')) for r in rows)+'\n'
            z.writestr(f'session_{n:02d}_unified_machine_speech_UNVERIFIED.jsonl',content)
        z.writestr('SOURCE_WINDOW_COVERAGE_PRIVATE.json',json.dumps(report,ensure_ascii=False,indent=2))
        z.writestr('ORIGINAL_INVENTORY_MANIFEST_UNCHANGED.json',raw['MANIFEST.json'])
        z.writestr('RESTORED_AUDIO_PROVENANCE_REFERENCE.json',reczip[ORIGINAL_FILE])
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--inventory',type=Path,required=True)
    ap.add_argument('--restored',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    res=run(args.inventory,args.restored,args.output)
    # Only publish counts, no verbatim private speech or raw price.
    print(json.dumps({k:res[k] for k in ('original_rows','new_unique_asr_segments',
         'unified_rows','sessions','legacy_entry_route_ids','legacy_time_citations',
         'unified_citations_with_asr','trade_signals_authorized')},ensure_ascii=False))