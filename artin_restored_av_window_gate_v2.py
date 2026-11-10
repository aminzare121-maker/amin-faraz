"""Verify SHA-256 of private recovered audio/video and strict citation-vs-clip frame coverage.
This is an integrity-only audit, never speaker/meaning certification or trading approval.
"""
import hashlib, json, re, wave, zipfile

def require(condition, message):
    if not condition:
        raise ValueError(message)
from pathlib import Path

FRAME_RE = re.compile(r'^frames/.+_t(\d{10})_original\.jpg$')

def audit(provenance, frames_archive, audio_archive):
    if not isinstance(provenance, dict) or not isinstance(provenance.get('citation_windows'), list):
        raise ValueError('invalid provenance document')
    frames={}
    with zipfile.ZipFile(frames_archive) as z:
        for member in z.namelist():
            m=FRAME_RE.match(member)
            if m:
                t=int(m.group(1))/1000
                frames[t]={'path':member,'sha256':hashlib.sha256(z.read(member)).hexdigest()}
        for record in provenance['original_frames']:
            t=record['source_time_seconds']
            require(t in frames, f'missing original frame {t}')
            require(frames[t]['path']==record['source_member'], 'frame identity mismatch')
            require(frames[t]['sha256']==record['original_frame_sha256'], 'frame SHA mismatch')
    audio={}
    with zipfile.ZipFile(audio_archive) as z:
        for name,expected in provenance['audio_clips'].items():
            require(name in z.namelist(), f'missing audio {name}')
            data=z.read(name)
            require(hashlib.sha256(data).hexdigest()==expected['sha256'], 'audio SHA mismatch')
            import io
            with wave.open(io.BytesIO(data),'rb') as wav:
                require(wav.getframerate()==expected['rate_hz'], 'audio sample rate mismatch')
                require(wav.getnchannels()==expected['channels'], 'audio channel mismatch')
                measured=wav.getnframes()/wav.getframerate()
                require(abs(measured-expected['duration_seconds'])<0.025, 'audio duration mismatch')
            audio[name]={'sha256_verified':True,'measured_seconds':round(measured,3)}
    cases=[]
    declared_by_id={c['id']:c for c in provenance['citation_windows']}
    aliases={a['window']:a['source_window'] for a in provenance.get('aliases',[])}
    for c in provenance['citation_windows']:
        start,end=c['citation_start_seconds'],c['citation_end_seconds']
        clip_start,clip_end=c['clip_start_seconds'],c['clip_end_seconds']
        require(clip_start<=start<end<=clip_end, 'invalid clip/citation span')
        is_video20=c['queue_video']==20
        inside=sorted(t for t in frames if start<=t<=end) if is_video20 else []
        in_clip=sorted(t for t in frames if clip_start<=t<=clip_end) if is_video20 else []
        if is_video20:
            require(inside==c['original_fullres_frames_inside_citation'], f'citation membership mismatch {c["id"]}')
            require(in_clip==c['original_fullres_frames_inside_clip_margin'], f'clip membership mismatch {c["id"]}')
        effective_clip=c['declared_clip']
        if c['id'] in aliases:
            target=declared_by_id[aliases[c['id']]]
            require((start,end)==(target['citation_start_seconds'],target['citation_end_seconds']), 'alias time mismatch')
            effective_clip=target['declared_clip']
        require(effective_clip in audio, 'unverified audio clip')
        cases.append({'id':c['id'],'queue_video':c['queue_video'],'route':c['route'],
            'citation_start_seconds':start,'citation_end_seconds':end,
            'original_frames_inside_citation_verified':inside if is_video20 else None,
            'original_frames_inside_audio_clip_span_verified':in_clip if is_video20 else None,
            'frames_exclusively_in_audio_margin':[t for t in in_clip if t not in inside] if is_video20 else None,
            'frame_archive_available_for_session':is_video20,
            'original_audio_sha256_verified':True,'resolved_audio_file':effective_clip,
            'audio_alias_used':c['id'] in aliases,'original_frame_sha256_verified':bool(inside) if is_video20 else False,
            'teacher_speech_listened_and_certified':False,'chart_referent_certified':False,
            'trade_action':'NO_TRADE'})
    return {'schema':'artin_restored_av_strict_boundary_audit_v2',
        'original_video20_frames_verified':len(provenance['original_frames']),
        'unique_audio_clips_sha256_verified':len(audio),'restored_citation_windows':len(cases),
        'video20_citations_with_strict_in_window_frame':sum(bool(c['original_frames_inside_citation_verified']) for c in cases),
        'video20_citations_with_margin_only_frame':sum(bool(c['frames_exclusively_in_audio_margin']) for c in cases),
        'audio_measurements':audio,'cases':cases,
        'speaker_meaning_certified':False,'trading_orders_authorized':0}

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('provenance');p.add_argument('frames_zip');p.add_argument('audio_zip');p.add_argument('output')
    a=p.parse_args()
    report=audit(json.loads(Path(a.provenance).read_text()),a.frames_zip,a.audio_zip)
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','audio_measurements')}))
if __name__=='__main__':main()
