#!/usr/bin/env python3
"""Fail-closed diagnostics of the original nested V13 evidence artifact."""
import argparse,hashlib,io,json,zipfile
from pathlib import Path

def audit(path):
    raw=Path(path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        nested=[n for n in outer.namelist() if n.endswith('.zip')]
        if len(nested)!=1:raise ValueError('Expected exactly one nested source ZIP')
        with zipfile.ZipFile(io.BytesIO(outer.read(nested[0]))) as archive:
            speech=[];visuals=[];sources=[]
            for name in archive.namelist():
                if not name.endswith('.json'):continue
                channel='speech' if name.startswith('speech_asr_raw/') else 'visual' if name.startswith(('board_ocr_raw/','student_chat_ocr_raw/')) else None
                if not channel:continue
                payload=archive.read(name);doc=json.loads(payload)
                sources.append({'file':name,'sha256':hashlib.sha256(payload).hexdigest()})
                if channel=='speech':
                    for seg in doc.get('segments',[]):
                        if isinstance(seg,dict) and isinstance(seg.get('start'),(int,float)):
                            speech.append({'start':seg['start'],'end':seg.get('end'),'text':seg.get('text',''),'source':name,'id':seg.get('id'),'confidence':seg.get('avg_logprob')})
                else:
                    for frame in doc.get('results',[]):
                        if not isinstance(frame,dict) or not isinstance(frame.get('time_original_video_seconds'),(int,float)):continue
                        lines=[x.get('ocr_candidate','') for x in frame.get('text_lines',[]) if isinstance(x,dict)]
                        if not lines and isinstance(frame.get('machine_text_raw'),str):lines=[frame['machine_text_raw']]
                        if lines:visuals.append({'start':frame['time_original_video_seconds'],'text':' | '.join(lines),'source':name,'id':frame.get('frame_id')})
    speech.sort(key=lambda x:x['start']);visuals.sort(key=lambda x:x['start'])
    if len(speech)<100 or len(visuals)<50:raise ValueError('Original evidence coverage insufficient')
    flags=[];matched=0
    for i,s in enumerate(speech):
        t=s['start'];end=s['end'];problems=[]
        if not isinstance(end,(int,float)) or end<=t:problems.append('INVALID_DURATION')
        elif end-t>12:problems.append('LONG_SEGMENT')
        if i and isinstance(speech[i-1]['end'],(int,float)) and t-speech[i-1]['end']>15:problems.append('SPEECH_GAP')
        if isinstance(s['confidence'],(int,float)) and s['confidence']<-.7:problems.append('LOW_ASR_CONFIDENCE')
        nearest=min(visuals,key=lambda v:abs(v['start']-t))
        delta=round(nearest['start']-t,3)
        if abs(delta)<=8:matched+=1
        if problems:flags.append({'time_seconds':t,'source':s['source'],'segment_id':s['id'],'flags':problems,'speech':s['text'],'nearest_visual_source':nearest['source'],'nearest_visual_time_delta':delta,'nearest_visual_text':nearest['text'][:400],'requires_original_audio_comparison':True})
    return {'status':'DIAGNOSTIC_ONLY','source_sha256':hashlib.sha256(raw).hexdigest(),'source_files':sources,'speech_segments':len(speech),'visual_frames':len(visuals),'speech_near_visual':matched,'flag_count':len(flags),'flags':flags,'teacher_semantics_verified':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source_zip');parser.add_argument('output_json');args=parser.parse_args()
    result=audit(args.source_zip);Path(args.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('SPEECH',result['speech_segments'],'VISUAL',result['visual_frames'],'FLAGS',result['flag_count'])
