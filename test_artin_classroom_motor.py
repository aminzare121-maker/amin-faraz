"""Tests for actual 13-branch execution, with SYNTHETIC classroom fixtures.
No fixture is claimed to be a certified teacher or broker trade.
"""
import json
import os
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from artin_classroom_motor import ClassroomMotorError, compile_case, index_original_citations, run
CORE=Path(os.environ.get('ARTIN_PINNED_LEGACY_DIR',ROOT/'core'))
sys.path.insert(0,str(CORE))
from examples import demo_document
from entry_engine import RULE_IDS


def citations():
    rows=[]
    for i in range(24):
        route=RULE_IDS[i%13]
        rows.append({'citation_index':i+1,'route_id':route,'session':(i%25)+1,
                     'start_seconds':100,'end_seconds':200,
                     'excerpts':[{'start':105,'end':108,'asr_segment_id':'ASR-'+str(i)}]})
    return {'summary':{'sessions':25},'citations':rows}


def records():
    all_citations=citations()['citations']
    first={}
    for c in all_citations:first.setdefault(c['route_id'],c)
    source_cases=[]
    for i,c in enumerate(demo_document()['cases']):
        cite=first[c['rule_id']]
        row={'case_id':'SYNTH_CASE_'+str(i),'citation_index':cite['citation_index'],
             'rule_id':c['rule_id'],'session':cite['session'],'class_seconds':[105,108],
             'source_asr_segment_ids':[cite['excerpts'][0]['asr_segment_id']],
             'side':c['side'],'market_decision_at':c['at'],
             'facts':c['facts'],'source_class':'SYNTHETIC_TEST',
             'teacher_choice':None,'teacher_choice_verified':False,
             'teacher_visual_verified':False}
        if 'paper_trade' in c: row['paper_trade']=c['paper_trade']
        source_cases.append(row)
    return {'schema':'artin_teacher_class_cases_v1','cases':source_cases}


class ClassroomEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.src=self.root/'citations.json';self.cases=self.root/'cases.json';self.out=self.root/'result.json'
        self.source_doc=citations();self.cases_doc=records();self.write()

    def write(self):
        self.src.write_text(json.dumps(self.source_doc),encoding='utf8')
        self.cases.write_text(json.dumps(self.cases_doc),encoding='utf8')

    def test_verified_real_case_requires_scene_speech_ids(self):
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None)
        row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        row['source_asr_segment_ids']=[]
        # Isolate the missing-speech guard from the separate synthetic-source guard.
        for fact in row['facts'].values():
            fact['source']='CLASSROOM_TEST_FIXTURE_NOT_ORIGINAL_EVIDENCE'
        idx=index_original_citations(self.source_doc,RULE_IDS)
        with self.assertRaisesRegex(
                ClassroomMotorError,'VERIFIED_TEACHER_CASE_REQUIRES_SCENE_SPEECH'):
            compile_case(row,idx,RULE_IDS)

    def test_real_teacher_claim_without_private_acceptance_is_blocked(self):
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None)
        row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        for fact in row['facts'].values():
            fact['source']='CLASSROOM_SOURCE_UNVERIFIED'
        self.cases_doc['cases']=[row]
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,
                'PRIVATE_ACCEPTANCE_REQUIRED_FOR_REAL_TEACHER_CLAIM'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_private_dossier_zero_certification_blocks_claimed_teacher_entry(self):
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None)
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        self.write()
        private=[]
        for i in range(3):
            p=self.root/('private_'+str(i)+'.json')
            p.write_text('{}',encoding='utf8')
            private.append(p)
        with patch('artin_13_teacher_acceptance_matrix.evaluate',
                   return_value={'routes':[{'route_id':row['rule_id'],
                                            'teacher_case_certified':False,
                                            'engine_decision_replay_certified':False}]}):
            with self.assertRaisesRegex(ClassroomMotorError,
                                        'PRIVATE_ACCEPTANCE_DOES_NOT_CERTIFY_TEACHER_CASE'):
                run(self.src,self.cases,CORE,self.out,private)
        self.assertFalse(self.out.exists())

    def test_future_fact_cannot_enter_classroom_engine(self):
        first=self.cases_doc['cases'][0]
        key=next(iter(first['facts']))
        first['facts'][key]['known_at']=first['market_decision_at']+1
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'FUTURE_MARKET_FACT_IN_CLASS_CASE'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_invalid_fact_clock_rejected_before_engine(self):
        for clock in (-1, 1.5, '100', None):
            with self.subTest(clock=clock):
                self.cases_doc=records()
                first=self.cases_doc['cases'][0]
                key=next(iter(first['facts']))
                first['facts'][key]['known_at']=clock
                self.write()
                with self.assertRaisesRegex(ClassroomMotorError,'INVALID_MARKET_FACT_CLOCK'):
                    run(self.src,self.cases,CORE,self.out)
                self.assertFalse(self.out.exists())

    def test_non_synthetic_paper_trade_requires_structured_payload(self):
        row=next(c for c in self.cases_doc['cases'] if 'paper_trade' in c)
        row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['paper_trade']='INVALID'
        for fact in row['facts'].values():
            fact['source']='CLASSROOM_TEST_NON_SYNTHETIC_SOURCE'
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'PAPER_LIFECYCLE_OBJECT_REQUIRED'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_teacher_entry_engine_conflict_blocks_paper_lifecycle(self):
        row=next(c for c in self.cases_doc['cases'] if 'paper_trade' in c)
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        # Missing is a supported objective fact state, never silently true.
        key=next(iter(row['facts']))
        row['facts'][key]['value']='MISSING'
        self.write()
        with self.assertRaisesRegex(
                ClassroomMotorError,'TEACHER_ENTRY_ENGINE_CONFLICT_BLOCKS_PAPER_LIFECYCLE'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_synthetic_teacher_claim_cannot_become_paper_review_ready(self):
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None)
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        self.cases_doc['cases']=[row]
        self.write()
        result=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(result['cases'][0]['motor_status'],'ELIGIBLE')
        self.assertFalse(result['cases'][0]['teacher_entry_ready_for_paper_review'])
        self.assertEqual(result['teacher_entry_paper_review_ready_cases'],0)
        self.assertEqual(result['orders_sent'],0)

    def test_verified_teacher_no_entry_overrides_eligible_engine_without_trade(self):
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None)
        row['teacher_choice']='NO_TRADE'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        self.write()
        result=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(result['cases'][0]['motor_status'],'ELIGIBLE')
        self.assertEqual(result['cases'][0]['effective_classroom_action'],
                         'NO_TRADE_TEACHER_VETO')
        self.assertEqual(result['teacher_vetoed_cases'],1)
        self.assertFalse(result['cases'][0]['teacher_entry_ready_for_paper_review'])
        self.assertEqual(result['orders_sent'],0)

    def test_verified_teacher_no_trade_blocks_proposed_paper_lifecycle(self):
        row=next(c for c in self.cases_doc['cases'] if 'paper_trade' in c)
        row['teacher_choice']='NO_TRADE'
        row['teacher_choice_verified']=True
        row['teacher_visual_verified']=True
        self.write()
        with self.assertRaisesRegex(
                ClassroomMotorError,'VERIFIED_TEACHER_NO_TRADE_BLOCKS_PAPER_LIFECYCLE'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_unverified_real_teacher_scene_cannot_create_paper_entry(self):
        row=next(c for c in self.cases_doc['cases'] if 'paper_trade' in c)
        row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['paper_trade_teacher_source']='session_audio'
        row['teacher_choice']='ENTER'
        row['teacher_choice_verified']=False
        row['teacher_visual_verified']=False
        # Replace synthetic fixture provenance so the test reaches the
        # teacher-lifecycle gate rather than the earlier source-integrity gate.
        for fact in row['facts'].values():
            fact['source']='CLASSROOM_TEST_NON_SYNTHETIC_SOURCE'
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'TEACHER_PAPER_LIFECYCLE_NOT_VERIFIED'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_run_all_thirteen_real_legacy_engines_and_paper_lifecycle(self):
        result=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(result['motor_class_cases'],13)
        self.assertEqual(result['motor_entry_decisions'],13)
        self.assertEqual(result['paper_lifecycle_cases'],1)
        self.assertEqual(result['motor_teacher_comparisons_confirmed'],0)
        self.assertEqual(result['teacher_entry_paper_review_ready_cases'],0)
        self.assertEqual(result['unverified_eligible_motor_cases'],13)
        self.assertTrue(all(not c['teacher_entry_ready_for_paper_review']
                            and not c['live_or_demo_order_authorized']
                            for c in result['cases']))
        self.assertEqual(result['orders_sent'],0)
        self.assertTrue(self.out.exists())
        self.assertTrue(all(row['motor_status']=='ELIGIBLE' for row in result['cases']))

    def test_case_proof_route_identity_rejected_if_compiler_misattributed(self):
        from artin_classroom_motor import compile_case as original_compile
        def corrupt(*args,**kwargs):
            data,proof=original_compile(*args,**kwargs)
            proof['route_id']='WRONG_ROUTE'
            return data,proof
        with patch('artin_classroom_motor.compile_case',side_effect=corrupt):
            with self.assertRaisesRegex(ClassroomMotorError,'CLASSROOM_CASE_PROOF_IDENTITY_MISMATCH'):
                run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_dropped_or_extra_engine_decision_is_rejected(self):
        # A mismatched result stream must never be silently paired via zip().
        from run_engine import run_document as original_run
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                def corrupt(source, delta=delta):
                    result = original_run(source)
                    result['decisions'] = (result['decisions'][:delta]
                                           if delta == -1
                                           else result['decisions'] + result['decisions'][:1])
                    return result
                with patch('run_engine.run_document', side_effect=corrupt):
                    with self.assertRaisesRegex(ClassroomMotorError, 'CLASSROOM_DECISION_COUNT_MISMATCH'):
                        run(self.src, self.cases, CORE, self.out)
                self.assertFalse(self.out.exists())

    def test_reordered_equal_length_decisions_cannot_match_wrong_teacher_scenes(self):
        from run_engine import run_document as original_run
        def reorder(source):
            result=original_run(source)
            result['decisions'][0],result['decisions'][1] = (
                result['decisions'][1],result['decisions'][0])
            return result
        with patch('run_engine.run_document', side_effect=reorder):
            with self.assertRaisesRegex(ClassroomMotorError,'CLASSROOM_DECISION_IDENTITY_MISMATCH'):
                run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_actual_classroom_excerpt_with_missing_market_facts_is_review_not_trade(self):
        row=self.cases_doc['cases'][0]
        row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['facts']={};row.pop('paper_trade',None)
        row['teacher_choice']='NO_TRADE';row['teacher_choice_verified']=False
        self.cases_doc['cases']=[row];self.write()
        r=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(r['cases'][0]['motor_status'],'REVIEW')
        self.assertEqual(r['cases'][0]['teacher_engine_comparison'],'NOT_INDEPENDENTLY_CONFIRMED_FROM_CLASS')
        self.assertEqual(r['motor_entry_decisions'],0)

    def test_literal_classroom_no_trade_is_scoped_not_generalized(self):
        c=self.source_doc['citations'][0];c['excerpts'][0]['text_unverified']='اینجا ورود نمی کنیم'
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None);row['facts']={};row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['teacher_choice']='NO_TRADE';row['teacher_choice_verified']=False
        self.cases_doc['cases']=[row];self.write()
        report=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(report['cases'][0]['classroom_instruction_state'],'CLASSROOM_NO_ENTRY_CANDIDATE')
        self.assertEqual(report['cases'][0]['motor_status'],'REVIEW')
        self.assertEqual(report['orders_sent'],0)

    def test_affirmative_classroom_phrase_never_bypasses_market_guards(self):
        c=self.source_doc['citations'][0];c['excerpts'][0]['text_unverified']='رو کلوز تاییده ورود میکنیم'
        row=self.cases_doc['cases'][0]
        row.pop('paper_trade',None);row['facts']={};row['source_class']='CLASSROOM_ASR_CANDIDATE'
        row['teacher_choice']='ENTER';row['teacher_choice_verified']=False
        self.cases_doc['cases']=[row];self.write()
        report=run(self.src,self.cases,CORE,self.out)
        self.assertEqual(report['cases'][0]['classroom_instruction_state'],'CLASSROOM_CONDITIONAL_ENTRY_CANDIDATE')
        self.assertEqual(report['cases'][0]['motor_status'],'REVIEW')
        self.assertEqual(report['motor_entry_decisions'],0)

    def test_bad_lesson_session_rejected(self):
        self.cases_doc['cases'][0]['session']=25;self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'CLASS_SESSION_MISMATCH'):
            run(self.src,self.cases,CORE,self.out)

    def test_wrong_lesson_route_rejected(self):
        self.cases_doc['cases'][0]['rule_id']='BREAK_STRONG';self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'CLASS_CITATION_ROUTE_MISMATCH'):
            run(self.src,self.cases,CORE,self.out)

    def test_same_citation_segment_from_different_scene_is_rejected(self):
        # The citation is 100..200, but this decision scene is 150..160.
        # ASR at 105..108 belongs to another moment of the lesson.
        row=self.cases_doc['cases'][0]
        row['class_seconds']=[150,160]
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,
                                    'CLASS_SOURCE_SEGMENT_OUTSIDE_CASE_SCENE'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_scene_boundary_touch_without_overlap_is_rejected(self):
        row=self.cases_doc['cases'][0]
        row['class_seconds']=[108,120]
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,
                                    'CLASS_SOURCE_SEGMENT_OUTSIDE_CASE_SCENE'):
            run(self.src,self.cases,CORE,self.out)
        self.assertFalse(self.out.exists())

    def test_no_unverified_asr_ids_spliced(self):
        self.cases_doc['cases'][0]['source_asr_segment_ids']=['not-a-source'];self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'CLASS_SOURCE_SEGMENT_NOT_IN_CITATION'):
            run(self.src,self.cases,CORE,self.out)

    def test_synthetic_fact_without_explicit_fixture_declaration_rejected(self):
        self.cases_doc['cases'][0]['source_class']='CLASSROOM_ASR_CANDIDATE';self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'UNDECLARED_SYNTHETIC_SOURCE'):
            run(self.src,self.cases,CORE,self.out)

    def test_duplicate_case_id_rejected(self):
        self.cases_doc['cases'][1]['case_id']=self.cases_doc['cases'][0]['case_id'];self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'DUPLICATE_TEACHER_CLASS_CASE'):
            run(self.src,self.cases,CORE,self.out)

    def test_cannot_overwrite_prior_motor_result(self):
        run(self.src,self.cases,CORE,self.out)
        with self.assertRaisesRegex(ClassroomMotorError,'NO_OVERWRITE_CLASSROOM_OUTPUT'):
            run(self.src,self.cases,CORE,self.out)

    def test_incomplete_pinned_manifest_cannot_bypass_hash_validation(self):
        from shutil import copytree
        with tempfile.TemporaryDirectory() as d:
            cp=Path(d)/'core';copytree(CORE,cp)
            manifest=cp/'LEGACY_SHA_MANIFEST.json'
            original=json.loads(manifest.read_text(encoding='utf8'))
            for hashes in ({}, {'entry_engine.py': original['files_sha256']['entry_engine.py']}):
                modified=dict(original, files_sha256=hashes)
                manifest.write_text(json.dumps(modified),encoding='utf8')
                with self.assertRaisesRegex(ClassroomMotorError,'PINNED_ENGINE_MANIFEST_INVALID'):
                    run(self.src,self.cases,cp,self.out)
                self.assertFalse(self.out.exists())

    def test_pinned_manifest_rejects_parent_path_escape(self):
        from shutil import copytree
        with tempfile.TemporaryDirectory() as d:
            cp=Path(d)/'core';copytree(CORE,cp)
            manifest=cp/'LEGACY_SHA_MANIFEST.json'
            modified=json.loads(manifest.read_text(encoding='utf8'))
            modified['files_sha256']['../outside.py']='0'*64
            manifest.write_text(json.dumps(modified),encoding='utf8')
            with self.assertRaisesRegex(ClassroomMotorError,'PINNED_ENGINE_MANIFEST_INVALID'):
                run(self.src,self.cases,cp,self.out)
            self.assertFalse(self.out.exists())

    def test_tampered_pinned_core_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            from shutil import copytree
            cp=Path(d)/'core';copytree(CORE,cp)
            (cp/'entry_engine.py').write_text('ORDER_SEND=1')
            with self.assertRaisesRegex(ClassroomMotorError,'PINNED_ENGINE_SOURCE_CHANGED'):
                run(self.src,self.cases,cp,self.out)

    def test_citation_interval_overlap_not_full_containment_is_allowed(self):
        self.source_doc['citations'][0]['excerpts'][0]['start']=99
        self.write()
        self.assertEqual(len(index_original_citations(self.source_doc, RULE_IDS)),24)

    def test_unanchored_source_segment_is_rejected(self):
        self.source_doc['citations'][0]['excerpts'][0]['start']=97
        self.source_doc['citations'][0]['excerpts'][0]['end']=99
        self.write()
        with self.assertRaisesRegex(ClassroomMotorError,'SEGMENT_OUTSIDE_CLASS_CITATION'):
            run(self.src,self.cases,CORE,self.out)

if __name__=='__main__':unittest.main(verbosity=2)