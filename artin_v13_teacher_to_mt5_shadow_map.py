#!/usr/bin/env python3
"""Connect actual Artin source-citation readiness records to MT5 shadow statuses.

This is a read-only evidence mapping. It cannot certify human listening or
conclude market eligibility. In particular it never accepts a 'verified' flag
from an unauthenticated JSON document as a trading authorization.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from artin_mt5_shadow_bridge import ROUTES

REQUIRED_REVIEWS=(
 'original_audio_independent_listening',
 'teacher_student_speaker_review',
 'original_chart_referent_review',
 'entry_exit_exception_decision_order_review',
 'cross_session_revisions_review',
 'teacher_example_vs_engine_replay',
)

def compile_shadow_evidence(source:dict)->dict:
    if not isinstance(source,dict) or not isinstance(source.get('routes'),list):
        raise ValueError('source acceptance queue missing')
    records=source['routes']
    if len(records)!=13 or {r.get('route_id') for r in records}!=set(ROUTES):
        raise ValueError('expected 13 unique teacher routes')
    total_citations=0;seen=set();result=[]
    for route in sorted(records,key=lambda x:x['route_id']):
        citations=route.get('citations')
        if not isinstance(citations,list) or not citations:raise ValueError('route missing citations')
        missing=route.get('missing_required_reviews')
        if not isinstance(missing,list) or set(missing)!=set(REQUIRED_REVIEWS):
            raise ValueError('cannot consume unreviewed or silently certified teacher case')
        if route.get('teacher_case_certified') is not False or route.get('engine_decision_replay_certified') is not False:
            raise ValueError('unverified JSON cannot approve lesson meaning')
        if route.get('orders_authorized')!=0:raise ValueError('trading disabled')
        session_set=set(route.get('source_sessions',[]))
        if not session_set or any(type(s) is not int or not 1<=s<=25 for s in session_set):
            raise ValueError('invalid source session')
        for c in citations:
            idx=c.get('citation_index');session=c.get('session')
            times=c.get('interval_seconds')
            if type(idx) is not int or idx in seen or not 1<=idx<=24:raise ValueError('duplicate/missing citation id')
            if session not in session_set or not isinstance(times,list) or len(times)!=2 or any(type(x) not in (int,float) for x in times) or not 0<=times[0]<times[1]:
                raise ValueError('invalid time or lesson reference')
            if c.get('audio_words_independently_verified') is not False or c.get('chart_visual_meaning_verified') is not False:
                raise ValueError('unsupported semantic source-claim')
            seen.add(idx);total_citations+=1
        result.append({'route_id':route['route_id'],'source_sessions':sorted(session_set),
          'citation_numbers':sorted(c['citation_index'] for c in citations),
          'teacher_instructor_conditions_verified':False,
          'mt5_shadow_status':'BLOCKED_TEACHER_SEMANTICS_NOT_INDEPENDENTLY_VERIFIED',
          'missing_reviews':list(REQUIRED_REVIEWS),
          'pending_entry_predicate_count':None,
          'orders_allowed':False})
    if seen!=set(range(1,25)) or total_citations!=24:raise ValueError('24 original citations not covered')
    if source.get('certified_routes')!=0 or source.get('orders_authorized')!=0:
        raise ValueError('source queue claims unsupported release')
    return {'schema':'artin_v13_13_route_to_mt5_demo_shadow_readiness_v1',
       'original_25_session_source_citations':24,
       'distinct_legacy_entry_routes':13,'teacher_certified_routes':0,
       'mt5_demo_order_authorizations':0,'orders_sent':0,
       'route_readiness':result,
       'next_evidence_needed':'Independent original teacher audio/visual and speaker, market-state rule, inter-session priority, matching classroom decisions.',
       'MT5_deployment_state':'SOURCE_ONLY_NOT_COMPILED_NOT_DEPLOYED'}

def main():
    p=argparse.ArgumentParser();p.add_argument('acceptance_queue',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.acceptance_queue.resolve()==a.output.resolve():raise ValueError('immutable source')
    original=a.acceptance_queue.read_bytes()
    report=compile_shadow_evidence(json.loads(original))
    report['source_acceptance_queue_sha256']=hashlib.sha256(original).hexdigest()
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'routes':13,'citations':24,'certified':0,'orders':0},ensure_ascii=False))
if __name__=='__main__':main()