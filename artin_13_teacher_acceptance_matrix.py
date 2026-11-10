"""Artin 13-route evidence acceptance preflight.

Evidence-only, without semantic inference or trading actions. Never upgrades
machine ASR, nearby photos, or manual flags into certified teacher decisions.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

EXPECTED_ROUTES = frozenset('''BREAK_STRONG BREAK_VERY_STRONG_RETEST BREAK_WEAK_FULLBODY_EXCEPTION BREAK_WEAK_PIVOT PULLBACK_STANDARD REVERSAL_CLASSIC REVERSAL_STAR REVERSAL_THREE STOPPUNCH_DOJI_AHEAD STOPPUNCH_DOJI_TIED STOPPUNCH_OPPOSITE_CONFIRMATION STOPPUNCH_S22_SELL_CONFIRMED_PAUSE STOPPUNCH_SAME_COLOUR'''.split())
REQUIRED_REVIEWS = ('original_audio_independent_listening', 'teacher_student_speaker_review', 'original_chart_referent_review', 'entry_exit_exception_decision_order_review', 'cross_session_revisions_review', 'teacher_example_vs_engine_replay')

def evaluate(dossiers:dict,citations:dict,crossmodal:dict)->dict:
    if any(not isinstance(x,dict) for x in (dossiers,citations,crossmodal)):
        raise ValueError('source docs must be objects')
    routes=dossiers.get('routes')
    cit=citations.get('citations')
    cm=crossmodal.get('citations')
    if not all(isinstance(x,list) for x in (routes,cit,cm)):
        raise ValueError('missing route/citation evidence')
    routeids=[r['route_id'] for r in routes]
    if len(routes)!=13 or set(routeids)!=EXPECTED_ROUTES or len(routeids)!=len(set(routeids)):
        raise ValueError('missing, duplicate or forged route')
    if len(cit)!=24 or len(cm)!=24:
        raise ValueError('source citations must be exactly 24')
    numbers=[c['citation_index'] for c in cit]
    if sorted(numbers)!=list(range(1,25)):
        raise ValueError('citation indexes invalid')
    cmap={c['citation_index']:c for c in cit}
    vmap={c['citation_index']:c for c in cm}
    if set(vmap)!=set(cmap):raise ValueError('visual scope index mismatch')
    output=[]
    for row in routes:
        route=row['route_id']
        own=sorted((c for c in cit if c['route_id']==route),key=lambda x:x['citation_index'])
        dossier_idx=[int(i['index']) for i in row.get('citation_intervals',[])]
        if not own or sorted(dossier_idx)!=[c['citation_index'] for c in own]:
            raise ValueError('dossier citation membership mismatch: '+route)
        source_sessions=set(row['source_sessions'])
        if source_sessions!={c['session'] for c in own}:
            raise ValueError('session mismatch: '+route)
        linked=[]; visual_inwindow=0; samples=0
        for c in own:
            v=vmap[c['citation_index']]
            if (v['route_id'],v['session'],v['source_start_seconds'],v['source_end_seconds']) != (route,c['session'],c['start_seconds'],c['end_seconds']):
                raise ValueError('cross-modal source identity/timing discrepancy')
            original_rows=c['excerpts']
            if not original_rows or len(original_rows)!=c['overlap_asr_rows']:
                raise ValueError('ASR excerpt membership mismatch')
            for e in original_rows:
                if not e.get('asr_segment_id') or not e.get('original_audio_sha256'):
                    raise ValueError('missing source linkage')
            n=len(v.get('reviewed_66_images_in_window',[]))
            visual_inwindow+=int(n>0);samples+=n
            linked.append({'citation_index':c['citation_index'],'session':c['session'],
              'interval_seconds':[c['start_seconds'],c['end_seconds']],
              'machine_asr_occurrences':len(original_rows),'sampled_images_in_window':n,
              'audio_words_independently_verified':False,'chart_visual_meaning_verified':False})
        # No fully reviewed teacher case is supported by these private source collections.
        blockers=list(REQUIRED_REVIEWS)
        output.append({'route_id':route,'source_sessions':sorted(source_sessions),
            'citations':linked,'citation_count':len(own),
            'sampled_in_window_image_citations':visual_inwindow,
            'sampled_in_window_image_occurrences':samples,
            'missing_required_reviews':blockers,
            'missing_pinned_exact_original_frame_in_citations':len(own)-visual_inwindow,
            'teacher_case_certified':False,'engine_decision_replay_certified':False,
            'release_status':'BLOCKED_ORIGINAL_AV_SEMANTICS_UNVERIFIED',
            'orders_authorized':0})
    if sum(x['citation_count'] for x in output)!=24:raise ValueError('citation coverage duplicate/missing')
    return {'schema':'artin_13_teacher_acceptance_queue_v1','source_routes':13,'source_citations':24,
      'routes':output,'certified_routes':0,'orders_authorized':0,
      'warning':'A manually selected positive review value is not independent proof. Original teacher AV and decision replay are not certified.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('dossiers');p.add_argument('citations');p.add_argument('crossmodal');p.add_argument('output')
    a=p.parse_args()
    data=[json.loads(Path(x).read_text(encoding='utf-8')) for x in (a.dossiers,a.citations,a.crossmodal)]
    result=evaluate(*data)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'routes':result['source_routes'],'citations':result['source_citations'],'certified':0,'orders':0}))
if __name__=='__main__': main()