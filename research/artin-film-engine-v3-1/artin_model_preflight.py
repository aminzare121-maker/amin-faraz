"""Honest readiness check for fully local Whisper + Ollama (no downloads)."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


def _valid_local_endpoint(value):
    url=urllib.parse.urlsplit(value)
    if (url.scheme!='http' or url.hostname not in ('localhost','127.0.0.1','::1')
            or url.username or url.password or url.query or url.fragment
            or url.path not in ('','/')):
        raise ValueError('Only LOCAL Ollama address is permitted')
    return value.rstrip('/')


def check(asr_model=None,ollama_model=None,endpoint='http://127.0.0.1:11434'):
    endpoint=_valid_local_endpoint(endpoint)
    checks={}
    for name in ('ffmpeg','ffprobe'):
        checks[name]=bool(shutil.which(name))
    checks['faster_whisper_python_installed']=importlib.util.find_spec('faster_whisper') is not None
    checks['local_asr_model_directory_exists']=bool(asr_model and Path(asr_model).is_dir())
    checks['ollama_local_server_responsive']=False
    checks['chosen_ollama_model_installed']=False
    checks['chosen_ollama_model_reports_vision_capability']=False
    model_errors=[]
    try:
        with urllib.request.urlopen(endpoint+'/api/tags',timeout=3) as response:
            data=json.load(response)
        checks['ollama_local_server_responsive']=True
        available={m.get('name') for m in data.get('models',[])}
        checks['chosen_ollama_model_installed']=bool(ollama_model in available)
        if checks['chosen_ollama_model_installed']:
            req=urllib.request.Request(endpoint+'/api/show',
                   json.dumps({'model':ollama_model}).encode('utf-8'),
                   headers={'Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req,timeout=5) as response:
                details=json.load(response)
            cap=details.get('capabilities',[])
            checks['chosen_ollama_model_reports_vision_capability']='vision' in cap
    except (OSError,ValueError,KeyError) as e:
        model_errors.append(type(e).__name__)
    checks['can_attempt_local_speech_transcription']=checks['ffmpeg'] and checks['faster_whisper_python_installed'] and checks['local_asr_model_directory_exists']
    checks['can_attempt_local_video_frame_understanding']=checks['ffmpeg'] and checks['chosen_ollama_model_reports_vision_capability']
    checks['can_attempt_full_local_analysis']=all((checks['can_attempt_local_speech_transcription'],checks['can_attempt_local_video_frame_understanding']))
    return {
        'schema':'artin_preflight_v3','checks':checks,'model_errors':model_errors,
        'all_video_contents_understood':False,
        'teacher_rules_verified':0,
        'recommendations':[t for cond,t in (
            (not checks['ffmpeg'],'Install FFmpeg and FFprobe'),
            (not checks['faster_whisper_python_installed'],'Install faster-whisper Python package'),
            (not checks['local_asr_model_directory_exists'],'Provide a previously downloaded local ASR model directory'),
            (not checks['ollama_local_server_responsive'],'Start Ollama on localhost'),
            (not checks['chosen_ollama_model_installed'],'Select/pull an installed local Ollama model'),
            (not checks['chosen_ollama_model_reports_vision_capability'],'Use an Ollama model with declared vision capability'),
        ) if cond]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asr-model',required=True)
    p.add_argument('--ollama-model',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    p.add_argument('--require-ready',action='store_true',help='Exit nonzero if full local audio+vision processing cannot start')
    a=p.parse_args()
    result=check(a.asr_model,a.ollama_model,a.endpoint)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.require_ready and not result['checks']['can_attempt_full_local_analysis']:
        raise SystemExit(2)

if __name__=='__main__':main()
