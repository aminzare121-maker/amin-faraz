#!/usr/bin/env python3
"""Read-only timestamp/source integrity audit of six Artin audio/ASR teaching citations.

Original board image sources are the immutable V13 GitHub workflow artifacts for
queue videos 20 and 22. This tool checks image ZIP SHA256 and exact frame time;
scene labels reflect bounded still-image inspection, *not* verified words,
teacher identity, referenced chart element, independently confirmed trade rules,
or permission to trade. Private teacher text and screenshot bytes remain local.
"""
from __future__ import annotations
import hashlib
import json
import re
import zipfile
from pathlib import Path

SOURCE_BOARD_SHA256 = {
    20: '4ee123ee806c848b4b733f3bbc1e7ae4f2f12f1ef94f96095cda7312c45f319f',
    22: 'b56deb23203ab616b614cc0f959e342b26dfbccda7f964e663c887e39338770a',
}
# Bound the actual scene claim to the original byte digest of the specific frame.
# These are only scene descriptions (chart vs. meeting interface), not teacher intent.
REVIEWED_SCENES = {
 (20, 4095.0): ('CHART_VISIBLE', '3334cbd0854575e3241c867cf8b16faafc363cb48a0a9362a61374696a0cdc41'),
 (20, 4125.0): ('CHART_VISIBLE', '3945449396ef0eb8d6887143e98060cb1b4fdc11fbd99d9273841e6c2c477e76'),
 (20, 4185.0): ('CHART_VISIBLE', '9b0c221a9552c00bd89a6821cb2cfb4225a7c4a3984e7b8777bfc9ea7a5e0443'),
 (20, 4215.0): ('CHART_VISIBLE', 'aec74674a9f251412fa5e4a8f0c9c39216e489437551762f6e1fe242657603d2'),
 (22, 4695.0): ('MEETING_INTERFACE', 'ad3c59d928082d20c34f314db195bebabd56e6cb586ff6432f9118a50802a439'),
 (22, 4725.0): ('CHART_VISIBLE', 'b624b5792eed1ff31d02ef79851c6f707610d1555773f9bc74064d0deaad6ecf'),
}
FRAME_NAME = re.compile(r'^board/[A-Za-z0-9_-]+_t(\d+)_board\.png$')
CHAT_NAME = re.compile(r'^chat/[A-Za-z0-9_-]+_t(\d+)_chat\.png$')
ORIGINAL_FRAME_NAME = re.compile(r'^frames/[A-Za-z0-9_-]+_t(\d+)_original\.jpg$')
EXPECTED_WINDOWS = (
 ('ARTIN-RESTORED-01', 20, 4100.0, 4133.0),
 ('ARTIN-RESTORED-02', 20, 4201.30, 4208.84),
 ('ARTIN-RESTORED-03', 20, 4210.14, 4214.52),
 ('ARTIN-RESTORED-04', 20, 4210.14, 4214.52),
 ('ARTIN-RESTORED-05', 20, 4214.52, 4223.26),
 ('ARTIN-RESTORED-06', 22, 4694.0, 4728.0),
)


def digest_file(path: Path) -> str:
    with Path(path).open('rb') as src:
        return hashlib.file_digest(src, 'sha256').hexdigest()


def _validate_zip(z: zipfile.ZipFile) -> dict[float, zipfile.ZipInfo]:
    members=z.infolist()
    if not members or len(members)>5000:
        raise ValueError('unexpected board image file count')
    if len({x.filename for x in members})!=len(members):
        raise ValueError('duplicate board ZIP members')
    frames={}
    for info in members:
        m=FRAME_NAME.fullmatch(info.filename)
        if info.is_dir() or info.flag_bits & 1 or (m is None and CHAT_NAME.fullmatch(info.filename) is None and ORIGINAL_FRAME_NAME.fullmatch(info.filename) is None and info.filename != 'visual_timeline_v6.json'):
            raise ValueError('untrusted ZIP board member name or encryption')
        if info.file_size<=0 or info.file_size>8*1024*1024 or info.compress_size<=0:
            raise ValueError('board frame size out of bounds')
        if info.file_size>max(1,info.compress_size)*200:
            raise ValueError('board ZIP decompression ratio excessive')
        if m is None:  # Embedded chat screenshots are valid archive contents, not board evidence.
            continue
        t=int(m.group(1))/1000
        if t in frames:
            raise ValueError('duplicate frame timestamp')
        frames[t]=info
    return frames


def _gap(t:float,start:float,end:float)->float:
    if start<=t<=end:return 0.0
    return round(start-t if t<start else t-end,4)


def build_audit(restored: dict, paths: dict[int,Path], *, board_sha256=SOURCE_BOARD_SHA256,
                scene_index=REVIEWED_SCENES, allow_unpinned_for_synthetic_tests=False) -> dict:
    if not isinstance(restored,dict):raise ValueError('source report must be object')
    windows=restored.get('private_review_windows')
    if not isinstance(windows,list) or len(windows)!=6:raise ValueError('six authenticated speech windows needed')
    tuples=[(x.get('source_window_id'),x.get('queue_video'),x.get('start_seconds'),x.get('end_seconds')) for x in windows]
    if tuples!=list(EXPECTED_WINDOWS):raise ValueError('speech citation identity or bounds mismatch')
    if restored.get('original_audio_chunk_sha_verification_passed') is not True:
        raise ValueError('original audio identity not verified')
    if restored.get('video_registry_identity_verified') is not True:
        raise ValueError('original video identity not verified')
    frames={};sha={}
    for video in (20,22):
        p=Path(paths[video]); sha[video]=digest_file(p)
        if sha[video]!=board_sha256[video] and not allow_unpinned_for_synthetic_tests:
            raise ValueError('original board artifact SHA256 mismatch')
        with zipfile.ZipFile(p) as z:
            info=_validate_zip(z)
            frames[video]={}
            for t,entry in info.items():
                label='UNREVIEWED_SCENE'
                observed=None
                if (video,t) in scene_index:
                    label,expected_frame_sha=scene_index[(video,t)]
                    observed=hashlib.sha256(z.read(entry)).hexdigest()
                    if observed!=expected_frame_sha:
                        raise ValueError('pinned original screenshot bytes changed')
                frames[video][t]={'timestamp_seconds':t,'frame_filename':entry.filename,
                                  'scene_label':label,'original_png_sha256':observed}
    audits=[]
    for w in windows:
        video,start,end=w['queue_video'],w['start_seconds'],w['end_seconds']
        neighbor=sorted(frames[video].values(),key=lambda f:(_gap(f['timestamp_seconds'],start,end),abs(f['timestamp_seconds']-(start+end)/2)))[:4]
        nearby=[]
        for frame in neighbor:
            t=frame['timestamp_seconds'];distance=_gap(t,start,end)
            nearby.append({**frame,'inside_speech_interval':start<=t<=end,
                           'gap_to_speech_window_seconds':distance})
        within=[f for f in nearby if f['inside_speech_interval']]
        labels={f['scene_label'] for f in within}
        timing='IN_WINDOW_FRAMES_EXIST' if within else 'NO_FRAME_WITHIN_SPEECH_INTERVAL'
        if 'CHART_VISIBLE' in labels and 'MEETING_INTERFACE' in labels:
            timing='MIXED_SCENES_WITHIN_INTERVAL'
        unique={'video':video,'start_seconds':start,'end_seconds':end}
        audits.append({
            'source_window_id':w['source_window_id'], 'rule_id':w['entry_rule_id'],
            **unique,'audio_excerpt_sha256':w.get('audio_excerpt_sha256'),
            'original_video_sha256':w['video_sha256'],'board_archive_sha256':sha[video],
            'temporal_status':timing,'in_window_frame_count':len(within),
            'nearest_verified_frame_context':nearby,
            'speaker_verified':False,'teacher_words_verified':False,
            'chart_referent_to_spoken_instruction_verified':False,
            'rule_conditions_verified':False,'market_order_authorized':False,
        })
    shared=audits[2]['audio_excerpt_sha256']==audits[3]['audio_excerpt_sha256'] and audits[2]['start_seconds']==audits[3]['start_seconds']
    if not shared: raise ValueError('DOJI branches no longer share same evidence interval')
    return {
      'schema':'artin_v13_original_board_audio_timing_audit_v1',
      'board_zip_bytes_hash_verified':not allow_unpinned_for_synthetic_tests,
      'original_board_zip_sha256':{str(k):v for k,v in sha.items()},
      'source_window_count':len(audits),'unique_source_windows':5,
      'original_board_images_examined_for_scene_tag':len(scene_index),
      'windows_with_in_interval_original_board_frame':sum(a['in_window_frame_count']>0 for a in audits),
      'windows_without_in_interval_original_board_frame':sum(a['in_window_frame_count']==0 for a in audits),
      'doji_ahead_and_tied_share_same_audio':shared,
      'independently_verified_teacher_trade_rules':0,
      'paper_trades_permitted':False,'mt5_orders_permitted':False,
      'interpretation':'Original image existence/time is proven; scene label is visual-only. Visual reference and teacher semantics remain unverified.',
      'windows':audits,
    }


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--restored',type=Path,required=True)
    parser.add_argument('--board20',type=Path,required=True)
    parser.add_argument('--board22',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    doc=json.loads(args.restored.read_text(encoding='utf-8'))
    report=build_audit(doc,{20:args.board20,22:args.board22})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('source_window_count','windows_without_in_interval_original_board_frame','independently_verified_teacher_trade_rules','mt5_orders_permitted')}))

if __name__=='__main__':main()