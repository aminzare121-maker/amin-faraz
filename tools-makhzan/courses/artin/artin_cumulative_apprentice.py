#!/usr/bin/env python3
"""Incremental, source-bound concept learning; never imports trading rules."""
import argparse,collections,json,re
from pathlib import Path
STOP=set('این اون آن از به با که در را رو برای و یا یک یه من ما شما تو او هم هست است بود شده میشه میکنه میکنم میکنید اگر بعد قبل خیلی الان همین اونجا اینجا باید یعنی خب خوب حالا پس تا دیگه هر چه چی چرا چطور کجا فقط وقتی مثلا داریم دوست دوستان استاد کلاس جلسه سوال سؤال جواب'.split())
def tokens(t):
    t=str(t).replace('ي','ی').replace('ك','ک').replace('‌',' ')
    return set(w for w in re.findall(r'[\u0600-\u06FF]{3,}',t) if w not in STOP)
def build(sessions,limit=100):
    out={'schema':'artin_apprentice_v1','sessions':[],'concepts':{},'links':[],'certified_trading_rules':[],'policy':'SOURCE_MEANING_FIRST; NEVER IMPORT OUTSIDE STRATEGY'}
    for sequence,s in enumerate(sessions,1):
        sid=s['session_id']
        if any(x['session_id']==sid for x in out['sessions']):raise ValueError('duplicate session')
        speech=sorted(s.get('speech',[]),key=lambda r:float(r['start']))
        loc=collections.defaultdict(list)
        for i,row in enumerate(speech):
            for w in tokens(row.get('text','')):loc[w].append(i)
        ranked=sorted((w for w in loc if len(loc[w])>=3),key=lambda w:(-len(loc[w]),w))[:limit]
        for w in ranked:
            concept=out['concepts'].setdefault(w,{'first_session':sid,'meaning':'OPEN','teacher_belief':'NOT_PROVEN','student_understanding':'NOT_PROVEN','history':[]})
            examples=[]
            for i in loc[w][:4]:
                row=speech[i]
                examples.append({'time_seconds':float(row['start']),'source_id':row.get('id'),'text':row.get('text',''),
                    'before':speech[i-1].get('text','') if i else None,
                    'after':speech[i+1].get('text','') if i+1<len(speech) else None})
            if concept['history']:
                out['links'].append({'term':w,'previous_session':concept['history'][-1]['session_id'],'current_session':sid,
                    'semantic_continuity_verified':False,'status':'LEXICAL_BRIDGE_ONLY'})
            concept['history'].append({'session_id':sid,'count':len(loc[w]),'examples':examples,
                'interpretation':'OPEN_FOR_LATER_LESSONS','revision_allowed':True})
        questions=[]
        for q in s.get('questions',[]):
            t=float(q.get('time_seconds',q.get('start',0)))
            questions.append({'time_seconds':t,'question_candidate':q.get('text',''),
                'following_speech':[{'start':r['start'],'text':r.get('text','')} for r in speech if t<=float(r['start'])<=t+35][:8],
                'teacher_answer_verified':False})
        out['sessions'].append({'sequence':sequence,'session_id':sid,'speech_segments':len(speech),
            'concepts_as_spoken':ranked,'questions':questions,'meaning_status':'IN_PROGRESS'})
    out['counts']={'sessions':len(out['sessions']),'speech_segments':sum(s['speech_segments'] for s in out['sessions']),
        'concepts':len(out['concepts']),'lexical_links':len(out['links']),'verified_rules':0}
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');a=p.parse_args()
    data=json.loads(Path(a.input).read_text(encoding='utf8'))
    result=build(data['sessions'])
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result['counts'],ensure_ascii=False))
