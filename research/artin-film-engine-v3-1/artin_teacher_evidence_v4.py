#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-grounded Persian classroom Q&A candidates and FAIL-CLOSED rule evaluator.

Automated speech-to-text, vision captions, or adjacent segments NEVER verify
teacher identity or rule correctness. Only deliberately reviewed cases may
reach the paper-only execution gate; no broker or MT5 integration.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from collections.abc import Mapping

QUESTION_MARKERS=('آیا','چرا','چطور','چگونه','کدام','چه زمانی','میشه','می شه','میتونیم','می توانیم','کی ','آیا اگر','چیه','یعنی')
TRADING_MARKERS=('ورود','خروج','استاپ','حد ضرر','کندل','سیگنال','معامله','خرید','فروش','شرط','بازار','پوزیشن','چارت')


def _normalized(value):
    if not isinstance(value,str):return ''
    return re.sub(r'\s+',' ',value.replace('ي','ی').replace('ك','ک').replace('\u200c',' ')).strip()


def line_identity(source_sha256,part_global,segment):
    if not re.fullmatch(r'[a-f0-9]{64}',str(source_sha256)):
        raise ValueError('Expected source video hash')
    if type(part_global) is not int or part_global<1:raise ValueError('Expected global part number')
    for x in ('id','start','end','text'):
        if x not in segment:raise ValueError('Missing source segment field')
    if type(segment['start']) not in (float,int) or type(segment['end']) not in (float,int):
        raise ValueError('Missing source timestamps')
    if not 0 <= segment['start'] < segment['end']:
        raise ValueError('Invalid timing')
    sig=f"{source_sha256}:{part_global}:{segment['id']}:{segment['start']}:{segment['end']}:{_normalized(segment['text'])}"
    return 'u_'+hashlib.sha256(sig.encode('utf8')).hexdigest()[:24]


def linked_qa_candidates(source_hash,utterances,question_window_s=420):
    """Find QUESTIONS and nearby possible replies; never assert a teacher answer."""
    if not 30<=question_window_s<=900:raise ValueError('Question context range unsupported')
    ordered=sorted(utterances,key=lambda x:(x['start'],x['part_global'],x['id']))
    by_id=set();indexed=[]
    for u in ordered:
        key=line_identity(source_hash,u['part_global'],u)
        if key in by_id:continue
        by_id.add(key)
        indexed.append({**u,'line_id':key,'text':_normalized(u['text'])})
    links=[]
    for q in indexed:
        phrase=q['text']
        # A question WITHOUT an explicit marker can be missed; the result is not a full course audit.
        # Word boundaries prevent 'کی ' inside 'یکی' and 'میشه' inside
        # unrelated declarative words. Do not treat 'یعنی' alone as a question.
        question_words=re.search(
            r'(?<!\w)(?:آیا|چرا|چطور|چگونه|کدام|چه زمانی|کی|چیه)(?!\w)', phrase)
        modal_start=re.match(r'^(?:می شه|میشه|میتونیم|می توانیم)\s', phrase)
        is_q=('؟' in phrase or '?' in phrase or bool(question_words) or bool(modal_start))
        if not is_q:continue
        candidates=[]
        for a in indexed:
            if a['start']<=q['end']:continue
            if a['start']-q['end']>question_window_s:break
            if a['line_id']==q['line_id']:continue
            # Candidate list does not treat proximity as teacher or correctness.
            candidates.append({'line_id':a['line_id'],'time':a['start'],
                               'text':a['text'][:200],'role':'UNKNOWN','response_verified':False})
            if len(candidates)>=8:break
        links.append({'question_line_id':q['line_id'],
                      'question_time_seconds':q['start'],'question_text':phrase[:600],
                      'question_has_trading_terms':any(w in phrase for w in TRADING_MARKERS),
                      'possible_following_utterances':candidates,
                      'question_speaker':'UNKNOWN','answer_speaker':'UNKNOWN',
                      'teacher_answer_verified':False,
                      'status':'REVIEW_AUDIO_VISUAL_AND_TEACHER_RESPONSE',
                      'can_change_artin_engine':False})
    return {'schema':'artin_qa_candidates_v4','source_video_sha256':source_hash,
            'total_utterances':len(indexed),'question_candidates':links,
            'teacher_answers_verified':0,'rules_approved':0,
            'no_teacher_identity_inference':True}


ALLOWED_FEATURES=frozenset({'open','high','low','close','volume','ma21','ma100','ma200',
                             'rsi','atr','adx','spread','body','upper_wick','lower_wick'})
OPERATORS=frozenset({'eq','ne','gt','gte','lt','lte'})


def validate_condition_tree(node):
    if not isinstance(node,dict):raise ValueError('Condition must be a JSON object')
    if 'all' in node or 'any' in node:
        if len(node)!=1:raise ValueError('Logical group has extra fields')
        label='all' if 'all' in node else 'any'
        nodes=node[label]
        if not isinstance(nodes,list) or not 1<=len(nodes)<=20:raise ValueError('Invalid logical group')
        for n in nodes:validate_condition_tree(n)
        return
    if set(node)!={'field','op','value'}:raise ValueError('Condition must have field/op/value')
    if node['field'] not in ALLOWED_FEATURES or node['op'] not in OPERATORS:
        raise ValueError('Feature or operator is not on the approved evaluation list')
    if type(node['value']) not in (int,float) or not math.isfinite(node['value']):
        raise ValueError('Only finite numeric values are allowed')


def review_rule_eligibility(rule,known_evidence):
    """Return REJECT/REVIEW/PAPER_ONLY. Caller cannot infer permission from ASR output."""
    issues=[]
    if not isinstance(rule,dict):return {'status':'REJECT','issues':['INVALID_RULE_OBJECT']}
    if not isinstance(known_evidence,Mapping):return {'status':'REJECT','issues':['INVALID_SOURCE_LEDGER']}
    if rule.get('decision') not in ('BUY','SELL','NO_TRADE'):
        issues.append('UNKNOWN_DECISION')
    try:validate_condition_tree(rule.get('conditions'))
    except (ValueError,TypeError):issues.append('CONDITIONS_NOT_EXECUTABLE')
    refs=rule.get('source_line_ids')
    if not isinstance(refs,list) or not refs or any(not isinstance(r,str) for r in refs):
        issues.append('MISSING_SOURCE_LINES');refs=[]
    if len(refs)!=len(set(refs)):issues.append('DUPLICATE_SOURCE_LINES')
    source=[known_evidence.get(i) for i in refs]
    if any(s is None for s in source):issues.append('SOURCE_LINE_NOT_FOUND')
    else:
        if not any(s.get('confirmed_role')=='TEACHER' and s.get('speaker_human_verified') is True for s in source):
            issues.append('TEACHER_IDENTITY_UNVERIFIED')
        if any(s.get('audio_reviewed_against_original') is not True for s in source):
            issues.append('ORIGINAL_AUDIO_UNREVIEWED')
        if any(s.get('text_human_corrected_or_verified') is not True for s in source):
            issues.append('QUOTE_UNVERIFIED')
    if rule.get('requires_visual_example'):
        if not rule.get('reference_frames') or rule.get('visual_reference_human_verified') is not True:
            issues.append('CHART_VISUAL_UNVERIFIED')
    for qa in rule.get('question_answer_references',[]):
        if not (isinstance(qa,dict) and qa.get('question_line') in known_evidence
                and qa.get('teacher_answer_line') in known_evidence
                and known_evidence[qa['question_line']].get('audio_reviewed_against_original') is True
                and known_evidence[qa['teacher_answer_line']].get('confirmed_role')=='TEACHER'
                and known_evidence[qa['teacher_answer_line']].get('audio_reviewed_against_original') is True):
            issues.append('UNVERIFIED_QUESTION_ANSWER')
    if rule.get('later_correction_unresolved') is not False:
        issues.append('LATER_CORRECTION_NOT_RECONCILED')
    if rule.get('reviewed_by_user') is not True:
        issues.append('USER_SIGNOFF_NOT_PRESENT')
    # Every example must be grounded and considered by the reviewer. This is a
    # checklist, not proof that historical profit or accuracy is good.
    if not rule.get('positive_example_reviewed') or not rule.get('negative_example_reviewed'):
        issues.append('POSITIVE_OR_NEGATIVE_EXAMPLE_MISSING')
    return {'status':'PAPER_ONLY' if not issues else 'REVIEW','issues':sorted(set(issues)),
            'can_place_real_order':False,'source_line_ids':refs}


def evaluate_paper_rule(rule,known_evidence,features):
    result=review_rule_eligibility(rule,known_evidence)
    if result['status']!='PAPER_ONLY':return {**result,'paper_decision':'BLOCKED'}
    if not isinstance(features,Mapping):return {**result,'paper_decision':'BLOCKED_FEATURES'}
    def check(node):
        if 'all' in node:return all(check(x) for x in node['all'])
        if 'any' in node:return any(check(x) for x in node['any'])
        v=features.get(node['field'])
        if type(v) not in (float,int) or not math.isfinite(v):return False
        t=node['value'];op=node['op']
        return {'eq':lambda:v==t,'ne':lambda:v!=t,'gt':lambda:v>t,
                'gte':lambda:v>=t,'lt':lambda:v<t,'lte':lambda:v<=t}[op]()
    return {**result,'paper_decision':rule['decision'] if check(rule['conditions']) else 'NO_TRADE',
            'paper_only':True,'broker_action':None}