"""Combine multiple Artin classroom films into a source-linked, NON-EXECUTABLE syllabus.

Each lesson must have been processed by artin_film_pipeline.merge. This is a
research handoff, not teacher-certified trading logic, not a model that "learns"
from a course and not a broker connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from artin_film_pipeline import atomic_json, load_manifest, normalize_text
from artin_semantic_context import noise_risk

RELEVANT_KINDS = frozenset({'RULE','CORRECTION','EXCEPTION','EXAMPLE'})
QA_KINDS = frozenset({'QUESTION','ANSWER'})


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _assert_path_under(path, root):
    result=(root/path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Path escapes selected course root')
    return result


def compile_course(course_config, expected_sessions=26):
    """Accept a config of {lessons:[{session:1, folder:'/path/to/local-output'}]}.

    Absolute local lesson paths are allowed; no uploads or external API calls.
    """
    if not isinstance(course_config,dict) or not isinstance(course_config.get('lessons'),list):
        raise ValueError('Course configuration must have lessons list')
    if type(expected_sessions) is not int or not 1 <= expected_sessions <= 1000:
        raise ValueError('Invalid number of expected sessions')
    # Reject duplicate lesson IDs BEFORE opening any potentially missing files.
    raw_ids=[x.get('session') for x in course_config['lessons'] if isinstance(x,dict)]
    if len(raw_ids)!=len(set(raw_ids)):
        raise ValueError('Duplicate session number in course input')
    parsed=[];seen_sessions=set();seen_video_hashes=set();all_events=[];all_segments=[];all_noise=[]
    for item in course_config['lessons']:
        if not isinstance(item,dict) or type(item.get('session')) is not int:
            raise ValueError('Session must be an integer')
        session=item['session']
        if not 1<=session<=expected_sessions or session in seen_sessions:
            raise ValueError('Duplicate or out-of-range session')
        seen_sessions.add(session)
        folder=Path(item['folder']).resolve()
        required=['manifest.json','unified_timeline.json','audit_report.json',
                  'rule_candidate_graph.json','artin_engine_handoff.json','noise_quarantine.json']
        if any(not (folder/f).is_file() for f in required):
            raise ValueError(f'Session {session}: required local outputs missing')
        manifest=load_manifest(folder)
        audit=_read(folder/'audit_report.json')
        timeline=_read(folder/'unified_timeline.json')
        handoff=_read(folder/'artin_engine_handoff.json')
        noise=_read(folder/'noise_quarantine.json')
        graph=_read(folder/'rule_candidate_graph.json')
        digest=manifest['video_sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Source video SHA256 invalid')
        if digest in seen_video_hashes:
            raise ValueError('Same source video cannot represent two different sessions')
        seen_video_hashes.add(digest)
        if any([audit.get('video_sha256')!=digest,
                timeline.get('source_video_sha256')!=digest,
                handoff.get('source_video_sha256')!=digest,
                timeline.get('schema')!='artin_linked_timeline_v1',
                audit.get('schema')!='artin_full_lesson_diagnostic_v1',
                graph.get('schema')!='artin_rule_candidate_graph_v1',
                noise.get('schema')!='artin_classroom_noise_review_v1',
                handoff.get('trade_permissions')!=0,
                handoff.get('approved_rules')!=0,
                graph.get('may_modify_engine') is not False,
                audit.get('teacher_rules_approved')!=0,
                audit.get('artin_rule_ready') is not False,
                audit.get('transcript_and_semantic_outputs_present') is not True]):
            raise ValueError(f'Session {session}: incomplete, untrusted or executable input')
        if audit.get('chunk_count')!=len(manifest['chunks']):
            raise ValueError(f'Session {session}: chunk count does not match original')
        seg_by_id={s['id']:s for s in timeline['segments']}
        lesson_events=[]
        for event in timeline.get('semantic_candidates',[]):
            if event.get('status')!='UNVERIFIED_MODEL_INTERPRETATION_REQUIRES_AUDIO_VIDEO_REVIEW' or event.get('can_trade') is not False:
                raise ValueError('Input includes unsafely promoted semantic event')
            ids=event.get('source_ids',[])
            if not isinstance(ids,list) or not ids or any(i not in seg_by_id for i in ids):
                raise ValueError('Semantic event has missing source segment')
            txt=normalize_text(event.get('quote',''))
            if not txt or not any(txt in normalize_text(seg_by_id[i]['text']) for i in ids):
                raise ValueError('Candidate rule quote is not present in exact source transcript')
            start=event['start']
            if type(start) not in (int,float) or not 0<=start<manifest['source_duration']+1:
                raise ValueError('Event timestamp outside original video')
            exact=dict(event)
            exact['course_event_id']=f's{session:02d}:{event["id"]}'
            exact['session']=session
            exact['source_video_sha256']=digest
            exact['source_ids']=[f's{session:02d}:{x}' for x in ids]
            exact['speaker_verified']=False
            exact['teacher_rule_verified']=False
            exact['artin_engine_change_allowed']=False
            lesson_events.append(exact)
        for s in timeline['segments']:
            all_segments.append({'session':session,'id':f's{session:02d}:{s["id"]}',
                                 'start':s['start'],'end':s['end'],'text':s['text'],
                                 'source_video_sha256':digest,'speaker_verified':False})
        all_events.extend(lesson_events)
        for x in noise.get('quarantined_events',[]):
            all_noise.append({'session':session,'event_id':x.get('id'),
                              'reason':x.get('noise_review_status'),
                              'may_modify_engine':False})
        parsed.append({'session':session,'video_sha256':digest,
                       'duration_s':manifest['source_duration'],
                       'chunks':len(manifest['chunks']),
                       'transcript_segments':len(timeline['segments']),
                       'events':len(lesson_events),
                       'candidate_rules':len(graph.get('candidate_rules',[])),
                       'lesson_verified':False})
    parsed.sort(key=lambda s:s['session'])
    # Deliberately do not merge by an unreviewed rule_label if it has a noise cue.
    topics=defaultdict(list);qa=[];unmapped=[]
    for e in all_events:
        if e.get('kind')=='CLASSROOM_NOISE' or noise_risk(e.get('quote',''))!='NOT_IDENTIFIED':
            all_noise.append({'session':e['session'],'event_id':e['id'],
                              'reason':'UNRELATED_OR_MIXED_CONTEXT_REVIEW',
                              'may_modify_engine':False})
            continue
        kind=e.get('kind')
        if kind in QA_KINDS:
            qa.append({'course_event_id':e['course_event_id'],
                       'session':e['session'],'kind':kind,'start':e['start'],
                       'text':e['quote'],'related_rule_candidate':e.get('rule_label_candidate'),
                       'speaker_and_answer_not_verified':True})
        if kind not in RELEVANT_KINDS:
            continue
        key=normalize_text(e.get('rule_label_candidate',''))
        if not key:
            unmapped.append(e['course_event_id']);continue
        topics[key].append(e)
    bundles=[];revision_hints=[];conflicts=[]
    for key,rows in sorted(topics.items()):
        rows.sort(key=lambda e:(e['session'],e['start'],e['course_event_id']))
        decisions=sorted(set(e.get('decision_candidate','UNKNOWN') for e in rows if e.get('decision_candidate')!='UNKNOWN'))
        corrections=[e for e in rows if e.get('kind')=='CORRECTION']
        hints=[]
        for correction in corrections:
            prior=[e for e in rows if (e['session'],e['start']) <
                   (correction['session'],correction['start'])]
            if prior:
                hint={'type':'POSSIBLE_LATER_CORRECTION_NOT_PROVEN',
                      'from_event':correction['course_event_id'],
                      'to_event':prior[-1]['course_event_id'],
                      'source_sessions':[prior[-1]['session'],correction['session']],
                      'requires_direct_teacher_media_review':True}
                hints.append(hint);revision_hints.append(hint)
        if ('BUY' in decisions and 'SELL' in decisions) or ('NO_TRADE' in decisions and len(decisions)>1):
            conflicts.append({'topic':key,'decisions':decisions,
                              'reason':'POTENTIAL_DISAGREEMENT_CHECK_TEACHER_CONTEXT'})
        bundles.append({
            'topic_key':key, 'candidate_display_name':rows[-1]['rule_label_candidate'],
            'appears_in_sessions':sorted({e['session'] for e in rows}),
            'chronological_sources':[{'course_event_id':e['course_event_id'],
                'session':e['session'],'second':e['start'],
                'source_video_sha256':e['source_video_sha256'],
                'transcript_segment_ids':e['source_ids'],'original_quote':e['quote'],
                'type_candidate':e['kind'],'decision_candidate':e.get('decision_candidate'),
                'condition_text_candidates':e.get('condition_candidates',[]),
                'sampled_visual_evidence':e.get('related_visual_frame_evidence',[]),
                'teacher_identity_verified':False} for e in rows],
            'possible_later_corrections':hints,
            'teacher_positive_example_verified':False,
            'teacher_negative_example_verified':False,
            'all_student_questions_resolved':False,
            'teacher_final_rule_verified':False,
            'can_compile_to_executable_artin_rule':False,
            'blocking_reason':'REQUIRES_DIRECT_MEDIA_QA_AND_POSITIVE_NEGATIVE_CASE_VALIDATION',
        })
    missing=sorted(set(range(1,expected_sessions+1))-seen_sessions)
    return {
        'schema':'artin_multi_lesson_candidate_syllabus_v1',
        'purpose':'CONTEXTUAL_SYLLABUS_FOR_MANUAL_OR_RULE_SPEC_REVIEW_ONLY',
        'declared_session_count':expected_sessions,'supplied_lessons':len(parsed),
        'missing_sessions':missing,'sessions':parsed,
        'source_utterances':len(all_segments), 'candidate_events':len(all_events),
        'candidate_topics':len(bundles),'topics':bundles,
        'student_question_answer_review_queue':qa,
        'cross_session_revision_review_edges':revision_hints,
        'candidate_decision_conflicts':conflicts,
        'events_without_rule_label':unmapped,
        'quarantined_noninstructional_or_mixed_events':all_noise,
        'complete_original_video_course_reviewed':False,
        'all_teacher_answers_and_corrections_verified':False,
        'artin_engine_auto_patch_generated':False,
        'rules_approved':0,'live_or_demo_orders_sent':0,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--course-config',type=Path)
    group.add_argument('--course-root',type=Path,
                       help='Folder containing local session_01 ... session_26 result folders')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--expected-sessions',type=int,default=26)
    a=p.parse_args()
    if a.course_config is not None:
        if a.course_config.resolve()==a.out.resolve():
            p.error('Do not overwrite input configuration')
        config=_read(a.course_config)
    else:
        import re
        root=a.course_root.resolve()
        if not root.is_dir():
            p.error('Course root not found')
        lessons=[]
        for folder in root.iterdir():
            if not folder.is_dir():continue
            m=re.fullmatch(r'(?:session|lesson)[_-]?(\d{1,3})',folder.name,re.I)
            if m:
                lessons.append({'session':int(m.group(1)),'folder':str(folder)})
        config={'lessons':lessons}
    result=compile_course(config,a.expected_sessions)
    atomic_json(a.out,result)
    print(json.dumps({'supplied_lessons':result['supplied_lessons'],
                      'candidate_topics':result['candidate_topics'],
                      'missing_sessions':result['missing_sessions'],
                      'teacher_verified_rules':0},ensure_ascii=False))


if __name__=='__main__':main()
