#!/usr/bin/env python3
"""Build a privacy-preserving, source-anchored review queue for all 25 Artin lessons.

Input is privately held Behrooz machine ASR/OCR archives, NOT certified
teacher meaning. Hypothetical states are treated as legitimate teaching
scenarios, without implying a historical trade occurred. Never places trades.
"""
import argparse
import hashlib
import json
import re
import zipfile
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

FIRST = 'بهروز.zip'
LATER = 'Artin_22_Sessions_Speech_OCR_Review_20261109.zip'
SHA = re.compile(r'^[0-9a-f]{64}$')
MARKET_ANCHORS = ('چارت', 'نمودار', 'کندل', 'پولبک', 'پیوت', 'اسپرد', 'بروکر', 'فارکس', 'پوزیشن', 'حد ضرر', 'استاپ', 'روند', 'حمایت', 'مقاومت', 'نقدینگی', 'مارکت', 'متاتریدر', 'لات', 'ریوارد', 'تارگت', 'بای', 'سل', 'معامله')
CONDITIONS = ('اگر', 'فرض', 'وقتی', 'مثلا', 'مثلاً', 'در صورتی', 'به شرط', 'هر وقت', 'زمانی که', 'چنانچه')
TOPIC_TERMS = {
    'entry': ('ورود', 'بخر', 'بفروش', 'خرید', 'فروش', 'پوزیشن', 'معامله بگیری', 'سل بگیری', 'بای بگیری', 'نقطه ورود'),
    'exit': ('خروج', 'ببند', 'میبند', 'می بند', 'تارگت', 'تی پی', 'سیو سود', 'حد سود'),
    'risk': ('حد ضرر', 'استاپ', 'استاپ لاس', 'ریسک', 'حداکثر ضرر', 'سربه سر', 'ریوارد', 'حجم معامله'),
    'market_state': ('روند', 'کندل', 'پولبک', 'پیوت', 'حمایت', 'مقاومت', 'نقدینگی', 'شکست', 'اوردر بلاک', 'اردربلاک'),
    'execution_mechanics': ('بید', 'اسک', 'اسپرد', 'لات', 'بروکر', 'متاتریدر', 'کمیسیون'),
}

def norm(text):
    return re.sub(r'\s+', ' ', str(text or '').replace('ي', 'ی').replace('ك', 'ک')).strip()

def get_rows(z, member):
    if member not in z.namelist():
        raise ValueError('Missing source member: ' + member)
    for i, b in enumerate(z.read(member).splitlines(), 1):
        if not b.strip():
            continue
        try: yield json.loads(b)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f'{member} bad JSONL at {i}: {exc}') from exc

def check_sha(v):
    return isinstance(v, str) and bool(SHA.fullmatch(v))

def load(root):
    lessons = {}
    with zipfile.ZipFile(root / FIRST) as z:
        for session in (1, 2, 3):
            p = f'DERIVED_NOT_RAW/VIDEO_{session:02d}/'
            rows = []
            for r in get_rows(z, p + 'SPEECH_TIMELINE_MACHINE_UNVERIFIED.jsonl'):
                t, e = r.get('start_seconds'), r.get('end_seconds')
                sha = r.get('source_video_sha256')
                if not isinstance(t,(int,float)) or not isinstance(e,(int,float)) or t > e or t < 0 or not check_sha(sha) or not check_sha(r.get('source_audio_sha256')):
                    raise ValueError('Invalid first-three source speech anchor, lesson '+str(session))
                rows.append({'start':t,'end':e,'text':norm(r.get('original_machine_text')),
                    'segment':r.get('original_segment_id'),'audio_sha':r.get('source_audio_sha256'),
                    'video_sha':sha,'raw_visual':[]})
            boards = []
            for frame in get_rows(z, p + 'BOARD_OCR_MACHINE_UNVERIFIED.jsonl'):
                time = frame.get('board_image_t')
                if isinstance(time,(int,float)) and check_sha(frame.get('source_image_sha256')):
                    boards.append({'kind':'board_OCR_machine_unverified', 'time':float(time),
                        'sha':frame['source_image_sha256'], 'file':frame.get('source_image_path')})
            boards.sort(key=lambda x:x['time']); frames_t = [f['time'] for f in boards]
            for row in rows:
                mid=(row['start']+row['end'])/2
                loc=bisect_left(frames_t, mid)
                neighbors=(boards[j] for j in (loc-1,loc) if 0<=j<len(boards))
                row['raw_visual']=[dict(f,delta_seconds=round(f['time']-mid,3)) for f in neighbors if abs(f['time']-mid)<=8]
            lessons[session] = rows
    with zipfile.ZipFile(root / LATER) as z:
        for session in range(4,26):
            member=f'session_{session:02d}_speech_visual_UNVERIFIED.jsonl'
            rows=[]
            for r in get_rows(z, member):
                start,end=r.get('time_start'),r.get('time_end')
                if r.get('sequence')!=session or not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or start<0 or end<start or not check_sha(r.get('source_audio_sha256')):
                    raise ValueError(f'Invalid speech source/time in lesson {session}')
                vv=[]
                for v in r.get('visual_candidates',[]):
                    if (isinstance(v,dict) and isinstance(v.get('time'),(int,float))
                            and check_sha(v.get('frame_sha256'))):
                        vv.append({'kind':v.get('kind','unclassified_visual'),
                                   'time':v['time'],'sha':v['frame_sha256'],
                                   'file':v.get('source_path',v.get('visual_id')),
                                   'delta_seconds':round(v['time']-start,3)})
                rows.append({'start':start,'end':end,'text':norm(r.get('speech_exact')),
                    'segment':r.get('speech_source_id'),'audio_sha':r['source_audio_sha256'],
                    'video_sha':None,'raw_visual':vv})
            lessons[session]=rows
    if sorted(lessons)!=list(range(1,26)) or any(not value for value in lessons.values()):
        raise ValueError('Incomplete 25 lesson coverage')
    return lessons

def candidate_score(rows,i):
    row=rows[i]
    context=norm(' '.join(r['text'] for r in rows[max(0,i-3):min(len(rows),i+4)]))
    phrase=row['text']
    topics=[topic for topic,terms in TOPIC_TERMS.items() if any(w in context for w in terms)]
    condition=any(w in context for w in CONDITIONS)
    specific=any(w in phrase for w in CONDITIONS) and any(w in phrase for topic in ('entry','exit','risk','market_state') for w in TOPIC_TERMS[topic])
    value=2*len(topics)+int(condition)*3+int(specific)*4+int(bool(row['raw_visual']))+int(len(phrase)>20)
    return value,topics,condition,context

def build(root,per_session=6,spacing=100):
    lessons=load(root)
    public=[];private=[];prev_by_topic={}
    links=[]
    for lesson,rows in lessons.items():
        ranked=[]
        for i,row in enumerate(rows):
            score,topics,conditional,context=candidate_score(rows,i)
            if not topics or score<4: continue
            if not any(t in topics for t in ('entry','exit','risk','market_state')):continue
            ranked.append((score,i,topics,conditional,context))
        ranked.sort(key=lambda q:(-q[0],q[1]))
        picks=[]
        for score,i,topics,conditional,context in ranked:
            t=rows[i]['start']
            if any(abs(t-rows[j]['start'])<spacing for _,j,*_ in picks):continue
            picks.append((score,i,topics,conditional,context))
            if len(picks)>=per_session:break
        picks.sort(key=lambda q:rows[q[1]]['start'])
        case_ids=[]
        for score,i,topics,conditional,context in picks:
            row=rows[i]
            origin=f'{lesson}:{row["start"]:.3f}:{row.get("segment")}:{row["audio_sha"]}'
            cid='ARTIN-SC-'+hashlib.sha256(origin.encode('utf-8')).hexdigest()[:16]
            is_hypothetical=any(w in context for w in CONDITIONS)
            market_anchor=any(w in context for w in MARKET_ANCHORS)
            linked=[]
            for topic in topics:
                past=prev_by_topic.get(topic)
                if past and past['session']<lesson:
                    linked.append({'earlier_case_id':past['case_id'],'earlier_session':past['session'],
                                   'topic':topic,'relation':'POSSIBLE_LEXICAL_CONTINUITY_ONLY',
                                   'teacher_revision_or_exception_verified':False})
                    links.append({'earlier':past['case_id'],'later':cid,'topic':topic,
                                  'chronological':True,'instruction_supersession_verified':False})
                prev_by_topic[topic]={'case_id':cid,'session':lesson}
            source={'segment_id':row['segment'],'source_audio_sha256':row['audio_sha'],
                    'source_video_sha256_if_available':row['video_sha']}
            vis=[v for v in row['raw_visual'] if abs(v['delta_seconds'])<=8]
            case={
                'case_id':cid,'session':lesson,'time_start_seconds':row['start'],
                'time_end_seconds':row['end'],'speech_machine_candidate':row['text'],
                'context_machine_candidate':context,'source_anchor':source,
                'visual_candidates':vis[:3], 'topics_for_review_only':topics,
                'conditional_or_hypothetical_cue':is_hypothetical,
                'market_specific_anchor_present':market_anchor,
                'candidate_class': ('HYPOTHETICAL_MARKET_SCENARIO_FOR_REVIEW' if is_hypothetical and market_anchor else 'MARKET_DESCRIPTION_FOR_REVIEW' if market_anchor else 'GENERAL_ANALOGY_NOT_A_TRADE_RULE'),
                'hypothetical_is_legitimate_teaching_scenario':True,
                'source_verified_to_be_historical_trade':False,
                'speaker_independently_verified':False,
                'utterance_against_original_audio_verified':False,
                'teaching_meaning_verified':False,
                'entry_exit_exception_order_complete':False,
                'teacher_expected_decision':None,'motor_observed_decision':None,
                'replay_result':'BLOCKED_PENDING_ORIGINAL_SOURCE_SEMANTIC_REVIEW',
                'prior_related_candidates':linked,'allow_mt5_trade':False,
            }
            private.append(case);case_ids.append(cid)
        public.append({'session':lesson,'machine_speech_rows':len(rows),
                       'candidate_review_cases':len(case_ids),
                       'cases_with_nearby_image':sum(bool(c['visual_candidates']) for c in private if c['session']==lesson),
                       'audio_review_complete':False,'semantic_rules_approved':0})
    return ({'schema':'artin_25_session_full_review_queue_v1',
             'source':'private Behrooz machine ASR/OCR zip archives',
             'session_count':len(public),'cases_for_human_audio_visual_review':len(private),
             'hypothetical_scenarios_preserved':sum(c['conditional_or_hypothetical_cue'] for c in private),
             'cases_with_nearby_image':sum(bool(c['visual_candidates']) for c in private),
             'market_specific_cases':sum(c['market_specific_anchor_present'] for c in private),
             'general_analogies_needing_classroom_relevance_review':sum(not c['market_specific_anchor_present'] for c in private),
             'lexical_cross_lesson_links':len(links),
             'per_session':public,'cases':private,
             'links':links, 'independently_verified_teacher_decisions':0,
             'motor_teacher_decisions_compared':0,'allow_mt5_trade':False,
             'status':'REVIEW_QUEUE_READY_NOT_SEMANTICALLY_CERTIFIED'},
            {'schema':'artin_25_session_review_index_v1',
             'sessions':public,'candidate_count':len(private),
             'links_not_approved':len(links),
             'hypothetical_teaching_examples_rejected_only_for_hypothetical':0,
             'approved_teacher_rules':0,'motor_ready':False})

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--private-out',required=True,type=Path)
    p.add_argument('--public-summary-out',type=Path)
    p.add_argument('--per-session',type=int,default=6)
    a=p.parse_args()
    if not 1<=a.per_session<=50:raise SystemExit('per-session must be 1..50')
    private,summary=build(a.root,a.per_session)
    a.private_out.write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if a.public_summary_out:a.public_summary_out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'sessions':private['session_count'],'candidate_review_cases':len(private['cases']),
                      'cross_lesson_lexical_links':len(private['links']),
                      'cases_with_nearby_image':private['cases_with_nearby_image'],
                      'semantic_rules_approved':0},ensure_ascii=False))

if __name__=='__main__':main()