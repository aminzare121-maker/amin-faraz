"""Execute the corrected 13-branch Artin engine on owner-provided M15 rows.

S19 recognition correction is applied to the engine, not just a separate
report. Exactly the previous 13 rule ids remain. No broker/order imports.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from artin_owner_motor import read_observations, CORE_COMMIT

HERE=Path(__file__).resolve().parent
CORRECTED=HERE/'teacher_core_s19'
ORIGINAL=HERE/'core'
class CorrectedEngineError(RuntimeError):pass

def verify_source_correction():
    manifest=json.loads((CORRECTED/'TEACHER_CORE_S19_PATCH_MANIFEST.json').read_text(encoding='utf8'))
    if manifest['original_core_git_commit']!=CORE_COMMIT:
        raise CorrectedEngineError('PINNED_REVISION_CHANGED')
    expected=set(manifest['changed_files'])
    if expected!={'entry_engine.py','raw_pipeline.py','examples.py'}:
        raise CorrectedEngineError('UNEXPECTED_ENGINE_CHANGE_SCOPE')
    for name,sha in manifest['sha256'].items():
        actual=CORRECTED/name
        if not actual.is_file() or hashlib.sha256(actual.read_bytes()).hexdigest()!=sha:
            raise CorrectedEngineError('PATCH_SHA_MISMATCH:'+name)
        old=ORIGINAL/name
        if not old.is_file():
            if name.startswith('test_'):continue
            raise CorrectedEngineError('ORIGINAL_CORE_MISSING:'+name)
        if name not in expected and old.read_bytes()!=actual.read_bytes():
            # Test fixture changes are allowed only under a separate test name;
            # nothing in the production rule engine may change unexpectedly.
            if not name.startswith('test_'):
                raise CorrectedEngineError('UNDECLARED_CORE_MUTATION:'+name)
    original_manifest=json.loads((ORIGINAL/'LEGACY_SHA_MANIFEST.json').read_text(encoding='utf8'))
    if original_manifest['source_commit']!=CORE_COMMIT:raise CorrectedEngineError('ORIGINAL_COMMIT_MISMATCH')
    for name,expected_sha in original_manifest['files_sha256'].items():
        p=ORIGINAL/name
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected_sha:
            raise CorrectedEngineError('ORIGINAL_SOURCE_TAMPERED:'+name)
    return manifest

def run(observations:Path,out:Path,selected_rules=None):
    manifest=verify_source_correction()
    if out.exists():raise CorrectedEngineError('OUTPUT_EXISTS_REFUSE_OVERWRITE')
    if not observations.is_file():raise CorrectedEngineError('OBSERVATIONS_NOT_FOUND')
    out.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='artin-teacher-source-run-') as td:
        csvpath=Path(td)/'source_rows.csv'
        with csvpath.open('w',newline='',encoding='utf8') as f:
            writer=csv.writer(f)
            writer.writerow(['time_raw_epoch','open','high','low','close'])
            src=read_observations(observations,writer)
        cmd=[sys.executable,str(CORRECTED/'run_raw.py'),'--csv',str(csvpath),
             '--output-dir',str(out),'--interval-seconds','900']
        for rule in selected_rules or []:cmd.extend(['--rule',rule])
        completed=subprocess.run(cmd,capture_output=True,text=True)
        if completed.returncode:
            raise CorrectedEngineError('CORRECTED_CORE_FAILED:'+completed.stderr[-500:])
    summary=json.loads((out/'SUMMARY.json').read_text(encoding='utf8'))
    if summary['observed_bars']!=src['rows'] or summary['orders_sent']!=0:
        raise CorrectedEngineError('REPLAY_POSTCONDITION_FAILED')
    receipt={'schema':'artin_source_reconciled_s19_core_execution_v1',
             'teacher_core_patch_manifest_sha256':hashlib.sha256((CORRECTED/'TEACHER_CORE_S19_PATCH_MANIFEST.json').read_bytes()).hexdigest(),
             'original_core_commit':CORE_COMMIT,'source':src,
             'teacher_rule_correction':'REVERSAL_THREE_ONE_DOUBT_CANDLE_IN_SENTIMENT_DIRECTION_AND_PIVOT_REQUIRED',
             'pivot_inferred_without_teacher_definition':False,
             'source_locator':'ARTIN 25-machine-speech session19 3440.62-3654.00 (ASR unverified)',
             'all_13_routes_covered':selected_rules is None,
             'evaluations':summary['actual_entry_evaluations'],
             'candidate_eligible':len(summary['eligible_entries']),
             'real_teacher_entries_confirmed':False,
             'broker_orders_sent':0,'teacher_trade_result_verified':False,
             'missing_dependency_occurrences':summary['missing_dependency_occurrences'],
             'summary_file':'SUMMARY.json'}
    (out/'S19_CORRECTED_EXECUTION_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bars',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--rule',action='append',help='optional one or more of the 13 source route ids')
    args=p.parse_args();print(json.dumps(run(args.bars,args.out,args.rule),ensure_ascii=False))