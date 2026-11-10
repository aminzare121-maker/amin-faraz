#!/usr/bin/env python3
"""Source-anchored, fail-closed lexical triage for 14 Artin ASR conflict pairs.

Identifies *machine text* false positives, conditional language and absent
chart references. It DOES NOT transcribe audio, identify a speaker, certify a
teacher rule or send orders. Original V1 claims are preserved as history.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import re
import zipfile
import wave
import io
from collections import Counter
from pathlib import Path

EXPECTED_SHA_BY_SESSION = {
    19: '164d6a5ef28b29e3500d4211b7a5954b95dd9fe1393d99d7e5806e693ca8dc03',
    20: '6db1d227430e99facea0ba6cc2931f04f70f67ed42d8f6abb0bb58f9e087e3a9',
    21: 'f63690d402f299d297110ff815b7fee9fcae8bb4927b9084e401488efaa3a1a3',
}
# Direct visual inspection of the 16 actual original MP4 frames in the cited pack.
# Labels describe the screenshot shown, never an inference about what the teacher intended.
FULL_SOURCE = {
    '0efe': ('historical_verified_wavs/s19_0efe_EXACT_SHA_MATCH.wav', 3588),
    'b964': ('historical_verified_wavs/s19_b964_EXACT_SHA_MATCH.wav', 4188),
    'b071': ('historical_verified_wavs/source_original_part12.wav', 3288),
    'd3ea': ('historical_verified_wavs/s21_d3ea_EXACT_SHA_MATCH.wav', 1788),
}
SCREEN_TYPE = {
    (19, 'b96434bd99'): 'TRADINGVIEW_XAUUSD_15M_ILLUSTRATED_CANDLES',
    (19, '0efe686fad'): 'WEBINAR_ROOM_NO_TRADING_CHART_VISIBLE',
    (20, 'b071b5ba12'): 'TRADINGVIEW_ILLUSTRATED_SINGLE_CANDLE',
    (21, 'd3ea03e2be'): 'TRADINGVIEW_EURUSD_15M_ANNOTATED_CHART',
}
ENTRY_WORD = re.compile(r'ورود|وارد|پوزیشن|معامله')
NEGATIVE = re.compile(r'نمی\s*(?:کن|شو|شد|زن|گیری)|نکن|نکرد|نشد|نشو|نباید|ممنوع|عدم\s*ورود|نه\s*وارد|قرار\s*نیست')
POSITIVE_ACTION = re.compile(r'(?:ورود\s*(?:می\s*کن|کنیم|کنم|کردم|کردیم|می\s*شه|می\s*شیم)|وارد\s*(?:می\s*ش|بش|شد))')
QUESTION = re.compile(r'استاد|سوال|سؤال|چرا|یعنی|\?')
CONDITIONAL = re.compile(r'اگر|وقتی|در\s*صورتی|تا\s*وقتی|مگر|شرط|مثلا')
PAST = re.compile(r'نکردم|نکردیم|کردم|کردیم|نپذیرفتم|قبل[اًا]?')

def normalize(s):
    if not isinstance(s,str): raise ValueError('Expected machine ASR string')
    return s.replace('ي','ی').replace('ك','ک').replace('\u200c',' ').replace('\u200f',' ')

def wording_class(s):
    """Classify lexical evidence only, NOT actual spoken teacher decisions."""
    t=normalize(s)
    if not ENTRY_WORD.search(t): return 'NO_ENTRY_WORD'
    if NEGATIVE.search(t): return 'NEGATED_ENTRY_WORDING'
    if POSITIVE_ACTION.search(t): return 'POSITIVE_ENTRY_ACTION_WORDING'
    return 'ENTRY_REFERENCE_WITHOUT_ACTION_ASSERTION'

def _verify_zip_frame(z, source, seg):
    name=seg['image']
    if name not in z.namelist():raise ValueError('Original visual frame absent')
    bs=z.read(name)
    if hashlib.sha256(bs).hexdigest()!=seg['image_sha256']:
        raise ValueError('Original visual frame hash mismatch')
    if not (seg['start']<=seg['image_capture_time']<=seg['end']):
        raise ValueError('Visual frame not inside claimed speech time')
    if not bs.startswith(b'\xff\xd8\xff'):raise ValueError('Original visual frame not JPEG')

def triage(manifest, source_review, media_zip, full_source_wav_zip):
    if len(manifest.get('pairs',[]))!=14 or len(manifest.get('sources',[]))!=4:
        raise ValueError('Expected exactly 14 deduplicated pairs and four sources')
    if manifest.get('all_four_original_wav_sha_exact_matched') is not True:
        raise ValueError('Four exact source WAV SHA matches required')
    sources={}
    for src in manifest['sources']:
        sess=src['session']; sha=src['historical_original_wav_sha256']
        if src['source_mp4_sha256']!=EXPECTED_SHA_BY_SESSION.get(sess):
            raise ValueError('Original MP4 source identity changed')
        key=(sess,sha)
        if key in sources:raise ValueError('Duplicated source WAV')
        label=SCREEN_TYPE.get((sess,sha[:10]))
        if not label:raise ValueError('Unreviewed original screenshot group')
        sources[key]=src
    # Source-identity keyed index; recorded names and text must match the review.
    originals={}
    for route in source_review['routes']:
        for e in route['events']:
            key=(e['session'],e['source_audio_sha256'],e['source_segment_id'])
            detail=(e['start_seconds'],e['end_seconds'],e['text_unverified'])
            if key in originals and originals[key]!=detail:
                raise ValueError('Inconsistent historical original ASR text/times')
            originals[key]=detail
    private=[]; counted=Counter(); all_visual_checks=0; unique_visual_frame_ids=set()
    with zipfile.ZipFile(media_zip) as z, zipfile.ZipFile(full_source_wav_zip) as zw:
        if z.testzip() is not None or zw.testzip() is not None:
            raise ValueError('Media ZIP integrity failed')
        # The v2 listening ZIP kept a stale v1 newly_decoded_wav_sha256 field.
        # Never trust that field: verify original historical WAV SHA and exact PCM
        # intersection instead, including all samples in the corresponding clip.
        for (sess,sha),src in sources.items():
            path,start=FULL_SOURCE[sha[:4]]
            if path not in zw.namelist():raise ValueError('Exact historical WAV absent')
            original=zw.read(path)
            if hashlib.sha256(original).hexdigest()!=sha:
                raise ValueError('Historical source WAV SHA failed')
            with wave.open(io.BytesIO(original),'rb') as parent, wave.open(io.BytesIO(z.read(src['clip'])),'rb') as clip:
                if ((parent.getframerate(),parent.getnchannels(),parent.getsampwidth())!=(16000,1,2)
                    or (clip.getframerate(),clip.getnchannels(),clip.getsampwidth())!=(16000,1,2)):
                    raise ValueError('Original WAV audio format mismatch')
                begin,end=src['clip_seconds']
                if not (start<=begin<end<=start+parent.getnframes()/16000):
                    raise ValueError('Clip outside original WAV')
                expected=int((end-begin)*16000)
                if clip.getnframes()!=expected:raise ValueError('Wrong source clip duration')
                parent.setpos(int((begin-start)*16000))
                reference=parent.readframes(expected)
                actual=clip.readframes(expected)
                if len(reference)!=expected*2 or actual!=reference:
                    raise ValueError('MP4 excerpt not byte-identical in PCM to historical source WAV')
                if clip.readframes(1):raise ValueError('Extra audio samples after claimed clip')
            if src['video_clip'] not in z.namelist() or hashlib.sha256(z.read(src['video_clip'])).hexdigest()!=src['video_clip_sha256']:
                raise ValueError('Original MP4 excerpt hash mismatch')

        for p in manifest['pairs']:
            key=(p['session'],p['original_audio_sha256_historical'])
            src=sources.get(key)
            if src is None or p['source_original_mp4_sha256']!=src['source_mp4_sha256']:
                raise ValueError('Pair/WAV provenance mismatch')
            if p['audio_generated_from_original_mp4_file']!=src['clip']:
                raise ValueError('Audio clip provenance mismatch')
            if len(p['segment_ids'])!=2 or len(set(p['segment_ids']))!=2:
                raise ValueError('Pair requires two distinct original segments')
            if src['clip'] not in z.namelist() or src['video_clip'] not in z.namelist():
                raise ValueError('Actual original AV clip missing')
            if hashlib.sha256(z.read(src['video_clip'])).hexdigest()!=src['video_clip_sha256']:
                raise ValueError('MP4 video excerpt hash mismatch')
            lookup={s['id']:s for s in src['unique_speech_segments']}
            mentions=[]
            for sid in p['segment_ids']:
                if sid not in lookup:raise ValueError('Segment not in cited original source')
                s=lookup[sid]
                a,b,text=originals[(p['session'],key[1],sid)]
                if (a,b,text)!=(s['start'],s['end'],s['machine_text_unverified']):
                    raise ValueError('Historical ASR text/timing mismatch')
                if not (p['clip_seconds'][0]<=a<b<=p['clip_seconds'][1]):
                    raise ValueError('Original utterance outside review audio')
                _verify_zip_frame(z,src,s);all_visual_checks+=1;unique_visual_frame_ids.add(s['image'])
                kind=wording_class(text)
                mentions.append({'segment_id':sid,'start_seconds':a,'end_seconds':b,
                    'machine_text_unverified':text,'wording_class':kind,
                    'contains_conditional_word':bool(CONDITIONAL.search(normalize(text))),
                    'contains_question_word':bool(QUESTION.search(normalize(text))),
                    'contains_past_tense_cue':bool(PAST.search(normalize(text))),
                    'source_frame':s['image'],'source_frame_time':s['image_capture_time'],
                    'source_frame_sha256':s['image_sha256'],
                    'independently_heard':False,'speaker_identity_verified':False})
            kinds={m['wording_class'] for m in mentions}
            if kinds=={'NEGATED_ENTRY_WORDING'}:
                status='FALSE_LEXICAL_FLIP_BOTH_WORDINGS_NEGATED'
            elif 'ENTRY_REFERENCE_WITHOUT_ACTION_ASSERTION' in kinds or 'NO_ENTRY_WORD' in kinds:
                status='NONCOMPARABLE_ACTION_CLAIM_IN_MACHINE_TEXT'
            elif kinds=={'NEGATED_ENTRY_WORDING','POSITIVE_ENTRY_ACTION_WORDING'}:
                status='CONTEXT_DEPENDENT_OPPOSITE_WORDING_NOT_VERIFIED_CONFLICT'
            else:
                status='UNRESOLVED_LEXICAL_CASE'
            counted[status]+=1
            screen=SCREEN_TYPE[(key[0],key[1][:10])]
            case={'pair_number_original':p['pair_number'],'session':p['session'],'route_ids':p['routes'],
                'source_wav_sha256':key[1], 'screen_type_visually_observed':screen,
                'original_video_sha256':src['source_mp4_sha256'],
                'original_video_excerpt':src['video_clip'],
                'audio_excerpt':src['clip'],'utterances':mentions,'v2_wording_status':status,
                'original_lexical_pair_was_teacher_contradiction':False,
                'identical_chart_state_proved':False,
                'independent_speaker_verified':False,'teacher_semantics_verified':False,
                'trade_permitted':False}
            if screen=='WEBINAR_ROOM_NO_TRADING_CHART_VISIBLE':
                case['visual_limitation']='These original frames show a webinar interface, not a chart; do not infer an actual chart trade.'
            elif screen=='TRADINGVIEW_EURUSD_15M_ANNOTATED_CHART':
                case['visual_limitation']='Original screenshot shows EURUSD 15m, not XAUUSD; chart reasoning cannot be transferred to gold without certified teacher meaning.'
            else:
                case['visual_limitation']='An original chart frame exists at each speech timestamp, but cursor/illustration changes are not verified teacher actions.'
            private.append(case)
    if len({(x['session'],tuple(sorted(u['segment_id'] for u in x['utterances']))) for x in private})!=14:
        raise ValueError('Not exactly 14 unique original speech pairs')
    summary={'schema':'artin_14_machine_lexical_conflict_triage_v2','distinct_pairs':14,
        'original_pair_occurrences_before_dedup':16,'source_wavs_original_SHA256_and_clip_PCM_verified_in_this_run':4,
        'original_frame_identity_checks_across_pair_mentions':all_visual_checks,
        'distinct_source_video_frames_sha256_verified':len(unique_visual_frame_ids),
        'classification_counts':dict(sorted(counted.items())),
        'v1_lexical_negative_bug_corrected':wording_class('ورود نکردم')=='NEGATED_ENTRY_WORDING',
        'v2_packet_stale_decoded_clip_hash_disregarded_and_original_full_pcm_verified':True,
        'original_speech_independently_transcribed':False,'teacher_speaker_verified':False,
        'teacher_chart_decision_compared_to_engine':False,'teacher_semantic_conflicts_certified':0,
        'teacher_rules_certified':0,'mt5_trades_authorized':0}
    if sum(counted.values())!=14:raise ValueError('Audit count inconsistent')
    return {'summary':summary,'cases':private}

def public_projection(r):
    out=copy.deepcopy(r['summary'])
    out['screen_type_counts']=dict(Counter(x['screen_type_visually_observed'] for x in r['cases']))
    out['cases']=[{'pair_number_original':x['pair_number_original'],'session':x['session'],
        'route_ids':x['route_ids'],'wording_status':x['v2_wording_status'],
        'screen_type':x['screen_type_visually_observed'],
        'speaker_verified':False,'semantic_conflict_verified':False,'trade_permitted':False}
        for x in r['cases']]
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument('private_source_manifest',type=Path)
    p.add_argument('private_original_conflict_review',type=Path)
    p.add_argument('private_original_av_zip',type=Path)
    p.add_argument('private_source_four_wav_zip',type=Path)
    p.add_argument('private_output',type=Path)
    p.add_argument('public_output',type=Path)
    a=p.parse_args()
    report=triage(json.loads(a.private_source_manifest.read_text()),
        json.loads(a.private_original_conflict_review.read_text()),a.private_original_av_zip,a.private_source_four_wav_zip)
    a.private_output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    a.public_output.write_text(json.dumps(public_projection(report),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False))

if __name__=='__main__':main()