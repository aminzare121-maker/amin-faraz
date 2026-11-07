#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional local-only multimodal analysis of sourced chat/board crops.

Needs a user-installed Ollama vision model. Zero remote uploads from this code.
Outputs are candidates for human/source review, NOT verified reading,
teacher identity, or executable strategies.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from artin_film_pipeline import ollama_json
from artin_student_chat_review_v6 import validate_visual_model_candidates


SYSTEM_PROMPT="""You are examining ONE screenshot cropped from a Persian online trading class.
Your job is only to report VISIBLE words (Persian or English) if legible.
Typed student chat is a separate channel from handwritten teacher notes.
Return exactly one JSON object with:
{"visible_text_candidate":"...","legibility":"HIGH|MEDIUM|LOW|UNKNOWN"}.
If text is too blurry or unreadable, return empty visible_text_candidate and LOW.
Do not guess any missing words, student names, indicator levels, candles,
trading rules, speaker identity, market outcomes, or teacher answers.
Do not treat typing on-screen as a spoken answer.
An image remains UNVERIFIED even if the text looks readable.
"""


def scan_local_visual(root,visual_index,model,*,max_frames=5,endpoint='http://127.0.0.1:11434',
                      call_model=None):
    if not isinstance(model,str) or not model.strip():
        raise ValueError('Vision model name required')
    if type(max_frames) is not int or not 1<=max_frames<=5000:
        raise ValueError('Invalid maximum frame count')
    if visual_index.get('schema')!='artin_classroom_visual_v6':
        raise ValueError('Original source-indexed images required')
    if call_model is None:
        call_model=ollama_json
    root=Path(root).resolve()
    proposals=[]
    failed=[]
    chosen=visual_index['rows'][:max_frames]
    for row in chosen:
        for channel in ('chat','board'):
            filename=(root/row[channel]['path']).resolve()
            if not filename.is_relative_to(root) or not filename.is_file():
                raise ValueError('Original image crop is missing or unsafe')
            from artin_film_pipeline import file_sha256
            if file_sha256(filename)!=row[channel]['sha256']:
                raise ValueError('Original image was tampered with')
            prompt=json.dumps({'channel':channel,
                'frame_id':row['frame_id'],
                'source_time_seconds':row['time_seconds'],
                'task':'Read only legible visible text from this crop. Never reconstruct missing letters.',
                'do_not_infer_teacher_rules':True},ensure_ascii=False)
            try:
                raw=call_model(model,prompt,frames=[str(filename)],
                    endpoint=endpoint,system_prompt=SYSTEM_PROMPT)
                if not isinstance(raw,dict):
                    raise ValueError('Invalid vision model JSON')
                txt=raw.get('visible_text_candidate')
                if not isinstance(txt,str):
                    raise ValueError('Vision JSON missing a text field')
                if not txt.strip():
                    failed.append({'frame_id':row['frame_id'],
                        'channel':channel,'status':'UNREADABLE_OR_NO_TEXT'})
                    continue
                proposals.append({'frame_id':row['frame_id'],'channel':channel,
                    'frame_sha256':row[channel]['sha256'],
                    'visible_text_candidate':txt,
                    'legibility':raw.get('legibility','UNKNOWN')})
            except Exception as exc:
                # Explicit failure; do NOT fabricate text or silently continue
                # as though the screenshot had been analyzed.
                failed.append({'frame_id':row['frame_id'],'channel':channel,
                    'status':'MODEL_FAILED','error_type':type(exc).__name__})
    if len(failed)==len(chosen)*2:
        raise RuntimeError('Vision model yielded no usable text in selected source frames')
    valid=validate_visual_model_candidates(visual_index,proposals)
    return {'schema':'artin_visual_ai_candidate_scan_v6',
            'source_video_sha256':visual_index['source_video_sha256'],
            'model':model,'frames_requested':len(chosen),
            'views_attempted':len(chosen)*2,
            'provisional_text_observations':valid['candidate_count'],
            'candidates':valid['candidates'],
            'missing_or_unreadable':failed,
            'verified_typed_student_questions':0,
            'verified_teacher_chart_rules':0,
            'can_change_artin_engine':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--visual-root',required=True,type=Path)
    p.add_argument('--visual-index',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--model',default='qwen2.5vl:3b')
    p.add_argument('--max-frames',type=int,default=5)
    p.add_argument('--endpoint',default='http://127.0.0.1:11434')
    a=p.parse_args()
    index=json.loads(a.visual_index.read_text(encoding='utf8'))
    report=scan_local_visual(a.visual_root,index,a.model,max_frames=a.max_frames,
                             endpoint=a.endpoint)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'status':'UNVERIFIED_IMAGE_TEXT_CANDIDATES',
        'frames_requested':report['frames_requested'],
        'observations':report['provisional_text_observations'],
        'verified_teacher_rules':0},ensure_ascii=False))


if __name__=='__main__':main()
