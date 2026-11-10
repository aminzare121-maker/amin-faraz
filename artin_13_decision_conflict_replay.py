"""Build evidence-grounded decision review packets, not teacher-verified trade rules.

Machine ASR can contain student questions and lexical false positives. This script
prioritizes original audiovisual replay. It never authorizes orders or certifies
speaker identity. Public results should exclude source text.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import math
import re
from pathlib import Path

EXPECTED_ROUTES = frozenset('''BREAK_STRONG BREAK_VERY_STRONG_RETEST BREAK_WEAK_FULLBODY_EXCEPTION BREAK_WEAK_PIVOT PULLBACK_STANDARD REVERSAL_CLASSIC REVERSAL_STAR REVERSAL_THREE STOPPUNCH_DOJI_AHEAD STOPPUNCH_DOJI_TIED STOPPUNCH_OPPOSITE_CONFIRMATION STOPPUNCH_S22_SELL_CONFIRMED_PAUSE STOPPUNCH_SAME_COLOUR'''.split())
ENTER = re.compile(r'ورود|وارد|پوزیشن|معامله')
NEGATE = re.compile(r'نمی\s*کن|نکن|نباید|نمی\s*شو|ممنوع|نه\s*وارد')
QUESTION = re.compile(r'استاد|سوال|سؤال|چرا|یعنی|\?')


def classify_candidate(text):
    """Lexical candidate only. ASR wording and role remain UNVERIFIED."""
    if not isinstance(text, str):
        raise ValueError('ASR text must be a string')
    clean = text.replace('\u200c', ' ').replace('ي', 'ی').replace('ك', 'ک')
    if ENTER.search(clean):
        return 'NEGATED_ENTRY_MENTION' if NEGATE.search(clean) else 'ENTRY_MENTION_UNVERIFIED'
    if QUESTION.search(clean):
        return 'QUESTION_OR_SPEAKER_REVIEW'
    return 'OTHER_CONTEXT'


def analyze(doc, interval_limit=20.):
    if not isinstance(doc, dict) or not isinstance(doc.get('citations'), list):
        raise ValueError('Invalid source review manifest')
    citations = doc['citations']
    if len(citations)!=24 or sorted(c['citation_index'] for c in citations)!=list(range(1,25)):
        raise ValueError('Citation inventory must be exactly 1-24')
    if {c['route_id'] for c in citations} != EXPECTED_ROUTES:
        raise ValueError('Unexpected or absent source route')
    if not isinstance(interval_limit,(int,float)) or not math.isfinite(interval_limit) or not 0<interval_limit<=120:
        raise ValueError('Invalid adjacency threshold')
    byroute=defaultdict(lambda:{'citations':[],'events':{},'collision_pairs':[]})
    all_occ=[]
    original_identity={}
    for c in citations:
        ix,route,session=c['citation_index'],c['route_id'],c['session']
        start,end=c['start_seconds'],c['end_seconds']
        if type(session) is not int or not 1<=session<=25 or not (0<=start<end):
            raise ValueError('Invalid source window')
        if len(c['excerpts'])!=c['overlap_asr_rows'] or len(c['excerpts'])!=c['expected_machine_asr_rows']:
            raise ValueError('Citation excerpt count mismatch')
        row=byroute[route]
        row['citations'].append({'index':ix,'session':session,'start_seconds':start,'end_seconds':end})
        seen=set()
        for e in c['excerpts']:
            segment_id=e['asr_segment_id']
            key=(session,segment_id)
            if key in seen: raise ValueError('Repeated source excerpt within one citation')
            seen.add(key)
            a,b=e['start'],e['end']
            if not (isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isfinite(a) and math.isfinite(b) and 0<=a<b and a<=end and b>=start):
                raise ValueError('Excerpt outside citation interval')
            source=(a,b,e['text_unverified'],e['original_audio_sha256'],e['record_id'])
            if key in original_identity and original_identity[key]!=source:
                raise ValueError('Source identity changed in repeated citations')
            original_identity[key]=source
            event={'session':session,'source_segment_id':segment_id,
                'record_id':e['record_id'],'start_seconds':a,'end_seconds':b,
                'text_unverified':e['text_unverified'],
                'source_audio_sha256':e['original_audio_sha256'],
                'candidate_class':classify_candidate(e['text_unverified']),
                'possible_student_question':bool(QUESTION.search(e['text_unverified'])),
                'citation_indices':[],'teacher_role_verified':False,
                'original_words_independently_verified':False,
                'visual_decision_verified':False,'trade_action':'NO_TRADE'}
            if key not in row['events']:row['events'][key]=event
            row['events'][key]['citation_indices'].append(ix)
            all_occ.append((route,ix,key))
    result=[]
    for route,row in sorted(byroute.items()):
        ev=sorted(row['events'].values(),key=lambda e:(e['session'],e['start_seconds'],e['source_segment_id']))
        for e in ev:e['citation_indices']=sorted(set(e['citation_indices']))
        collision=[]
        # Only *potential* polarity flip within same session, not an established teacher contradiction.
        mentions=[e for e in ev if e['candidate_class'] in ('NEGATED_ENTRY_MENTION','ENTRY_MENTION_UNVERIFIED')]
        for i,e in enumerate(mentions):
            for other in mentions[i+1:]:
                if other['session']!=e['session']:continue
                gap=other['start_seconds']-e['end_seconds']
                if gap>interval_limit:break
                if e['candidate_class']!=other['candidate_class'] and gap>=-10.:
                    collision.append({'session':e['session'],'first_segment_id':e['source_segment_id'],
                        'second_segment_id':other['source_segment_id'],'time_gap_seconds':round(gap,2),
                        'status':'NEEDS_ORIGINAL_AV_SPEAKER_AND_CHART_REPLAY_NO_TRADE'})
        counts={kind:sum(x['candidate_class']==kind for x in ev) for kind in (
          'NEGATED_ENTRY_MENTION','ENTRY_MENTION_UNVERIFIED','QUESTION_OR_SPEAKER_REVIEW','OTHER_CONTEXT')}
        result.append({'route_id':route,'citation_windows':sorted(row['citations'],key=lambda x:x['index']),
          'unique_source_segments':len(ev),'lexical_counts':counts,
          'candidate_polarity_flips':collision,
          'events':ev,'teacher_semantics_certified':False,
          'teacher_example_replay_passed':False,'trades_authorized':0})
    if len(result)!=13:
        raise ValueError("Route count mismatch")
    summary={'schema':'artin_13_teacher_decision_conflict_review_v1','citations':24,
      'routes':13,'source_excerpt_occurrences':len(all_occ),
      'unique_session_segment_ids':len(original_identity),
      'route_segment_references':sum(len(r['events']) for r in result),
      'candidate_polarity_flip_pairs':sum(len(r['candidate_polarity_flips']) for r in result),
      'machine_words_or_speaker_independently_verified':False,
      'teacher_decisions_certified':0,'mt5_orders_authorized':0}
    return {'summary':summary,'routes':result}


def public_projection(result):
    return {'summary':result['summary'],'routes':[{
      'route_id':r['route_id'],'citations':[w['index'] for w in r['citation_windows']],
      'unique_source_segments':r['unique_source_segments'],
      'lexical_counts':r['lexical_counts'],
      'candidate_polarity_flip_pairs':len(r['candidate_polarity_flips']),
      'teacher_semantics_certified':False,'trades_authorized':0
    } for r in result['routes']],
      'limitation':'Lexical polarity is NOT a teacher decision or proven contradiction. It is a review queue; never turn these candidates into market orders.'}


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('source_private_json');p.add_argument('private_output');p.add_argument('public_output')
    a=p.parse_args()
    src=json.loads(Path(a.source_private_json).read_text(encoding='utf-8'))
    report=analyze(src)
    Path(a.private_output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    Path(a.public_output).write_text(json.dumps(public_projection(report),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False))
if __name__=='__main__':main()