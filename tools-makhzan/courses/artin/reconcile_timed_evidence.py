#!/usr/bin/env python3
"""Align timed ASR with nearby OCR; temporal proximity is not semantic verification."""
import json,sys
from pathlib import Path

def seconds(v):
    if isinstance(v,(int,float)):return float(v)
    if isinstance(v,str):
        try:return float(v)
        except ValueError:
            try:
                parts=[float(x) for x in v.replace(',','.').split(':')]
                return sum(x*60**i for i,x in enumerate(reversed(parts)))
            except ValueError:return None
    return None


def extract_candidates(document,channel,source):
    """Read the observed original Artin ASR and OCR schemas, not guessed fields."""
    result=[]
    if not isinstance(document,dict):return result
    if channel=='asr':
        for seg in document.get('segments',[]):
            if not isinstance(seg,dict):continue
            t=seconds(seg.get('start'))
            if t is None or not isinstance(seg.get('text'),str):continue
            result.append({'channel':'asr','source':source,'start':t,'end':seconds(seg.get('end')),
                           'text':seg['text'],'speaker':seg.get('speaker','UNKNOWN'),
                           'source_segment_id':seg.get('id'),
                           'avg_logprob':seg.get('avg_logprob')})
    else:
        for frame in document.get('results',[]):
            if not isinstance(frame,dict):continue
            t=seconds(frame.get('time_original_video_seconds'))
            if t is None:continue
            lines=[line.get('ocr_candidate','') for line in frame.get('text_lines',[])
                   if isinstance(line,dict) and isinstance(line.get('ocr_candidate'),str)]
            if not lines and isinstance(frame.get('machine_text_raw'),str):
                lines=[frame['machine_text_raw']]
            if lines:
                result.append({'channel':channel,'source':source,'start':t,'end':t,
                               'text':' | '.join(lines),'source_frame_id':frame.get('frame_id'),
                               'source_frame_sha256':frame.get('source_frame_sha256')})
    return result

def reconcile(data,window=8):
    entries=data.get('candidates',[])
    speech=[x for x in entries if x.get('channel')=='asr' and seconds(x.get('start')) is not None]
    visual=[x for x in entries if x.get('channel')!='asr' and seconds(x.get('start')) is not None]
    result=[]
    for x in speech:
        t=seconds(x['start'])
        matches=[{'source':v.get('source'),'time_seconds':seconds(v['start']),'delta_seconds':round(seconds(v['start'])-t,3),'text':v.get('text','')} for v in visual if abs(seconds(v['start'])-t)<=window]
        result.append({'speech_source':x.get('source'),'speech_time_seconds':t,'speech_text':x.get('text',''),'speaker':'UNKNOWN','nearby_visual':sorted(matches,key=lambda y:abs(y['delta_seconds'])),'alignment_is_semantic_proof':False,'review_status':'NEEDS_AUDIO_VISUAL_COMPARISON'})
    return {'schema':'artin_crossmodal_reconciliation_v1','speech_count':len(speech),'visual_count':len(visual),'matched_speech_count':sum(bool(x['nearby_visual']) for x in result),'semantic_accuracy_verified':False,'items':result}

def main():
    src=Path(sys.argv[1]);dest=Path(sys.argv[2]);doc=json.loads(src.read_text(encoding='utf8'))
    output=reconcile(doc)
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
    if not output['speech_count']:
        raise SystemExit('ERROR: No timed ASR entries; cannot claim speech reconciliation succeeded')
    print('SPEECH='+str(output['speech_count'])+' MATCHED='+str(output['matched_speech_count'])+' VERIFIED=false')
if __name__=='__main__':main()
