"""Run the actual pinned 13-route classroom decision core WITH FXM risk gates.

This adapter never calls a broker and never upgrades a blank/unverified
classroom fact to a trade. It does not change the pinned 13-route algorithms.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from decimal import Decimal
from core.capital import Costs, Instrument
from artin_classroom_motor import run as classroom_run
from fxm_teacher_policy import (AccountRisk, risk_sized_plan, winrate_target_policy,
                                timeframe_notes)


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate_fxmgates(original, case_rows, account, *, risk_style, winrate=None, winrate_evidence=None):
    by_case={r['case_id']:r for r in case_rows}
    risk_state=account.assess()
    historical_rr=(winrate_target_policy(winrate,evidence_source=winrate_evidence)
                   if winrate is not None else {'status':'REVIEW_WINRATE_NOT_PROVIDED','orders_enabled':False})
    results=[]
    for result in original['cases']:
        row=by_case[result['case_id']]
        evidence_confirmed=(result['teacher_choice_independently_verified'] is True and
                            result['teacher_visual_verified'] is True and
                            result['teacher_choice_in_record']=='ENTER')
        if risk_state['status'] != 'RISK_BUDGET_AVAILABLE':
            status=risk_state['status']; sizing=None
        elif result['motor_status'] != 'ELIGIBLE' or not evidence_confirmed:
            status='WAIT_TEACHER_ENTRY_SEMANTICS_AND_CHART_FACTS'; sizing=None
        elif historical_rr['status'] not in ('RR_CANDIDATE_FROM_HANDOUT',):
            status='WAIT_FXM_TARGET_POLICY'; sizing=None
        elif not isinstance(row.get('paper_trade'),dict):
            status='WAIT_SOURCED_ENTRY_STOP_AND_CONTRACT'; sizing=None
        else:
            t=row['paper_trade'];i=t['instrument'];c=t['costs']
            sizing=risk_sized_plan(account,row['side'],t['entry_price'],t['initial_stop'],
                    Instrument(Decimal(str(i['money_per_price_unit_per_lot'])),
                               Decimal(str(i['min_lot'])), Decimal(str(i['lot_step']))),
                    Costs(Decimal(str(c['round_trip_fee_per_lot'])),
                          Decimal(str(c['adverse_price_allowance']))),
                    stop_source=row.get('paper_trade_teacher_source',''),
                    entry_source=row.get('paper_trade_teacher_source',''))
            status=sizing['status']
        results.append({'case_id':result['case_id'],
                'entry_route':result['route_id'],
                'entry_core_status':result['motor_status'],
                'fxm_status':status,
                'fxm_sizing':sizing,
                'orders_enabled':False})
    return {'schema':'artin_fxmgated_teacher_motor_v1',
            'pinned_core_commit':original['pinned_motor_commit'],
            'FXM_reference':'FXM.pdf#pages=2-7',
            'risk':risk_state,'rr':historical_rr,
            'style':timeframe_notes(risk_style),
            'original_13_route_engine_loaded':original['all_13_route_implementations_loaded'],
            'original_class_cases':len(original['cases']),
            'fxm_cases_checked':len(results),
            'fxm_paper_intents':sum(r['fxm_status']=='PAPER_SIZED_ONLY' for r in results),
            'broker_connected':False,'orders_sent':0,
            'semantic_certification_claimed':False,
            'results':results}


def run(*,citation_path,cases_path,core,fxm_pdf,out,
        balance,reference_balance,risk_pct,risk_style,winrate=None,winrate_evidence=None,
        action_events=None,source_folder=None):
    if not Path(fxm_pdf).is_file():
        raise FileNotFoundError('FXM_ORIGINAL_PDF_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='artin_fxm_') as d:
        prior=classroom_run(citation_path,cases_path,core,Path(d)/'classroom.json',
                            action_events,source_folder)
    cases=json.loads(Path(cases_path).read_text(encoding='utf8'))['cases']
    report=evaluate_fxmgates(prior,cases,AccountRisk(Decimal(str(balance)),
                 Decimal(str(reference_balance)),Decimal(str(risk_pct))),
                 risk_style=risk_style,winrate=winrate,winrate_evidence=winrate_evidence)
    report['source_evidence_sha256']={'fxm_pdf':hash_file(fxm_pdf),
          'citations':hash_file(citation_path),'cases':hash_file(cases_path)}
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise FileExistsError('OUTPUT_EXISTS_NO_OVERWRITE')
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return report


def main():
    p=argparse.ArgumentParser(description='Run 13-route Artin core with original FXM risk policy: paper only')
    p.add_argument('--private-citations',type=Path,required=True)
    p.add_argument('--classroom-cases',type=Path,required=True)
    p.add_argument('--pinned-core',type=Path,required=True)
    p.add_argument('--fxm-pdf',type=Path,required=True)
    p.add_argument('--balance',required=True)
    p.add_argument('--reference-balance',required=True)
    p.add_argument('--risk-percent',required=True)
    p.add_argument('--style',choices=['DAY_TRADE','SCALP','FAST_SCALP'],required=True)
    p.add_argument('--winrate',type=str)
    p.add_argument('--winrate-evidence',type=str)
    p.add_argument('--teacher-action-events',type=Path)
    p.add_argument('--original-25-sessions-dir',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(citation_path=a.private_citations,cases_path=a.classroom_cases,
        core=a.pinned_core,fxm_pdf=a.fxm_pdf,out=a.out,
        balance=a.balance,reference_balance=a.reference_balance,risk_pct=a.risk_percent,
        risk_style=a.style,winrate=a.winrate,winrate_evidence=a.winrate_evidence,
        action_events=a.teacher_action_events,source_folder=a.original_25_sessions_dir)
    print(json.dumps({k:result[k] for k in ('original_13_route_engine_loaded',
         'fxm_cases_checked','fxm_paper_intents','orders_sent')}))

if __name__=='__main__':main()