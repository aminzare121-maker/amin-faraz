#!/usr/bin/env python3
"""Four-way temporary shard worker for actual teacher video. No media is committed.

Every shard downloads the SAME SHA-pinned source, samples audio and images
without transcoding video, then produces only ASR candidates for global
chunk IDs assigned by modulo partition. Teacher authority remains UNKNOWN.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time

from artin_ephemeral_remote_ingest import download, get_direct_url
from artin_fast_av_v4 import fast_prepare, validate_fast
from artin_real_asr_trial_v5 import read_pcm_array


def process_shard(source_page: str, root: Path, shard: int, shard_count: int,
                  expected_sha: str, model_name='large-v3-turbo'):
    if not 0<=shard<shard_count<=17:
        raise ValueError('Invalid concurrent partition')
    if not source_page.startswith('https://my.uupload.ir/p/'):
        raise ValueError('Only an explicitly supplied user Uupload page accepted')
    root.mkdir(parents=True,exist_ok=True)
    url,_=get_direct_url(source_page)
    start=time.monotonic()
    private_mp4=root/'source_ephemeral.mp4'
    size,sha=download(url,private_mp4)
    if sha!=expected_sha:
        raise ValueError('Video SHA differs from expected source: abort full-course merge')
    manifest=fast_prepare(private_mp4,root/'fast',workers=4,frames_per_part=2)
    validate_fast(root/'fast',manifest,verify_files=True)
    selected=[p for p in manifest['parts'] if (p['chunk']-1)%shard_count==shard]
    if not selected:
        raise ValueError('Partition has no assigned parts')
    print('ARTIN_SHARD_READY='+json.dumps({'index':shard,'number_of_parts':len(selected),
        'source_parts':len(manifest['parts']),'part_indices':[p['chunk'] for p in selected],
        'source_sha256':sha,'source_bytes':size},ensure_ascii=False),flush=True)
    from faster_whisper import WhisperModel
    model=WhisperModel(model_name,device='cpu',compute_type='int8',
                       cpu_threads=4,num_workers=1)
    output=root/'asr_evidence'
    output.mkdir(exist_ok=True)
    for part in selected:
        audio=read_pcm_array(root/'fast'/part['audio'])
        st=time.monotonic()
        segments,info=model.transcribe(audio,language='fa',vad_filter=True,
                        beam_size=5,condition_on_previous_text=False,
                        word_timestamps=False)
        utterances=[]
        for i,seg in enumerate(segments):
            begin=part['cut_start']+float(seg.start)
            end=min(part['cut_end'],part['cut_start']+float(seg.end))
            if end<=begin:continue
            utterances.append({'id':f"asr_p{part['chunk']:03d}_{i:05d}",
                'start':round(begin,3),'end':round(end,3),
                'text':seg.text.strip(),'speaker':'UNKNOWN',
                'speaker_verified':False,
                'avg_logprob':round(float(seg.avg_logprob),4),
                'no_speech_prob':round(float(seg.no_speech_prob),4)})
        doc={'schema':'artin_asr_shard_v5','global_chunk':part['chunk'],
             'source_video_sha256':sha,'source_audio_sha256':part['audio_sha256'],
             'timebase':'absolute_original_video_seconds',
             'model':model_name,'speaker_human_verified':False,
             'teacher_rules_verified':False,'segments':utterances}
        (output/f"part_{part['chunk']:03d}_unverified.json").write_text(
            json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')
        print('ARTIN_SHARD_COMPLETED_PART='+json.dumps({'global_chunk':part['chunk'],
               'transcript_segments':len(utterances),
               'asr_seconds':round(time.monotonic()-st,2)},ensure_ascii=False),
               flush=True)
    if shard==0:
        manifest.pop('video_path_private',None)
        (output/'manifest_redacted.json').write_text(
            json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    status={'schema':'artin_asr_partition_v5','shard_index':shard,
            'partition_count':shard_count,
            'source_video_sha256':sha,
            'expected_global_parts':[p['chunk'] for p in selected],
            'completed_global_parts':[p['chunk'] for p in selected],
            'source_part_count':len(manifest['parts']),
            'elapsed_seconds':round(time.monotonic()-start,2),
            'all_speakers_verified':False,'rules_executable':0,
            'full_course_ready':False}
    (output/f'partition_{shard}_status.json').write_text(
        json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
    print('ARTIN_PARTITION_SUMMARY='+json.dumps(status,ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--index',required=True,type=int)
    p.add_argument('--partitions',required=True,type=int)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--model',default='large-v3-turbo')
    a=p.parse_args()
    page=os.environ.get('TEACHER_VIDEO_PAGE','')
    process_shard(page,a.out,a.index,a.partitions,a.expected_sha256,a.model)


if __name__=='__main__':main()
