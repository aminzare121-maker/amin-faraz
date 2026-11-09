#!/usr/bin/env python3
"""Stage all 25 Artin lessons for evidence-grounded replay without trading.

This reads PRIVATE Behrooz archives locally and exports an index of candidate
teaching scenarios, not a certificate of teacher fidelity or real orders.
"""
import argparse
import json
import zipfile
from pathlib import Path

SIX='Artin_Six_Source_Semantic_Cases_20261109.zip'
FOUR='Artin_Four_Additional_Semantic_Cases_20261109.zip'
SPEECH='Artin_22_Sessions_Speech_OCR_Review_20261109.zip'


def decision_comparison(case, engine_decision=None):
    """Never mark a replay PASS unless both teacher and motor are proven."""
    expected=case.get('teacher_expected_decision_verified')
    if (not case.get('speaker_verified') or not case.get('audio_visual_meaning_verified')
            or not case.get('decision_conditions_complete') or not case.get('exceptions_complete')
            or not case.get('cross_session_precedence_resolved')
            or expected not in {'ENTER','EXIT','HOLD','NO_TRADE'}):
        return 'BLOCKED_UNVERIFIED_TEACHER_DECISION'
    if engine_decision not in {'ENTER','EXIT','HOLD','NO_TRADE'}:
        return 'BLOCKED_NO_ENGINE_DECISION'
    return 'PASS' if expected == engine_decision else 'FAIL_MOTOR_DISAGREES_WITH_TEACHER'


def build(root):
    root=Path(root)
    with zipfile.ZipFile(root/SIX) as s,zipfile.ZipFile(root/FOUR) as f,zipfile.ZipFile(root/SPEECH) as z:
        six=json.loads(s.read('six_semantic_source_cases.json'))
        four=json.loads(f.read('cases.json'))
        links=json.loads(s.read('cross_session_conflict_review.json'))
        links += json.loads(f.read('cross_session_links.json'))
        sessions={n:{'session':n,'scenario_ids':[],'candidate_replays':0,
                     'independently_verified_teacher_rules':0} for n in range(1,26)}
        evidence={}
        for n in range(4,26):
            path=f'session_{n:02d}_speech_visual_UNVERIFIED.jsonl'
            if path not in z.namelist():raise ValueError('missing transcript '+path)
            evidence[n]=[json.loads(row) for row in z.read(path).splitlines() if row.strip()]
        normalized=[]
        for group,entries in [('six',six),('four',four)]:
            for x in entries:
                n=x['seq'] if group=='six' else x['sequence']
                tid=x['id'];t=x['speech_time'] if group=='six' else x['time']
                proof=x['proof'] if group=='six' else x['source_proof']
                speech=proof['speech_literal_exact'] if group=='six' else proof['original_ASR']
                sha=proof['visual_SHA256'] if group=='six' else proof['original_image_sha256']
                matching=[r for r in evidence[n] if r.get('speech_exact')==speech
                          and abs(r.get('time_start',-100000)-t)<0.065]
                if not matching:raise ValueError('missing original timed ASR case '+tid)
                if not sha or len(sha)!=64:raise ValueError('invalid SHA in '+tid)
                missing=x['missing'] if group=='six' else x['needed']
                case={
                    'case_id':tid,'session':n,'speech_start_seconds':t,
                    'source_anchor_sha256':sha, 'machine_speech_time_match':True,
                    'market_state_candidate':x.get('meaning_assessment_fa',x.get('meaning_fa')),
                    'scenario_class':'TEACHING_MARKET_SCENARIO_NOT_HISTORICAL_EXECUTION_PROOF',
                    'hypothetical_examples_allowed':True,
                    'missing_teacher_method_evidence':missing,
                    'speaker_verified':False,'audio_visual_meaning_verified':False,
                    'decision_conditions_complete':False,'exceptions_complete':False,
                    'cross_session_precedence_resolved':False,
                    'teacher_expected_decision_verified':None,'engine_observed_decision':None,
                    'trading_allowed':False,
                }
                case['replay_status']=decision_comparison(case)
                normalized.append(case)
                sessions[n]['scenario_ids'].append(tid)
                sessions[n]['candidate_replays']+=1
        normalized.sort(key=lambda x:(x['session'],x['speech_start_seconds']))
        case_n={c['case_id']:c['session'] for c in normalized}
        links_checked=[]
        for x in links:
            a=x.get('from',x.get('earlier'));b=x.get('to',x.get('later'))
            if a not in case_n or b not in case_n:raise ValueError('unlinked case ID')
            good=case_n[a]<case_n[b]
            links_checked.append({'earlier_claim':a,'later_claim':b,'chronological_order_valid':good,
                                  'may_override_prior_instruction':False,
                                  'needs_original_teacher_cross_lesson_review':True})
        return {'schema':'artin_25_lessons_replay_staging_v1',
                'source':'private archive candidate ASR and linked image references',
                'sessions':list(sessions.values()),'session_count':25,
                'candidate_cases':normalized,'candidate_cases_count':len(normalized),
                'cross_session_candidate_links':links_checked,
                'chronology_errors':[x for x in links_checked if not x['chronological_order_valid']],
                'example_policy':'Hypothetical market scenarios are valid teaching cases; historical execution is a distinct claim',
                'teacher_rules_certified':0,'motor_decisions_compared_with_verified_teacher':0,
                'semantic_certificate':False,'allow_mt5_trading':False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    report=build(args.root)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'sessions':report['session_count'],'cases':report['candidate_cases_count'],
                      'reverse_links':len(report['chronology_errors']),
                      'certified':report['teacher_rules_certified'],
                      'allow_mt5_trading':report['allow_mt5_trading']},ensure_ascii=False))
if __name__=='__main__':main()
