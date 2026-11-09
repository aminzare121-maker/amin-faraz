#!/usr/bin/env python3
"""Classroom-first reading of source ASR: identify Q/A turns and candidate lessons.
Does not invent teacher statements or certify audio fidelity."""
import io,json,re,sys,zipfile
from pathlib import Path
QUESTIONS=('سؤال','سوال','چرا','چطور','چگونه','یعنی','نیازه','میشه','میتونم','می تونم','چی','کدوم','آیا','؟','?')
TOPICS={'broker_account':('بروکر','حساب','ای پلانت','ایپیلانت','مارکت'),
'metatrader':('متاتریدر','میتا تریدر','متا تریدر','لات','اسپرد','سپرید','کمیسیون','کامشن'),
'strategy':('استراتژی','استریت','ای تی سی','ایتی سی','ورود','خروج','خرید','فروش','حد ضرر','حد سود')}
def process(segments):
    segments=sorted(segments,key=lambda s:float(s.get('start',0)))
    result=[];questions=[];topics=[]
    for i,s in enumerate(segments):
        t=float(s['start']);txt=s.get('text','').strip()
        if not txt:continue
        context=' '.join(x.get('text','') for x in segments[max(0,i-2):min(len(segments),i+3)])
        if any(q in txt for q in QUESTIONS) and len(txt)>5:
            before=segments[max(0,i-3):i];after=segments[i+1:min(len(segments),i+11)]
            questions.append({'time_seconds':t,'question_candidate':txt,
              'prior_context':' '.join(x.get('text','') for x in before),
              'response_candidate':' '.join(x.get('text','') for x in after),
              'teacher_or_student_not_proven':True,'audio_review_required':True})
        hits=[k for k,words in TOPICS.items() if any(w in context for w in words)]
        if hits:
            topics.append({'time_seconds':t,'text':txt,'topics':hits})
    return {'status':'CLASSROOM_CONTEXT_RECONSTRUCTED_NOT_AUDIO_VERIFIED',
       'speech_segments':len(segments),'question_answer_candidates':questions,
       'topic_utterances':topics,'verified_teacher_rules':0,
       'notes':'Question and answer roles are hypotheses; only original speech can establish speaker identity.'}
def main(src,dst):
    with zipfile.ZipFile(src) as outer:
        inner=next(x for x in outer.namelist() if x.endswith('.zip'))
        with zipfile.ZipFile(io.BytesIO(outer.read(inner))) as z:
            seg=[]
            for f in z.namelist():
                if re.search(r'speech_asr_raw/part_\d+_unverified\.json$',f):
                    seg.extend(json.loads(z.read(f)).get('segments',[]))
    if len(seg)<100:raise RuntimeError('Insufficient real source speech')
    result=process(seg)
    Path(dst).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('CLASSROOM',result['speech_segments'],'QUESTION_CANDIDATES',len(result['question_answer_candidates']))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
