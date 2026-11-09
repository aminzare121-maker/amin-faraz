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
