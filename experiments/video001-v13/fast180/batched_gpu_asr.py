"""Experimental V13: one warm CUDA model processes original source WAV shards in batches.

Works only on pre-verified audio shards. NEVER rewrites V12 artifacts, media or
raw ASR from another run. Fast mode is a separate candidate requiring gold review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as fp:
        for block in iter(lambda:fp.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def verify_inputs(source,expected_sha):
    source=Path(source).resolve()
    manifest=json.loads((source/'fast_av_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('video_sha256')!=expected_sha or len(expected_sha)!=64:
        raise ValueError('VIDEO_SHA_MISMATCH')
    duration=float(manifest['duration_seconds'])
    if not math.isfinite(duration) or duration<=0:
        raise ValueError('INVALID_DURATION')
    parts=manifest.get('parts')
    if not isinstance(parts,list) or len(parts)!=math.ceil(duration/300):
        raise ValueError('MISSING_AUDIO_PARTS')
    originals=[]
    for n,p in enumerate(parts,1):
        if p.get('chunk')!=n:
            raise ValueError('MISSING_OR_OUT_OF_ORDER_AUDIO')
        audio=(source/p['audio']).resolve()
        if not audio.is_relative_to(source) or not audio.is_file():
            raise ValueError('AUDIO_PATH_ESCAPE_OR_ABSENT')
        if sha256(audio)!=p.get('audio_sha256'):
            raise ValueError('AUDIO_SHA_MISMATCH')
        if not (float(p['cut_start'])<=float(p['core_start'])<float(p['core_end'])<=float(p['cut_end'])<=duration+1):
            raise ValueError('INVALID_SOURCE_TIMELINE')
        originals.append((p,audio))
    return originals


def write_no_clobber(out,doc):
    out.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(doc,ensure_ascii=False,indent=2).encode('utf-8')
    if out.exists():
        if out.read_bytes()==content:
            return 'EXISTING_IDENTICAL_CHECKPOINT'
        raise FileExistsError('REFUSE_TO_OVERWRITE_RAW_OR_OTHER_MODEL_OUTPUT')
    # Do not replace: the first writer creates it exclusively.
    fd=os.open(out, os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as fp:
        fp.write(content)
    return 'NEW_UNALTERED_MODEL_OUTPUT'


def transcribe(originals,output,video_sha,*,gpu_index=0,gpu_count=1,batch_size=16,engine=None):
    if type(gpu_index) is not int or type(gpu_count) is not int or not 0<=gpu_index<gpu_count<=16:
        raise ValueError('INVALID_GPU_ASSIGNMENT')
    if type(batch_size) is not int or not 1<=batch_size<=64:
        raise ValueError('INVALID_BATCH_SIZE')
    selected=[(p,f) for p,f in originals if (p['chunk']-1)%gpu_count==gpu_index]
    if not selected:
        raise ValueError('EMPTY_GPU_SHARD')
    # Inject fake engine ONLY for unit tests. Real runs must have CUDA.
    if engine is None:
        from faster_whisper import WhisperModel,BatchedInferencePipeline
        import ctranslate2
        if ctranslate2.get_cuda_device_count()<=gpu_index:
            raise RuntimeError('CUDA_GPU_NOT_PRESENT_FAIL_CLOSED')
        model=WhisperModel('large-v3-turbo',device='cuda',device_index=gpu_index,
                          compute_type='float16',num_workers=1,cpu_threads=4)
        engine=BatchedInferencePipeline(model=model)
    started=time.monotonic();status=[]
    for p,src in selected:
        # Store EVERY returned output line, including overlapping windows. A
        # derived, review-only index may later filter by core timestamps.
        segments,info=engine.transcribe(str(src),language='fa',beam_size=5,
             vad_filter=True,condition_on_previous_text=False,batch_size=batch_size)
        rows=[]
        for seg in segments:
            rows.append({'start_relative':float(seg.start),'end_relative':float(seg.end),
                 'start_absolute':float(p['cut_start'])+float(seg.start),
                 'end_absolute':float(p['cut_start'])+float(seg.end),
                 'text_machine_raw':seg.text,
                 'speaker_verified':False,'human_text_verified':False,
                 'in_primary_window':float(p['core_start'])<=float(p['cut_start'])+(float(seg.start)+float(seg.end))/2<float(p['core_end'])})
        doc={'schema':'video001_v13_raw_batched_cuda_asr_candidate_v1',
             'source_video_sha256':video_sha,'global_chunk':p['chunk'],
             'source_audio_sha256':p['audio_sha256'],
             'model':'large-v3-turbo','engine':'faster-whisper-batched-cuda',
             'batch_size':batch_size,'source_speech_modified':False,
             'review_only':True,'teacher_rules_verified':0,
             'source_text_human_verified':False,'segments':rows}
        dest=Path(output)/f'gpu_{gpu_index:02d}'/f'raw_chunk_{p["chunk"]:03d}.json'
        action=write_no_clobber(dest,doc)
        if sha256(src)!=p['audio_sha256']:
            raise ValueError('SOURCE_CHANGED_DURING_INFERENCE')
        status.append({'chunk':p['chunk'],'status':action,'segments':len(rows)})
    return {'cuda_gpu_index':gpu_index,'chunks_processed':len(status),
            'elapsed_seconds':round(time.monotonic()-started,2),'source_sha256':video_sha,
            'segments_total':sum(x['segments'] for x in status),'status':'CUDA_ASR_CANDIDATE_NOT_TEACHING_VERIFIED',
            'chunks':status}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-audio-root',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--video-sha256',required=True)
    p.add_argument('--gpu-index',type=int,default=0)
    p.add_argument('--gpu-count',type=int,default=1)
    p.add_argument('--batch-size',type=int,default=16)
    a=p.parse_args()
    source=a.source_audio_root.resolve();out=a.out.resolve()
    if source==out or source.is_relative_to(out) or out.is_relative_to(source):
        raise ValueError('CANDIDATE_OUTPUT_MUST_NOT_TOUCH_SOURCE')
    originals=verify_inputs(source,a.video_sha256)
    result=transcribe(originals,out,a.video_sha256,
         gpu_index=a.gpu_index,gpu_count=a.gpu_count,batch_size=a.batch_size)
    print('V13_CUDA_ASR_CANDIDATE='+json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()