"""Read-only, fail-closed media linkage for unverified Artin ASR polarity candidates.

A matching clock position is NOT proof that two audios have the same origin.
Never promotes a candidate to a trading rule or teacher interpretation.
"""
import hashlib
import json
import math
import wave
import zipfile
from collections import defaultdict
from io import BytesIO


def verify_audio_zip(path, member):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if names.count('fast_av_manifest.json') != 1 or names.count(member) != 1:
            raise ValueError('Missing or repeated source audio/manifest')
        manifest=json.loads(z.read('fast_av_manifest.json'))
        parts=[p for p in manifest['parts'] if p['audio']==member]
        if len(parts)!=1:raise ValueError('Ambiguous WAV member provenance')
        part=parts[0]
        wav=z.read(member)
        sha=hashlib.sha256(wav).hexdigest()
        if sha!=part['audio_sha256']:raise ValueError('Original WAV SHA-256 mismatch')
        with wave.open(BytesIO(wav),'rb') as a:
            rate=a.getframerate(); frames=a.getnframes()
            pcm=a.readframes(frames)
            if len(pcm)!=frames*a.getnchannels()*a.getsampwidth():
                raise ValueError('Truncated PCM payload')
            duration=frames/rate
        if abs(duration-(part['cut_end']-part['cut_start']))>.02:
            raise ValueError('WAV timebase mismatch')
        return {'sha256':sha,'video_sha256':manifest['video_sha256'],
            'start':float(part['cut_start']),'end':float(part['cut_end']),
            'member':member}


def evaluate(conflicts, crossmodal, media):
    if not isinstance(conflicts,dict) or not isinstance(conflicts.get('routes'),list):
        raise ValueError('Invalid conflict review')
    frame_windows={}
    for c in crossmodal['citations']:
        frame_windows[(c['route_id'],c['session'])]=frame_windows.get((c['route_id'],c['session']),[])+[c]
    all_cases=[]
    unique_pairs={}
    for route in conflicts['routes']:
        route_id=route['route_id'];events={}
        for e in route['events']:
            key=(e['session'],e['source_segment_id'])
            if key in events and events[key]!=e:
                raise ValueError('Conflicting repeated ASR identity')
            events[key]=e
        for pair in route['candidate_polarity_flips']:
            session=pair['session']; e1=events.get((session,pair['first_segment_id']));e2=events.get((session,pair['second_segment_id']))
            if not e1 or not e2:raise ValueError('Missing pair source event')
            if e1['start_seconds']>=e1['end_seconds'] or e2['start_seconds']>=e2['end_seconds']:
                raise ValueError('Invalid ASR source interval')
            if not all(math.isfinite(e[k]) for e in [e1,e2] for k in ('start_seconds','end_seconds')):
                raise ValueError('Nonfinite ASR source interval')
            origins={e1['source_audio_sha256'],e2['source_audio_sha256']}
            if len(origins)!=1: raise ValueError('Different audio hashes within pair')
            audio_sha=next(iter(origins))
            matching=[m for m in media if m['sha256']==audio_sha and
                      m['start']<=min(e1['start_seconds'],e2['start_seconds']) and
                      m['end']>=max(e1['end_seconds'],e2['end_seconds'])]
            # Spatial proximity is not enough: identify individual aligned frames inside each spoken segment.
            frames=[im['time_seconds'] for c in frame_windows.get((route_id,session),[])
                    for im in c['reviewed_66_images_in_window']]
            direct_frame_for_both=bool([t for t in frames if e1['start_seconds']<=t<=e1['end_seconds']]) and bool(
                [t for t in frames if e2['start_seconds']<=t<=e2['end_seconds']])
            key=(session,tuple(sorted((e1['source_segment_id'],e2['source_segment_id']))))
            unique_pairs.setdefault(key,[]).append(route_id)
            all_cases.append({'route_id':route_id,'session':session,
                'first':{'id':e1['source_segment_id'],'start':e1['start_seconds'],'end':e1['end_seconds'],
                    'machine_text_unverified':e1['text_unverified']},
                'second':{'id':e2['source_segment_id'],'start':e2['start_seconds'],'end':e2['end_seconds'],
                    'machine_text_unverified':e2['text_unverified']},
                'recorded_audio_sha256':audio_sha,'verified_original_wav_sha_match':bool(matching),
                'sampled_original_frames_for_both_utterances':direct_frame_for_both,
                'status':'REVIEW_SOURCE_ORIGIN_AND_SPEAKER_NO_TRADE' if not matching else 'WAV_BYTES_MATCHED_BUT_SEMANTICS_UNVERIFIED_NO_TRADE',
                'teacher_decision_verified':False,'orders_authorized':0})
    return {'schema':'artin_conflict_media_provenance_v1', 'occurrence_pairs':len(all_cases),
        'unique_session_segment_pairs':len(unique_pairs),
        'repeated_pairs_across_routes':sum(len(routes)-1 for routes in unique_pairs.values()),
        'source_audio_sha_matched_pairs':sum(x['verified_original_wav_sha_match'] for x in all_cases),
        'source_audio_sha_unmatched_pairs':sum(not x['verified_original_wav_sha_match'] for x in all_cases),
        'original_video20_audio_provenance':media,'cases':all_cases,
        'teacher_semantics_certified':False,'orders_authorized':0}


def main():
    import argparse
    from pathlib import Path
    ap=argparse.ArgumentParser()
    ap.add_argument('conflict_json');ap.add_argument('crossmodal_json');ap.add_argument('original_wav_zip');ap.add_argument('output_json')
    a=ap.parse_args()
    audio=verify_audio_zip(a.original_wav_zip,'audio/batch_001/part_07.wav')
    result=evaluate(json.loads(Path(a.conflict_json).read_text()),json.loads(Path(a.crossmodal_json).read_text()),[audio])
    Path(a.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','original_video20_audio_provenance')},ensure_ascii=False))
if __name__=='__main__':main()