"""Fail-closed verification of ASR negative-entry review candidates; never trade approval."""
from collections import defaultdict
from math import isfinite
import re

PATTERNS=(r'نمی\s*کن(?:یم|م|ید)',r'نکن(?:یم|م|ید|)',r'نباید')
def negative(text):
    if not isinstance(text,str):return False
    text=text.replace('\u200c',' ').replace('ي','ی').replace('ك','ک')
    return any(re.search(p,text) for p in PATTERNS)
def time_valid(start,end):
    return (type(start) in (int,float) and type(end) in (int,float) and
        isfinite(start) and isfinite(end) and 0<=start<end)
def audit(citation_doc,polarity_doc):
    if not isinstance(citation_doc,dict) or not isinstance(citation_doc.get('citations'),list):
        raise ValueError('invalid citation source')
    if not isinstance(polarity_doc,dict) or not isinstance(polarity_doc.get('routes'),list):
        raise ValueError('invalid review source')
    index=defaultdict(list)
    for cit in citation_doc['citations']:
        if not isinstance(cit,dict) or not isinstance(cit.get('excerpts'),list):
            raise ValueError('invalid citation')
        session,route=cit.get('session'),cit.get('route_id')
        if type(session) is not int or not 1<=session<=25 or not isinstance(route,str) or not route:
            raise ValueError('invalid source identity')
        for e in cit['excerpts']:
            if not isinstance(e,dict) or not isinstance(e.get('asr_segment_id'),str) or not e['asr_segment_id']:
                raise ValueError('invalid segment id')
            if not time_valid(e.get('start'),e.get('end')):
                raise ValueError('invalid source time')
            index[(session,e['asr_segment_id'])].append((route,e))
    cases={}
    for route in polarity_doc['routes']:
        if not isinstance(route,dict) or not isinstance(route.get('cases'),list):
            raise ValueError('invalid review route')
        for case in route['cases']:
            if case.get('polarity_triage')!='POSSIBLE_NEGATED_ENTRY':continue
            key=(case.get('session'),case.get('segment_id'))
            matches=index.get(key,[])
            if not matches:raise ValueError('source missing')
            same_route=[e for route_id,e in matches if route_id==route.get('route_id')]
            if not same_route:raise ValueError('route identity mismatch')
            t=case.get('start_seconds')
            if type(t) not in (int,float) or not isfinite(t) or not any(e['start']==t for e in same_route):
                raise ValueError('timestamp mismatch')
            variants={(e.get('text_unverified'),e.get('original_audio_sha256'),e['start'],e['end']) for _,e in matches}
            if len(variants)!=1:raise ValueError('conflicting source versions')
            phrase,sha,start,end=next(iter(variants))
            if not negative(phrase):raise ValueError('negation unsupported')
            if not isinstance(sha,str) or not sha.strip():raise ValueError('audio reference missing')
            if key not in cases:
                cases[key]={'session':key[0],'segment_id':key[1],'start_seconds':start,'end_seconds':end,
                    'text_unverified':phrase,'audio_source_sha256':sha,'assigned_routes':set(),
                    'teacher_semantics_verified':False,'action':'NO_TRADE'}
            cases[key]['assigned_routes'].add(route['route_id'])
    if not cases:raise ValueError('no negative-entry evidence to verify')
    values=[]
    for x in sorted(cases.values(),key=lambda d:(d['session'],d['start_seconds'],d['segment_id'])):
        x['assigned_routes']=sorted(x['assigned_routes'])
        values.append(x)
    return {'schema':'artin_negative_entry_gate_v2','unique_cases':len(values),'cases':values,
            'teacher_semantics_verified':False,'orders_authorized':0}
