"""Execute source-anchored Artin *classroom cases* through the existing 13-route
entry and paper-trade state machine. Nothing here sends broker orders.

Unlike bare raw-OHLC replay, this path accepts explicit classroom predicates,
source-verified at a given decision time; it NEVER guesses missing teacher facts.
Original video source windows (25-session numbering) are validated against the
existing private Behr(o)uz 24-citation document; that document stays private.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
import re
from pathlib import Path

PINNED_COMMIT = 'b48fb06f8b2b0d134292025f5b27fc670ad2a293'
ALLOWED_CHOICES = {'ENTER', 'NO_TRADE', 'WAIT', 'EXIT', 'HOLD'}

class ClassroomMotorError(ValueError):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_pinned(core):
    """No unreviewed modifications to the existing, tested motor permitted."""
    core = Path(core).resolve()
    manifest_path = core/'LEGACY_SHA_MANIFEST.json'
    if not manifest_path.is_file():
        raise ClassroomMotorError('PINNED_ENGINE_MANIFEST_MISSING')
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    if m.get('source_commit') != PINNED_COMMIT:
        raise ClassroomMotorError('PINNED_ENGINE_REVISION_CHANGED')
    for name, digest in m.get('files_sha256', {}).items():
        if sha256(core/name) != digest:
            raise ClassroomMotorError('PINNED_ENGINE_SOURCE_CHANGED:'+name)
    if not (core/'entry_engine.py').is_file() or not (core/'run_engine.py').is_file():
        raise ClassroomMotorError('PINNED_ENTRY_OR_TRADE_ENGINE_MISSING')
    sys.path.insert(0, str(core))
    try:
        eng = importlib.import_module('entry_engine')
        paper = importlib.import_module('run_engine')
        if Path(eng.__file__).resolve() != core/'entry_engine.py' or Path(paper.__file__).resolve() != core/'run_engine.py':
            raise ClassroomMotorError('WRONG_IMPORTED_MOTOR')
        return eng, paper
    finally:
        sys.path.remove(str(core))


def index_original_citations(document, routes):
    """Use corrected source IDs from the 25-session private dossier, not old 26-slot labels."""
    if document.get('summary', {}).get('sessions') != 25:
        raise ClassroomMotorError('REQUIRE_ORIGINAL_25_CLASS_SESSIONS')
    citations = document.get('citations', [])
    if len(citations) != 24 or len(set(c['citation_index'] for c in citations)) != 24:
        raise ClassroomMotorError('REQUIRE_24_DISTINCT_CLASS_CITATIONS')
    indexed = {}
    for c in citations:
        route = c['route_id']; session = c['session']; start = c['start_seconds']; stop = c['end_seconds']
        if route not in routes or type(session) is not int or not 1 <= session <= 25 or not 0 <= start < stop:
            raise ClassroomMotorError('INVALID_CLASS_CITATION')
        intervals = tuple((x['start'],x['end'],x['asr_segment_id']) for x in c['excerpts'])
        if any(not (a < b and max(start,a) < min(stop,b)) for a,b,_ in intervals):
            raise ClassroomMotorError('SEGMENT_OUTSIDE_CLASS_CITATION')
        indexed[c['citation_index']] = c
    if {c['route_id'] for c in indexed.values()} != set(routes):
        raise ClassroomMotorError('MISSING_CLASS_ROUTE')
    return indexed


def source_speech_polarity(cited, ids):
    """Only literal source text polarity for *this exact classroom scene*.

    A negated sentence is never interpreted as a global strategy veto, and an
    affirmative sentence never becomes an order. Original audio may override
    ASR; all this outputs is a provisional classroom instruction.
    """
    snippets=[x.get('text_unverified','') for x in cited['excerpts'] if x['asr_segment_id'] in ids]
    if not snippets:
        return 'UNKNOWN_UNANCHORED_MEANING'
    string=' '.join(snippets).replace('\u200c',' ').replace('ي','ی').replace('ك','ک')
    negative=bool(re.search(r'ورود\s+نمی\s*کن(?:یم|ید|م)|وارد\s+نمی\s*ش',string))
    positive=bool(re.search(r'ورود\s+می\s*کن(?:یم|ید|م)|ورود\s+کن(?:یم|ید|م)',string))
    return ('POSSIBLE_NO_TRADE_IN_THIS_SCENE' if negative and not positive
            else 'POSSIBLE_CONDITIONAL_ENTER_IN_THIS_SCENE' if positive and not negative
            else 'CONFLICTING_OR_UNCLEAR_TEACHER_WORDS')


def compile_case(row, index, route_ids):
    if not isinstance(row, dict):
        raise ClassroomMotorError('CLASS_CASE_OBJECT_REQUIRED')
    cid = row.get('case_id'); route = row.get('rule_id'); citation_id=row.get('citation_index')
    if not isinstance(cid, str) or not cid.strip() or route not in route_ids or type(citation_id) is not int:
        raise ClassroomMotorError('INVALID_CLASS_CASE_IDENTITY')
    cited = index.get(citation_id)
    if cited is None or cited['route_id'] != route:
        raise ClassroomMotorError('CLASS_CITATION_ROUTE_MISMATCH')
    if row.get('session') != cited['session']:
        raise ClassroomMotorError('CLASS_SESSION_MISMATCH')
    start,end = row.get('class_seconds', [None,None])
    if type(start) not in (int,float) or type(end) not in (int,float) or not cited['start_seconds'] <= start <= end <= cited['end_seconds']:
        raise ClassroomMotorError('CLASS_INTERVAL_MISMATCH')
    # A classroom event can be analyzed while missing objective chart facts;
    # MISSING stays REVIEW, never inferred from a word or image filename.
    facts = row.get('facts')
    if not isinstance(facts, dict):
        raise ClassroomMotorError('FACTS_OBJECT_REQUIRED')
    for name,f in facts.items():
        if not isinstance(name,str) or not isinstance(f,dict) or not f.get('source') or 'known_at' not in f:
            raise ClassroomMotorError('UNSOURCED_MARKET_FACT')
        if not isinstance(f['source'],str):
            raise ClassroomMotorError('INVALID_MARKET_FACT_SOURCE')
        if f['source'].startswith('SYNTHETIC_') and row.get('source_class') != 'SYNTHETIC_TEST':
            raise ClassroomMotorError('UNDECLARED_SYNTHETIC_SOURCE')
        # Source-backed predicates cannot be available after the decision
        # clock, even if the pinned evaluator later decides to WAIT.
        if type(f['known_at']) is not int or f['known_at'] < 0:
            raise ClassroomMotorError('INVALID_MARKET_FACT_CLOCK')
    teacher_choice = row.get('teacher_choice')
    if teacher_choice is not None and teacher_choice not in ALLOWED_CHOICES:
        raise ClassroomMotorError('INVALID_CLASSROOM_DECISION_LABEL')
    ids = row.get('source_asr_segment_ids', [])
    if not isinstance(ids,list) or len(ids) != len(set(ids)):
        raise ClassroomMotorError('INVALID_SOURCE_SEGMENT_IDS')
    verified_source_ids = {x['asr_segment_id'] for x in cited['excerpts']}
    if not set(ids).issubset(verified_source_ids):
        raise ClassroomMotorError('CLASS_SOURCE_SEGMENT_NOT_IN_CITATION')
    at = row.get('market_decision_at')
    if type(at) is not int or at < 0:
        raise ClassroomMotorError('INVALID_MARKET_DECISION_TIME')
    if row.get('side') not in ('BUY','SELL'):
        raise ClassroomMotorError('CLASS_CASE_SIDE_REQUIRED')
    for fact_name,fact in facts.items():
        if fact['known_at'] > at:
            raise ClassroomMotorError('FUTURE_MARKET_FACT_IN_CLASS_CASE')
    data = {'rule_id':route,'side':row['side'],'at':at,'facts':facts}
    if 'paper_trade' in row:
        if row.get('source_class') != 'SYNTHETIC_TEST':
            if not isinstance(row['paper_trade'],dict):
                raise ClassroomMotorError('PAPER_LIFECYCLE_OBJECT_REQUIRED')
            if not row.get('paper_trade_teacher_source'):
                raise ClassroomMotorError('TEACHER_SOURCED_EXIT_RISK_REQUIRED')
            # Machine ASR or a proposed teacher label is insufficient to
            # simulate a purportedly teacher-approved entry lifecycle.
            if (row.get('teacher_choice') != 'ENTER'
                    or row.get('teacher_choice_verified') is not True
                    or row.get('teacher_visual_verified') is not True
                    or not ids):
                raise ClassroomMotorError('TEACHER_PAPER_LIFECYCLE_NOT_VERIFIED')
        data['paper_trade'] = row['paper_trade']
    proof = {'case_id':cid,'route_id':route,'citation_index':citation_id,
             'video_session':cited['session'],'class_interval_seconds':[start,end],
             'source_asr_segment_ids':ids,'teacher_choice_in_record':teacher_choice,
             'teacher_choice_independently_verified':row.get('teacher_choice_verified') is True,
             'source_class':row.get('source_class','CLASSROOM_ASR_CANDIDATE'),
             'teacher_visual_verified':row.get('teacher_visual_verified') is True,
             'exact_scene_speech_polarity_unverified':source_speech_polarity(cited,ids)}
    return data,proof


def run(citation_path, cases_path, core, out, private_acceptance_sources=None):
    # Optional private-source acceptance is deliberately fail-closed.
    # The private dossiers currently certify zero routes. A self-declared
    # teacher_verified flag in a case must not bypass that assessment.
    if private_acceptance_sources is not None:
        from artin_13_teacher_acceptance_matrix import evaluate
        if len(private_acceptance_sources) != 3:
            raise ClassroomMotorError('THREE_PRIVATE_ACCEPTANCE_SOURCES_REQUIRED')
        private_docs = [json.loads(Path(p).read_text(encoding='utf8'))
                        for p in private_acceptance_sources]
        acceptance = evaluate(*private_docs)
        accepted_routes = {r['route_id'] for r in acceptance['routes']
                           if r['teacher_case_certified'] and
                           r['engine_decision_replay_certified']}
    else:
        accepted_routes = None
    eng, paper = load_pinned(core)
    raw_citations = json.loads(Path(citation_path).read_text(encoding='utf8'))
    index = index_original_citations(raw_citations, eng.RULE_IDS)
    cases_doc = json.loads(Path(cases_path).read_text(encoding='utf8'))
    if cases_doc.get('schema') != 'artin_teacher_class_cases_v1':
        raise ClassroomMotorError('UNSUPPORTED_CLASS_CASE_FORMAT')
    rows = cases_doc.get('cases')
    if not isinstance(rows,list) or not rows:
        raise ClassroomMotorError('NONEMPTY_CLASS_CASES_REQUIRED')
    cases=[];proofs=[];seen=set()
    for row in rows:
        data, proof=compile_case(row,index,eng.RULE_IDS)
        if accepted_routes is not None and (
                proof['teacher_choice_independently_verified']
                or proof['teacher_visual_verified']
                or row.get('paper_trade_teacher_source')):
            if proof['route_id'] not in accepted_routes:
                raise ClassroomMotorError('PRIVATE_ACCEPTANCE_DOES_NOT_CERTIFY_TEACHER_CASE')
        if proof['case_id'] in seen:
            raise ClassroomMotorError('DUPLICATE_TEACHER_CLASS_CASE')
        seen.add(proof['case_id']);cases.append(data);proofs.append(proof)
    # Even a structurally valid paper trade must not be replayed against a
    # verified teacher NO_TRADE instruction. Resolve the conflict before
    # invoking the pinned lifecycle runner, not merely in the final report.
    for data,proof in zip(cases,proofs):
        if ('paper_trade' in data and proof['teacher_choice_in_record']=='NO_TRADE'
                and proof['teacher_choice_independently_verified']
                and proof['teacher_visual_verified']):
            raise ClassroomMotorError('VERIFIED_TEACHER_NO_TRADE_BLOCKS_PAPER_LIFECYCLE')
    # Evaluate the source-bound case before running any proposed paper
    # lifecycle. This uses the same pinned entry evaluator as the runner.
    from entry_engine import Fact,Observation
    for data,proof in zip(cases,proofs):
        if ('paper_trade' in data and proof['teacher_choice_in_record']=='ENTER'
                and proof['teacher_choice_independently_verified']
                and proof['teacher_visual_verified']):
            observation=Observation(data['side'],data['at'],
                {k:Fact(v['value'],v['known_at'],v['source'])
                 for k,v in data['facts'].items()})
            decision=eng.Engine('ARTIN_CLASS_25_VIDEO_TEACHER_MOTOR',
                               tuple(eng.RULE_IDS)).evaluate(data['rule_id'],observation)
            if decision.status!='ELIGIBLE':
                raise ClassroomMotorError('TEACHER_ENTRY_ENGINE_CONFLICT_BLOCKS_PAPER_LIFECYCLE')
    source = {'mode':'ANNOTATED_OFFLINE','plan_id':'ARTIN_CLASS_25_VIDEO_TEACHER_MOTOR',
              'allowed_rules':list(eng.RULE_IDS),'cases':cases,
              'synthetic_only':all(p['source_class']=='SYNTHETIC_TEST' for p in proofs)}
    evaluated = paper.run_document(source)
    # A truncated or duplicated result stream cannot be compared to teacher scenes.
    # zip() would otherwise silently discard unmatched classroom decisions.
    decisions = evaluated.get('decisions')
    if not isinstance(decisions, list) or len(decisions) != len(proofs):
        raise ClassroomMotorError('CLASSROOM_DECISION_COUNT_MISMATCH')
    # The pinned runner returns positional decisions without case identifiers.
    # Re-evaluate each source-bound case with the pinned Engine to ensure
    # an equal-length reordered stream cannot be attributed to another scene.
    for proof,data,decision in zip(proofs,cases,decisions):
        if (data['rule_id']!=proof['route_id']
                or data['side'] not in ('BUY','SELL')
                or proof['citation_index'] not in index):
            raise ClassroomMotorError('CLASSROOM_CASE_PROOF_IDENTITY_MISMATCH')
        from entry_engine import Fact,Observation
        expected=eng.Engine(source['plan_id'],tuple(source['allowed_rules'])).evaluate(
            data['rule_id'],
            Observation(data['side'],data['at'],
                        {k:Fact(v['value'],v['known_at'],v['source'])
                         for k,v in data['facts'].items()}))
        from dataclasses import asdict
        if not isinstance(decision,dict) or decision != asdict(expected):
            raise ClassroomMotorError('CLASSROOM_DECISION_IDENTITY_MISMATCH')
    results=[]
    for proof,decision in zip(proofs,decisions):
        status=decision['status']; teacher=proof['teacher_choice_in_record']
        # Literal classroom NO_TRADE is a scene-scoped protection, not a rule
        # that says all similar future market candles are prohibited. It can
        # block this replay even if the generic entry-engine has other data.
        utterance=proof['exact_scene_speech_polarity_unverified']
        scene_state=('CLASSROOM_NO_ENTRY_CANDIDATE' if teacher=='NO_TRADE' and
                     utterance=='POSSIBLE_NO_TRADE_IN_THIS_SCENE'
                     else 'CLASSROOM_CONDITIONAL_ENTRY_CANDIDATE' if teacher=='ENTER' and
                     utterance=='POSSIBLE_CONDITIONAL_ENTER_IN_THIS_SCENE'
                     else 'CLASSROOM_INSTRUCTION_UNRESOLVED')
        if teacher is None or not proof['teacher_choice_independently_verified'] or not proof['teacher_visual_verified']:
            comparison='NOT_INDEPENDENTLY_CONFIRMED_FROM_CLASS'
        elif teacher=='ENTER':
            comparison='MATCH' if status=='ELIGIBLE' else 'MISMATCH_OR_MISSING_MARKET_FACTS'
        elif teacher=='NO_TRADE':
            comparison='MATCH' if status in ('REJECT','WAIT') else 'MISMATCH_OR_REVIEW_REQUIRED'
        else:
            comparison='NEEDS_SPECIFIC_TEACHER_OUTCOME_REPLAY'
        teacher_entry_ready=(status=='ELIGIBLE' and teacher=='ENTER'
                             and proof['teacher_choice_independently_verified']
                             and proof['teacher_visual_verified']
                             and comparison=='MATCH')
        effective_classroom_action=(
            'NO_TRADE_TEACHER_VETO' if teacher=='NO_TRADE'
            and proof['teacher_choice_independently_verified']
            and proof['teacher_visual_verified']
            else 'PAPER_ENTRY_REVIEW_CANDIDATE' if teacher_entry_ready
            else 'WAIT_FOR_TEACHER_AND_ENGINE_ALIGNMENT')
        results.append({**proof,'effective_classroom_action':effective_classroom_action,
                        'teacher_entry_ready_for_paper_review':teacher_entry_ready,
                        'live_or_demo_order_authorized':False,
                        'motor_status':status,'motor_reason':list(decision['reasons']),
                        'motor_source_legacy_26_slot_ids':list(decision['sources']),
                        'motor_source_25_video_citation':proof['citation_index'],
                        'teacher_engine_comparison':comparison,'classroom_instruction_state':scene_state,
                        'order_created':False})
    summary={'schema':'artin_classroom_teacher_motor_execution_v1',
             'pinned_motor_commit':PINNED_COMMIT,'original_25_class_source_sha256':sha256(citation_path),
             'class_case_input_sha256':sha256(cases_path), 'motor_class_cases':len(results),
             'motor_entry_decisions':sum(x['motor_status']=='ELIGIBLE' for x in results),
             'motor_teacher_comparisons_confirmed':sum(x['teacher_engine_comparison']=='MATCH' for x in results),
             'paper_lifecycle_cases':len(evaluated['paper_trades']),
             'teacher_vetoed_cases':sum(
                 x['effective_classroom_action']=='NO_TRADE_TEACHER_VETO' for x in results),
             'teacher_entry_paper_review_ready_cases':sum(
                 x['teacher_entry_ready_for_paper_review'] for x in results),
             'unverified_eligible_motor_cases':sum(
                 x['motor_status']=='ELIGIBLE' and not x['teacher_entry_ready_for_paper_review']
                 for x in results),
             'all_13_route_implementations_loaded':len(eng.RULE_IDS)==13,
             'trading_authorized':False,'orders_sent':0,
             'teacher_semantic_certification_auto_granted':False,
             'cases':results,'paper_trades':evaluated['paper_trades']}
    target=Path(out)
    if target.exists():raise ClassroomMotorError('NO_OVERWRITE_CLASSROOM_OUTPUT')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--private-citations',type=Path,required=True)
    p.add_argument('--classroom-cases',type=Path,required=True)
    p.add_argument('--pinned-core',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--private-acceptance-sources',type=Path,nargs=3)
    a=p.parse_args()
    s=run(a.private_citations,a.classroom_cases,a.pinned_core,a.out,a.private_acceptance_sources)
    print(json.dumps({k:s[k] for k in ('motor_class_cases','motor_entry_decisions','motor_teacher_comparisons_confirmed','paper_lifecycle_cases','orders_sent')}))

if __name__=='__main__': main()