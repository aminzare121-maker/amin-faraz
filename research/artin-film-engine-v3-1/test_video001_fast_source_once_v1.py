#!/usr/bin/env python3
"""Synthetic-only zero-speech integration fixture to test full SHA-timeline join.

The synthetic sine-wave movie has NO teacher/lesson; fixture creates no
transcription or user-supplied content. Successful test proves SOFTWARE
contracts only; never label it a real teaching-video accuracy benchmark.
"""
from __future__ import annotations
import json
from pathlib import Path
from video001_fast_verify_v1 import verify

def write(path,doc):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf8')

def test(root):
    root=Path(root)
    prep=root/'safe_source_prep_summary.json'
    source=root/'full_chat'/'chat_selected_index.json'
    visual=json.loads(source.read_text())
    src_sha=visual['source_video_sha256']
    manifest=json.loads((root/'asr_shards'/'worker_00'/'fast_av_manifest.json').read_text())
    audio=root/'fake_empty_asr'
    write(audio/'manifest_redacted.json',manifest)
    parts=manifest['parts']
    assert len(parts)==1 and len(visual['rows'])>=1
    for p in parts:
        write(audio/f"part_{p['chunk']:03d}_unverified.json",{
            'schema':'artin_asr_shard_v5','global_chunk':p['chunk'],
            'source_video_sha256':src_sha,
            'source_audio_sha256':p['audio_sha256'],
            'timebase':'absolute_original_video_seconds','model':'SYNTHETIC_NO_SPEECH',
            'speaker_human_verified':False,'teacher_rules_verified':False,
            'segments':[]})
    write(audio/'partition_0_status.json',{
        'shard_index':0,'partition_count':1,'source_video_sha256':src_sha,
        'expected_global_parts':[1],'completed_global_parts':[1]})
    ocr=root/'fake_empty_ocr'/'video001-fast-ocr-0'
    rows=[]
    for row in visual['rows']:
        rows.append({
            'frame_id':row['frame_id'],
            'time_original_video_seconds':row['time_seconds'],
            'global_chunk':row['global_chunk'],
            'source_frame_sha256':row['chat']['sha256'],
            'state':'OCR_NO_READABLE_TEXT',
            'text_lines':[],'possible_typed_questions':[],
            'source_text_verified':False,'teacher_answer_verified':False})
    write(ocr/'full_chat_ocr_candidates_PRIVATE.json',{
        'schema':'artin_full_original_chat_ocr_v7',
        'partition_index':0,'partition_count':1,
        'source_video_sha256':src_sha,
        'frames_total':len(rows),'frames_targeted':len(rows),
        'frames_attempted':len(rows),'complete':True,
        'results':rows})
    out=root/'zero_speech_full_integration'
    result=verify(audio,ocr.parent,source,root/'board_review',prep,out,
                  audio_workers=1,ocr_workers=1)
    assert result['source_evidence_loss']==0
    assert result['source_chat_highres_screenshots']==len(rows)
    assert result['original_five_minute_audio_parts']==1
    assert result['original_asr_utterances']==0
    assert not result['trading_allowed']
    # Force mismatch and verify that video SHA tampering CANNOT pass validation.
    ocr_doc=json.loads((ocr/'full_chat_ocr_candidates_PRIVATE.json').read_text())
    ocr_doc['source_video_sha256']='0'*64
    write(ocr/'full_chat_ocr_candidates_PRIVATE.json',ocr_doc)
    try:
        verify(audio,ocr.parent,source,root/'board_review',prep,root/'expected_to_fail',
               audio_workers=1,ocr_workers=1)
        raise AssertionError('Incorrect original movie SHA was erroneously accepted')
    except ValueError:
        pass
    print('VIDEO001_FAST_COMPLETE_SYNTHETIC_ZERO_SPEECH_SHA_REJECTION_SUCCESS=True')

if __name__=='__main__':
    import sys
    test(sys.argv[1])
