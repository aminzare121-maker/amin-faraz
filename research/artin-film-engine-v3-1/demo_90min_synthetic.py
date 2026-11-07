#!/usr/bin/env python3
"""End-to-end fake transcripts on a real 90-minute *synthetic video*.
No teacher, no real data, no ASR, no model, no trading. Demonstrates 18-way
video splitting and full-timeline Q&A + late correction stitching.
"""
import argparse
import json
from pathlib import Path
import artin_film_pipeline as p


def example(video, root, workers=3):
    m=p.prepare(Path(video),Path(root),workers=workers,frames_per_chunk=1)
    if len(m['chunks']) != 18:
        raise ValueError('This demo expects a 90-minute artificial video')
    msgs = {
        1:[(1,298.8,299.6,'پرسش ساختگی: اینجا چرا باید صبر کنیم؟')],
        2:[(1,301,305,'پاسخ ساختگی: چون تأیید کندل هنوز بسته نشده است'),
           (2,320,326,'قانون فرضی: با بسته شدن کندل خرید می‌کنیم')],
        18:[(1,5320,5328,'اصلاح فرضی قانون: نه، فقط بسته شدن کافی نیست')]
    }
    for c in m['chunks']:
        s=[]
        for n,start,end,txt in msgs.get(c['chunk'],[]):
            s.append({'id':f"c{c['chunk']:02d}_u{n:04d}",'start':start,
                      'end':end,'text':txt,'speaker':'UNKNOWN','speaker_verified':False})
        p.atomic_json(Path(root)/c['transcript'],{'schema':'artin_chunk_transcript_v1',
            'chunk':c['chunk'],'source_clip_sha256':c['clip_sha256'],
            'asr':'SYNTHETIC_DEMO_NOT_REAL_SPEECH','segments':s})
        events=[]
        for u in s:
            kind=('QUESTION' if c['chunk']==1 else 'CORRECTION' if c['chunk']==18 else
                  'RULE' if u['start']==320 else 'ANSWER')
            raw={'events':[{'kind':kind,'source_ids':[u['id']],'exact_quote':u['text'],
                'rule_label':'قانون فرضی' if kind in ('RULE','CORRECTION') else '',
                'decision':'BUY' if kind=='RULE' else 'NO_TRADE' if kind=='CORRECTION' else 'UNKNOWN',
                'conditions':[]}]}
            data,rejections=p.validate_model_events(raw,s,c)
            if rejections:raise AssertionError(rejections)
            events.extend(data)
        p.atomic_json(Path(root)/c['analysis'],{
            'schema':'artin_chunk_analysis_v1','chunk':c['chunk'],
            'model_name':'NO_MODEL_SYNTHETIC_DEMO','interpretation_verified':False,
            'events':events,'rejections':[]})
    summary=p.merge(root)
    video_result=p.remux_chapters(root,Path(root)/'source_with_18_chapters.mp4')
    result={
        'experiment':'SYNTHETIC_VIDEO_AND_SYNTHETIC_DIALOGUE_NOT_TEACHER_REVIEW',
        'video_parts':len(m['chunks']),
        'frame_samples':sum(len(c['frames']) for c in m['chunks']),
        'dialogue_question_answer_edges':summary['possible_question_answer_links'],
        'later_rule_correction_edges':summary['possible_later_corrections'],
        'candidate_rule_groups':summary['candidate_rule_groups'],
        'generated_video_has_chapters':video_result['chapters'],
        'teacher_rules_verified':0,
        'actual_speech_transcribed':False,
        'actual_visual_semantics_understood':False,
        'trading_engine_modified':False,
        'orders_sent':0,
    }
    p.atomic_json(Path(root)/'SYNTHETIC_DEMO_REPORT.json',result)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=3)
    a=parser.parse_args()
    print(json.dumps(example(a.video,a.out,a.workers),indent=2,ensure_ascii=False))
