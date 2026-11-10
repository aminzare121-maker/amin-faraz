#!/usr/bin/env python3
"""Source-anchored, read-only audit of nine unresolved Artin teacher review pairs.

This module audits bytes, original audiovisual offsets, and visual-state differences.
It does NOT infer a teacher decision, certify transcription, or execute trades.
Private source files stay in /بهروز, never committed to the public repository.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import wave
import zipfile
from collections import Counter
from pathlib import Path

OPEN_CASES = (2, 3, 5, 7, 9, 10, 12, 13, 14)
UNRESOLVED = 'CONTEXT_DEPENDENT_OPPOSITE_WORDING_NOT_VERIFIED_CONFLICT'
EXPECTED_SESSION = {19: (4276, 4331), 21: (1896, 1944)}
LABELS = {
    19: 'XAUUSD_15M_CHART_ILLUSTRATED',
    21: 'EURUSD_15M_CHART_ANNOTATED',
}
# Human visual observations made from original captured chart images only.
# Distinct pictures do not prove distinct rules or different teacher decisions.
PAIR_VISUAL_NOTES = {
    2: 'Negative phrase has a red illustrated candle; positive phrase has a later green candle.',
    3: 'Negative phrase has a red illustrated candle; positive phrase has a later green candle.',
    5: 'Both original frames depict green candle examples, with on-screen annotations at different times.',
    7: 'Both original frames depict green candle examples, with on-screen annotations at different times.',
    9: 'Underlying EURUSD candlestick chart is similar; drawn levels and pointers differ.',
    10: 'Underlying EURUSD candlestick chart is similar; drawn levels and pointers differ.',
    12: 'Underlying EURUSD candlestick chart is similar; drawn levels and pointers differ.',
    13: 'Underlying EURUSD candlestick chart is similar; drawn levels and pointers differ.',
    14: 'Underlying EURUSD candlestick chart is similar; drawn levels and pointers differ.',
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_boundaries(start: float, end: float, clip_start: float, clip_end: float) -> tuple[float, float]:
    numbers = (start, end, clip_start, clip_end)
    if any(type(x) not in (int, float) for x in numbers):
        raise ValueError('Non-numeric original media timing')
    if not 0 <= clip_start <= start < end <= clip_end:
        raise ValueError('Utterance interval outside available original AV')
    return round(start - clip_start, 3), round(end - clip_start, 3)


def validate_media_member(path: str) -> None:
    if not isinstance(path, str) or not path or path.startswith('/') or '\\' in path or '..' in Path(path).parts:
        raise ValueError('Unsafe media path')
    if not (path.startswith('original_mp4_') and path.endswith(('.jpg', '.wav', '.mp4'))):
        raise ValueError('Unexpected media type')


def media_identity_matches(source_data: bytes, pack_data: bytes) -> bool:
    return sha(source_data) == sha(pack_data)


def audit(target: Path, original: Path, triage_file: Path) -> dict:
    private = json.loads(triage_file.read_text(encoding='utf-8'))
    actual_cases = [c for c in private['cases'] if c['v2_wording_status'] == UNRESOLVED]
    if sorted(c['pair_number_original'] for c in actual_cases) != list(OPEN_CASES):
        raise ValueError('Unexpected active 9-case review queue')
    original_seen = set()
    with zipfile.ZipFile(original) as master, zipfile.ZipFile(target) as review:
        if master.testzip() is not None or review.testzip() is not None:
            raise ValueError('Invalid ZIP CRC')
        master_members = master.namelist()
        names = review.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive members')
        if names.count('manifest.json') != 1 or names.count('index.html') != 1:
            raise ValueError('Missing review metadata or HTML')
        manifest = json.loads(review.read('manifest.json'))
        sources = manifest.get('source_groups', [])
        if len(sources) != 2 or {s['session'] for s in sources} != {19, 21}:
            raise ValueError('Expected exactly the two original source windows')
        if sorted(manifest.get('open_case_numbers', [])) != list(OPEN_CASES):
            raise ValueError('Incorrect case index')
        if manifest.get('teacher_meaning_verified') is not False or manifest.get('orders_authorized') != 0:
            raise ValueError('Unfounded semantic or trading authorization')
        if len(names) != 17: # 2 metadata + 15 exact original media members
            raise ValueError('Unexpected source media count')
        for name in names:
            if name not in ('manifest.json', 'index.html'):
                validate_media_member(name)
                if name not in master_members or not media_identity_matches(master.read(name), review.read(name)):
                    raise ValueError('Media differs from source archive')
                original_seen.add(name)
        if len(original_seen) != 15:
            raise ValueError('Original audio-video-image assets missing')
        source_by_sha = {s['historical_original_wav_sha256']: s for s in sources}
        images = {p for p in original_seen if p.endswith('.jpg')}
        if len(images) != 11:
            raise ValueError('Expected 11 unique original screenshots')
        html = review.read('index.html').decode('utf-8')
        buttons = [(float(a),float(b)) for a,b in re.findall(r'<button[^>]+data-start="([0-9.]+)" data-end="([0-9.]+)"',html)]
        if len(buttons) != 18 or html.count('<article>') != 9:
            raise ValueError('Review UI button/case binding mismatch')
        expected_buttons = []
        output_cases = []
        for c in sorted(actual_cases,key=lambda c:(c['session'],c['pair_number_original'])):
            source = source_by_sha.get(c['source_wav_sha256'])
            if not source or tuple(source['clip_seconds']) != EXPECTED_SESSION[c['session']]:
                raise ValueError('Case source identity/time mismatch')
            lookups = {}
            for s in original_manifest_segment_lookup(master,source['historical_original_wav_sha256']):
                lookups[s['id']] = s
            records = []
            for u in sorted(c['utterances'],key=lambda u:u['start_seconds']):
                if u['segment_id'] not in lookups:
                    raise ValueError('Citation not tied to original ASR source')
                src = lookups[u['segment_id']]
                if (u['start_seconds'],u['end_seconds'],u['machine_text_unverified']) != (src['start'],src['end'],src['machine_text_unverified']):
                    raise ValueError('Source ASR text/times altered')
                im = src['image']
                if im not in images or sha(review.read(im)) != src['image_sha256']:
                    raise ValueError('Wrong source screenshot or SHA')
                if not src['start'] <= src['image_capture_time'] <= src['end']:
                    raise ValueError('Screenshot not captured inside utterance')
                x,y=validate_boundaries(src['start'],src['end'],*source['clip_seconds'])
                expected_buttons.append((x,y))
                records.append({'original_segment_id':src['id'], 'original_start_seconds':src['start'], 'original_end_seconds':src['end'], 'original_screenshot_time':src['image_capture_time'], 'original_screenshot_sha256':src['image_sha256'], 'machine_ASR_text_unverified':src['machine_text_unverified']})
            output_cases.append({'pair':c['pair_number_original'],'video_session':c['session'],
                   'chart_in_frame':LABELS[c['session']], 'screenshot_state_observation':PAIR_VISUAL_NOTES[c['pair_number_original']],
                   'original_source_audio_sha256':c['source_wav_sha256'], 'two_utterances':records,
                   'same_teacher_chart_conditions_verified':False, 'original_speech_independently_verified':False,
                   'semantic_contradiction_certified':False, 'trade_permitted':False})
        if expected_buttons != buttons:
            raise ValueError('Review button timing does not match original ASR source')
        for s in sources:
            if s['clip'] not in original_seen or s['video_clip'] not in original_seen:
                raise ValueError('Missing video or audio from cited source')
            with wave.open(io.BytesIO(review.read(s['clip'])), 'rb') as w:
                if (w.getframerate(),w.getnchannels(),w.getsampwidth()) != (16000,1,2):
                    raise ValueError('WAV source encoding unexpected')
                expected_frames=int((s['clip_seconds'][1]-s['clip_seconds'][0])*16000)
                if w.getnframes()!=expected_frames or len(w.readframes(expected_frames))!=expected_frames*2:
                    raise ValueError('Truncated WAV payload')
        return {'schema':'artin_9_original_av_visual_context_independent_gate_v1',
            'private_package':str(target),'case_count':len(output_cases), 'total_review_media_seconds':103,
            'original_media_members_byte_identical_to_verified_source':15,'original_screenshots_sha_verified':11,
            'original_audio_windows_duration_and_pcm_verified':2,'original_video_excerpts_verified_byte_identical_to_previous_source':2,
            'asr_utterance_buttons_checked':18,
            'chart_symbols_from_direct_observed_screenshots':{'19':'XAUUSD_15M', '21':'EURUSD_15M'},
            'evidence_cases':output_cases,
            'teacher_speech_independently_heard':False, 'teacher_market_decision_replayed':False,
            'teacher_strategy_semantics_certified':False, 'orders_sent':0}


def original_manifest_segment_lookup(master: zipfile.ZipFile, source_sha: str) -> list:
    d=json.loads(master.read('manifest.json'))
    matches=[s for s in d.get('sources',[]) if s['historical_original_wav_sha256']==source_sha]
    if len(matches)!=1:
        raise ValueError('Original archive source lookup not unique')
    return matches[0]['unique_speech_segments']


def main():
    p=argparse.ArgumentParser()
    p.add_argument('review_zip',type=Path);p.add_argument('master_zip',type=Path);p.add_argument('triage_json',type=Path);p.add_argument('private_report',type=Path)
    args=p.parse_args()
    result=audit(args.review_zip,args.master_zip,args.triage_json)
    args.private_report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':result['case_count'], 'minutes':result['total_review_media_seconds']/60,
         'media_verified':result['original_media_members_byte_identical_to_verified_source'],
         'teacher_verified':False,'trades':0}))

if __name__ == '__main__':main()