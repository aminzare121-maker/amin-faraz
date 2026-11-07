#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run source-verified Persian OCR over actual sampled classroom chat frames.

This is OCR CANDIDATE coverage, not verified student messages, post time,
speaker identity, exact question-answer correspondence, or trading rules.
Stores only private outputs and short numeric metrics in GitHub logs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from artin_persian_chat_ocr_trial_v7 import reading_order_fa,sha

def write_atomic(path,content):
    tmp=path.with_name(path.name+".part")
    tmp.write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(tmp,path)

def _valid_source_row(row,root):
    ref=row.get('chat',{})
    if not isinstance(ref,dict) or not isinstance(ref.get('sha256'),str):
        raise ValueError('Chat frame hash is missing')
    f=(root/ref.get('path','')).resolve()
    if not f.is_relative_to(root.resolve()) or not f.is_file() or sha(f)!=ref['sha256']:
        raise ValueError('Cannot OCR unsourced or changed chat image')
    if not isinstance(row.get('frame_id'),str) or not isinstance(row.get('time_seconds'),(int,float)):
        raise ValueError('Frame identity/time missing')
    return f

def ocr_frames(original_visual_root,index,output,*,max_frames=0,
               ocr_factory=None,checkpoint_every=10,
               partition_index=0,partition_count=1):
    if index.get('schema') not in ('artin_classroom_visual_v6','artin_change_selected_chat_v8'):
        raise ValueError('Original video visual index required')
    video_sha=index.get('source_video_sha256')
    if not isinstance(video_sha,str) or len(video_sha)!=64:
        raise ValueError('Original video SHA unavailable')
    rows=index.get('rows')
    if not isinstance(rows,list) or not rows:
        raise ValueError('No original classroom screenshots')
    if type(max_frames) is not int or max_frames<0 or max_frames>100000:
        raise ValueError('Invalid frame limit')
    if (type(partition_index) is not int or type(partition_count) is not int or
        not 1<=partition_count<=16 or not 0<=partition_index<partition_count):
        raise ValueError('Invalid independent OCR partition')
    root=Path(original_visual_root).resolve()
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    available=rows if not max_frames else rows[:max_frames]
    chosen=[row for pos,row in enumerate(available)
            if pos%partition_count==partition_index]
    if not chosen:raise ValueError('Partition has no selected source frames')
    # Every frame must first pass source validation before importing a third
    # party OCR model. No mislabeled screenshot can silently enter output.
    files=[_valid_source_row(r,root) for r in chosen]
    if ocr_factory is None:
        from paddleocr import PaddleOCR
        ocr_factory=PaddleOCR
    model=ocr_factory(lang='fa',use_doc_orientation_classify=False,
                  use_doc_unwarping=False,use_textline_orientation=False)
    started=time.monotonic()
    results=[];failed=[]
    private_path=out/'full_chat_ocr_candidates_PRIVATE.json'
    for i,(row,path) in enumerate(zip(chosen,files),1):
        try:
            first=model.predict(str(path))[0]
            raw=list(first.get('rec_texts',[]))
            scores=list(first.get('rec_scores',[]))
            boxes=first.get('rec_boxes')
            if boxes is None:
                # PaddleOCR returns no boxes for a legitimately empty chat.
                # No detected text is NOT an OCR engine failure; only
                # recognized text with absent source geometry is unsafe.
                if raw:
                    raise ValueError('Missing OCR geometry for recognized Persian text')
                ordered=[]
            else:
                ordered=reading_order_fa(raw,scores,boxes)
            state='OCR_TEXT_CANDIDATES' if ordered else 'OCR_NO_READABLE_TEXT'
            candidates=[]
            for j,x in enumerate(ordered):
                t=x['ocr_candidate']
                # A question mark may finish a 2-line question; include the
                # preceding line as context, without attributing it to a student.
                if '؟' in t or '?' in t:
                    prev=ordered[j-1]['ocr_candidate'] if j and x['visual_line_index']>0 else ''
                    candidates.append({'possible_question_text':
                          (prev+' '+t).strip()[:400],
                          'image_text_human_verified':False,
                          'actual_student_message_verified':False})
            results.append({'frame_id':row['frame_id'],
                 'time_original_video_seconds':row['time_seconds'],
                 'global_chunk':row['global_chunk'],'batch':row['batch'],
                 'slot':row['slot'],
                 'source_frame_sha256':row['chat']['sha256'],
                 'text_lines':ordered,
                 'possible_typed_questions':candidates,
                 'message_post_time_unknown':True,
                 'teacher_answer_verified':False,
                 'source_text_verified':False,
                 'state':state})
        except Exception as exc:
            failed.append({'frame_id':row['frame_id'],
                           'error_type':type(exc).__name__,
                           'private_diagnostic':str(exc)[:360]})
            results.append({'frame_id':row['frame_id'],
                 'time_original_video_seconds':row['time_seconds'],
                 'global_chunk':row['global_chunk'],
                 'source_frame_sha256':row['chat']['sha256'],
                 'state':'OCR_FAILED_REVIEW_REQUIRED',
                 'error_type':type(exc).__name__,
                 'private_diagnostic':str(exc)[:360],
                 'source_text_verified':False,
                 'teacher_answer_verified':False})
        if i%checkpoint_every==0 or i==len(chosen):
            write_atomic(private_path,{'schema':'artin_full_original_chat_ocr_v7',
                  'source_video_sha256':video_sha,
                  'frames_total':len(rows),'frames_targeted':len(chosen),
                  'frames_attempted':i,'complete':i==len(chosen),
                  'partition_index':partition_index,'partition_count':partition_count,
                  'human_verified_chat_messages':0,'teacher_answers_verified':0,
                  'rules_executable':0,'results':results})
            print('ARTIN_CHAT_OCR_PROGRESS='+json.dumps({
                  'attempted':i,'total':len(chosen),
                  'failed':len(failed),'time_elapsed_seconds':round(time.monotonic()-started,2)},
                  ensure_ascii=False),flush=True)
    summary={'schema':'artin_original_chat_ocr_coverage_v7',
        'source_video_sha256':video_sha,'source_frames_total':len(rows),
        'partition_index':partition_index,'partition_count':partition_count,
        'frames_targeted':len(chosen),'frames_attempted':len(results),
        'frames_with_some_ocr_text':sum(r['state']=='OCR_TEXT_CANDIDATES' for r in results),
        'frames_without_detected_text':sum(r['state']=='OCR_NO_READABLE_TEXT' for r in results),
        'ocr_failed_frames':len(failed),
        'ocr_error_types':{key:sum(x['error_type']==key for x in failed)
                           for key in sorted({x['error_type'] for x in failed})},
        'frames_with_question_mark_candidates':sum(bool(r.get('possible_typed_questions')) for r in results),
        'elapsed_seconds':round(time.monotonic()-started,2),
        'human_verified_typed_messages':0,
        'valid_teacher_question_answer_pairs':0,
        'verified_teacher_rules':0,
        'population_OCR_accuracy':None,
        'sampled_frames_are_not_every_video_frame':True,
        'status':'SOURCE_LINKED_UNVERIFIED_OCR_FINISHED' if not failed else 'PARTIAL_OCR_NEEDS_RETRY'}
    write_atomic(out/'full_chat_ocr_summary_safe.json',summary)
    print('ARTIN_FULL_SOURCE_CHAT_OCR='+json.dumps(summary,ensure_ascii=False),flush=True)
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--visual-root',type=Path,required=True)
    p.add_argument('--visual-index',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-frames',type=int,default=0)
    p.add_argument('--partition-index',type=int,default=0)
    p.add_argument('--partition-count',type=int,default=1)
    a=p.parse_args()
    index=json.loads(a.visual_index.read_text(encoding='utf8'))
    summary=ocr_frames(a.visual_root,index,a.out,max_frames=a.max_frames,
                      partition_index=a.partition_index,partition_count=a.partition_count)
    if summary['ocr_failed_frames']:
        raise SystemExit(2)

if __name__=='__main__':main()
