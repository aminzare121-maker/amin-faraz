"""Create a fail-closed, independently replayable audit of the original Artin AV packet.
No speech semantics and no trade authorizations can be inferred by this program.
"""
import argparse
import hashlib
import io
import json
import math
import pathlib
import wave
import zipfile


def audit_packet(path):
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        if len(names)!=len(z.namelist()):
            raise ValueError('duplicate filename in AV packet')
        d=json.loads(z.read('manifest.json'))
        clips={}
        for a in d['unique_audio_clips']:
            name=a['filename']
            if name in clips or name not in names or not name.endswith('.wav'):
                raise ValueError('duplicate or missing WAV')
            blob=z.read(name)
            if hashlib.sha256(blob).hexdigest()!=a['sha256']:
                raise ValueError('WAV checksum mismatch')
            with wave.open(io.BytesIO(blob),'rb') as w:
                duration=w.getnframes()/w.getframerate()
            if not math.isfinite(duration) or abs(duration-a['duration_seconds'])>0.01:
                raise ValueError('WAV duration mismatch')
            clips[name]=duration
        images={}
        for a in d['images']:
            if a['filename'] not in names or a['filename'] in images:
                raise ValueError('missing or duplicated image')
            if hashlib.sha256(z.read(a['filename'])).hexdigest()!=a['sha256']:
                raise ValueError('image checksum mismatch')
            images[a['filename']]=a['source_second']
        reviewed=[]
        for w in d['windows']:
            name=w['clip']
            if name not in clips:
                raise ValueError('unresolvable clip reference')
            start=w['audio_start']; declared_end=w['audio_end']
            if not all(type(v) in (int,float) and math.isfinite(v) for v in [start,declared_end,w['start'],w['end']]):
                raise ValueError('invalid time')
            actual_end=start+clips[name]
            if abs(actual_end-declared_end)>0.02 or not start<=w['start']<w['end']<=actual_end+0.01:
                raise ValueError('WAV/citation offset mismatch')
            segments=[]
            for r in w['asr']:
                ss=r['start']; ee=r['end']
                if not all(type(v) in (int,float) and math.isfinite(v) for v in [ss,ee]) or not ss<ee:
                    raise ValueError('bad ASR time')
                audible_from=max(ss,start);audible_to=min(ee,actual_end)
                audible=max(0,audible_to-audible_from)
                missing=max(0,ee-max(ss,actual_end)) + max(0,min(ee,start)-ss)
                truncated=missing>0.015
                if truncated!=r['audio_excerpt_truncated']:
                    raise ValueError('manifest truncation flag disagrees with WAV')
                if abs(r['audible_end_seconds']-min(ee,declared_end))>0.02:
                    raise ValueError('manifest audible end differs from WAV')
                segments.append({'id':r['id'],'start_seconds':ss,'end_seconds':ee,
                    'audible_seconds':round(audible,3),'missing_seconds':round(missing,3),
                    'audio_coverage_complete':not truncated,'teacher_words_verified':False,
                    'trade_authorized':False})
            reviewed.append({'citation_id':w['id'],'queue_video':w['queue_video'],'clip':name,
                'source_audio_start':start,'source_audio_end':round(actual_end,3),
                'machine_asr':segments,'teacher_semantics_verified':False,'action':'NO_TRADE'})
        return {'schema':'artin_6_original_av_playable_coverage_v2',
            'clip_count':len(clips),'source_windows':len(reviewed),'original_images_verified':len(images),
            'cases':reviewed,'independently_listened_to_audio':False,
            'teacher_semantics_certified':False,'orders_authorized':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('packet_zip');p.add_argument('output_json')
    a=p.parse_args();result=audit_packet(a.packet_zip)
    pathlib.Path(a.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))

if __name__=='__main__':main()