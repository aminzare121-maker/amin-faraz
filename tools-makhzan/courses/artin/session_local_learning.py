# -*- coding: utf-8 -*-
"""Session-local concept learning: never detach a teacher utterance from its class."""
import json,collections,sys
from pathlib import Path
TOPICS={'market':('فارکس','بازار','قیمت','ارز','طلا','انس','جفت ارز'),'tools':('متاتریدر','بروکر','حساب','لات','چارت','نمودار','تتر','دلار','صرافی'),'execution':('ورود','خروج','خرید','فروش','معامله','پوزیشن','کندل','روند'),'risk':('ریسک','ضرر','استاپ','حد ضرر','حد سود','سرمایه','مدیریت','سود'),'learning':('روان','ترس','طمع','تمرین','آموزش','سوال','سؤال','اشتباه','صبر','تجربه')}
def labels(t):
 t=str(t).replace('ي','ی').replace('ك','ک')
 return [k for k,words in TOPICS.items() if any(w in t for w in words)]
def build(sessions):
 out=[]
 for session in sessions:
  seg=sorted(session.get('speech',[]),key=lambda x:float(x['start']))
  bins=collections.defaultdict(list)
  for x in seg:bins[int(float(x['start'])//300)].append(x)
  windows=[]
  for b,parts in sorted(bins.items()):
   counts=collections.Counter(topic for s in parts for topic in labels(s.get('text','')))
   questions=[q for q in session.get('questions',[]) if b*300<=float(q.get('time_seconds',q.get('start',0)))<(b+1)*300]
   examples=[{'time_seconds':s['start'],'speech':s.get('text',''),'before':parts[i-1].get('text','') if i else '', 'after':parts[i+1].get('text','') if i+1<len(parts) else '', 'concepts':labels(s.get('text','')),'speaker_verified':False} for i,s in enumerate(parts) if labels(s.get('text',''))]
   windows.append({'start_seconds':b*300,'end_seconds':(b+1)*300,'concept_counts':dict(counts),'contextual_examples':examples,'question_candidates':questions,'teacher_action_verified':False,'engine_replay_ready':False})
  out.append({'session_id':session['session_id'],'speech_segments':len(seg),'windows':windows})
 return {'schema':'artin_session_specific_learning_v1','sessions':out,'no_invented_teacher_rules':True,'original_engine_unchanged':True}
if __name__=='__main__':
 src=json.loads(Path(sys.argv[1]).read_text(encoding='utf8'))
 Path(sys.argv[2]).write_text(json.dumps(build(src['sessions']),ensure_ascii=False,indent=2),encoding='utf8')
