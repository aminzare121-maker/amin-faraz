#!/usr/bin/env python3
"""Transcribe real user-provided teacher video on ephemeral GitHub runner.
Unverified ASR cannot create trading rules. Original audio is never committed.
"""
import argparse
import json
import os
import subprocess
import time
import wave
from pathlib import Path

from artin_ephemeral_remote_ingest import get_direct_url


def extract_audio_from_remote(url, dest, seconds):
    cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
         '-i',url,'-t',str(seconds),'-vn','-ac','1','-ar','16000',
         '-c:a','pcm_s16le',str(dest)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
    if p.returncode:raise RuntimeError('FFmpeg extraction failed: '+p.stderr[-300:])
    if not dest.is_file() or dest.stat().st_size<10000:
        raise ValueError('Empty WAV')
    with wave.open(str(dest),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
            raise ValueError('Invalid WAV format')
        return round(w.getnframes()/w.getframerate(),3)


def read_pcm_array(filename):
    import numpy as np
    with wave.open(str(filename),'rb') as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
            raise ValueError('Only mono 16-bit 16kHz supported')
        frames=w.readframes(w.getnframes())
    # Use numeric samples to avoid unsupported PyAV kwargs in this environment.
    return np.frombuffer(frames,dtype='<i2').astype('float32')/32768.0


def transcribe_audio(audio,model_name,output,minutes):
    from faster_whisper import WhisperModel
    start=time.monotonic()
    model=WhisperModel(model_name,device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
    loaded=time.monotonic()-start
    start=time.monotonic()
    result,info=model.transcribe(audio,language='fa',vad_filter=True,beam_size=5,
                                 condition_on_previous_text=False,word_timestamps=False)
    utterances=[]
    for i,s in enumerate(result):
        if s.end<=s.start:continue
        utterances.append({'id':f'asr_{i+1:04d}', 'start':round(float(s.start),3),
           'end':round(float(s.end),3),'text':s.text.strip(),
           'avg_logprob':round(float(s.avg_logprob),4),
           'no_speech_prob':round(float(s.no_speech_prob),4),
           'speaker':'UNKNOWN','speaker_verified':False,
           'audio_reviewed_against_original':False,'can_change_artin_engine':False})
    inference=time.monotonic()-start
    doc={'schema':'artin_real_asr_trial_v5','model':model_name,'language':'fa',
         'source':'PRIVATE_USER_CLASS_VIDEO','minutes':minutes,
         'transcript_verified':False,'speaker_verified':False,'rules_verified':0,
         'segments':utterances}
    (output/'unverified_transcript.json').write_text(
         json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
    report={'status':'UNVERIFIED_REAL_AUDIO_TRANSCRIPTION','model':model_name,
         'minutes':minutes,'segment_count':len(utterances),
         'model_load_seconds':round(loaded,2),'inference_seconds':round(inference,2),
         'total_characters':sum(len(u['text']) for u in utterances),
         'low_logprob_segments':sum(u['avg_logprob']<-.9 for u in utterances),
         'rules_verified':0,'needs_human_review':True}
    (output/'trial_report.json').write_text(
         json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='large-v3-turbo')
    p.add_argument('--minutes',type=int,default=5)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if not 1<=a.minutes<=10:raise ValueError('Trial limited to 1-10 minutes')
    a.out.mkdir(parents=True,exist_ok=True)
    page=os.environ.get('TEACHER_VIDEO_PAGE')
    if not page or not page.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Only authorized Uupload link accepted')
    direct,_=get_direct_url(page)
    seconds=extract_audio_from_remote(direct,a.out/'sample_private.wav',a.minutes*60)
    print('ARTIN_V5_AUDIO_EXTRACTED_SECONDS='+str(seconds),flush=True)
    audio=read_pcm_array(a.out/'sample_private.wav')
    print('ARTIN_V5_ASR_STARTED='+a.model,flush=True)
    result=transcribe_audio(audio,a.model,a.out,a.minutes)
    print('ARTIN_V5_ASR_TRIAL_REPORT='+json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
