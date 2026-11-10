"""Restore the full audio envelope of a previously short review excerpt.
It never changes or certifies machine ASR, speaker attribution or trading logic.
"""
from __future__ import annotations
import hashlib,io,json,re,wave,zipfile
from pathlib import Path

SOURCE_WAV_MEMBER='audio/batch_001/part_16.wav'
SOURCE_SHA='d0ab09ee0452930b246ab6ad34ce6cc982f2284f7efa694e253890c13e0d3afe'
SOURCE_CUT_START=4488.0
SOURCE_CUT_END=4812.0
EXCERPT_NAME='source_window_06_video22_4694-4728.wav'
NEW_EXCERPT_START=4689.0
NEW_EXCERPT_END=4743.55
TARGET_ASR='asr_p016_00063'

def extract_original(source_archive):
    with zipfile.ZipFile(source_archive) as z:
        audio=z.read(SOURCE_WAV_MEMBER)
        manifest_name=next(n for n in z.namelist() if n.endswith('fast_av_manifest.json'))
        manifest=json.loads(z.read(manifest_name))
    if hashlib.sha256(audio).hexdigest()!=SOURCE_SHA:
        raise ValueError('original source WAV SHA-256 mismatch')
    part=[x for x in manifest['parts'] if x.get('chunk')==16]
    if len(part)!=1 or part[0]['cut_start']!=SOURCE_CUT_START or part[0]['cut_end']!=SOURCE_CUT_END:
        raise ValueError('original source timebase mismatch')
    if part[0]['audio_sha256']!=SOURCE_SHA:raise ValueError('source AV manifest SHA mismatch')
    with wave.open(io.BytesIO(audio),'rb') as w:
        rate=w.getframerate()
        if (rate,w.getnchannels(),w.getsampwidth())!=(16000,1,2):raise ValueError('original audio shape mismatch')
        if abs(w.getnframes()/rate-(SOURCE_CUT_END-SOURCE_CUT_START))>0.001:raise ValueError('original audio duration mismatch')
        if NEW_EXCERPT_END>SOURCE_CUT_END:raise ValueError('audio exceeds original source')
        offset=round((NEW_EXCERPT_START-SOURCE_CUT_START)*rate)
        length=round((NEW_EXCERPT_END-NEW_EXCERPT_START)*rate)
        w.setpos(offset)
        pcm=w.readframes(length)
        if len(pcm)!=length*2:raise ValueError('truncated source audio')
    out=io.BytesIO()
    with wave.open(out,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm)
    return out.getvalue()

def repair(source_archive,old_packet,output):
    restored=extract_original(source_archive)
    with zipfile.ZipFile(old_packet) as zin:
        names=zin.namelist()
        if names.count(EXCERPT_NAME)!=1 or names.count('manifest.json')!=1 or names.count('index.html')!=1:
            raise ValueError('invalid original review packet')
        manifest=json.loads(zin.read('manifest.json'))
        target=[x for x in manifest['windows'] if x['id']=='ARTIN-RESTORED-06']
        if len(target)!=1 or target[0]['audio_end']!=4733.0 or target[0]['audio_start']!=NEW_EXCERPT_START:
            raise ValueError('unexpected earlier packet audio span')
        target=target[0]
        old_asr=[x for x in target['asr'] if x['id']==TARGET_ASR]
        if len(old_asr)!=1 or old_asr[0]['end']!=4738.55 or old_asr[0]['audio_excerpt_truncated'] is not True:
            raise ValueError('unexpected previously truncated segment')
        target['audio_end']=NEW_EXCERPT_END
        for x in target['asr']:
            x['audio_excerpt_truncated']=x['end']>NEW_EXCERPT_END
            x['audible_end_seconds']=min(x['end'],NEW_EXCERPT_END)
        if any(x['audio_excerpt_truncated'] for x in target['asr']):
            raise ValueError('some ASR excerpts remain outside actual WAV')
        manifest['schema']='artin_6_original_av_listening_packet_v2_restored_original_WAV'
        manifest['source_recovery']={'source':'GitHub Actions original audio artifact 13679791669',
          'source_audio_sha256':SOURCE_SHA,'source_video_seconds':[SOURCE_CUT_START,SOURCE_CUT_END],
          'old_review_excerpt_end':4733,'new_review_excerpt_end':NEW_EXCERPT_END,
          'restored_original_audio_seconds':round(NEW_EXCERPT_END-4733,2),
          'audio_coverage_complete_for_asr_63':True,
          'independent_teacher_speech_verification':False,'trade_authorized':False}
        html=zin.read('index.html').decode('utf-8')
        old=' [انتهای قطعه صوتی ناقص است]'
        if html.count(old)!=1:raise ValueError('original HTML truncated annotation count mismatch')
        html=html.replace(old,' [صوت اصلی این جمله بازیابی شد؛ متن ماشینی هنوز تأیید نشده است]')
        tmp=Path(output)
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
            for name in names:
                if name=='manifest.json': b=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
                elif name=='index.html':b=html.encode('utf-8')
                elif name==EXCERPT_NAME:b=restored
                else:b=zin.read(name)
                zout.writestr(name,b)
    return {'schema':'artin_restored_audio_review_v22_v2','source_audio_sha256_verified':True,
        'source_audio_manifest_verified':True,'old_clip_end':4733.0,'new_clip_end':NEW_EXCERPT_END,
        'original_source_cut_end':SOURCE_CUT_END,'recovered_review_audio_seconds':NEW_EXCERPT_END-4733,
        'asr_segment_end':4738.55,'asr_segment_fully_audible':True,
        'independent_teacher_semantic_verification':False,'orders_authorized':0,
        'review_packet':str(output),'restored_wav_sha256':hashlib.sha256(restored).hexdigest()}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source_archive');p.add_argument('old_packet');p.add_argument('new_packet');p.add_argument('report')
    a=p.parse_args();r=repair(a.source_archive,a.old_packet,a.new_packet)
    Path(a.report).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r,ensure_ascii=False))