"""Existing 13-route Artin motor + ORIGINAL FXM + ORIGINAL Technical handouts.

Pure offline paper simulation. This wrapper cannot authorize orders or claim
teacher semantic certification; input chart observations are externally sourced.
No existing classroom/risk algorithms are modified.
"""
from __future__ import annotations
import argparse, hashlib, json, tempfile
from pathlib import Path
from decimal import Decimal
from artin_fxm_teacher_motor import run as fxm_run
from technical_teacher_policy import apply_technical_handout


def _digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(earlier, cases):
    if earlier.get('schema') != 'artin_fxmgated_teacher_motor_v1':
        raise ValueError('FXM_ENGINE_REPORT_REQUIRED')
    indexed={c['case_id']:c for c in cases}
    if len(indexed)!=len(cases):raise ValueError('DUPLICATE_CASE_ID')
    outputs=[]
    for prior in earlier['results']:
        row=indexed[prior['case_id']]
        result=apply_technical_handout(route=prior['entry_route'],side=row['side'],
             at=row['market_decision_at'],
             evidence=row.get('technical_chart'),fxm_sizing=prior.get('fxm_sizing'),
             rr=earlier['rr'])
        outputs.append({'case_id':prior['case_id'],
                        'original_entry_core_status':prior['entry_core_status'],
                        'original_fxm_status':prior['fxm_status'],
                        'technical':result})
    return {'schema':'artin_source_guarded_technical_fxm_motor_v1',
            'pinned_core_commit':earlier['pinned_core_commit'],
            'original_class_cases':earlier['original_class_cases'],
            'technical_cases_checked':len(outputs),
            'paper_technical_plans':sum(r['technical']['status']==
                       'PAPER_TECHNICAL_FXM_CONDITIONS_SATISFIED' for r in outputs),
            'teacher_semantic_certification':False,
            'actual_mt5_trading_test':False,'orders_enabled':False,'orders_sent':0,
            'results':outputs}


def run(*,citation_path,cases_path,core,fxm_pdf,technical_pdf,out,
        balance,reference_balance,risk_pct,risk_style,winrate=None,winrate_evidence=None,
        action_events=None,source_folder=None):
    if not Path(fxm_pdf).is_file() or not Path(technical_pdf).is_file():
        raise FileNotFoundError('BOTH_ORIGINAL_FXM_AND_TECHNICAL_PDFS_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='artin_technical_fxm_') as t:
        earlier=fxm_run(citation_path=citation_path,cases_path=cases_path,core=core,
             fxm_pdf=fxm_pdf,out=Path(t)/'fxm.json',balance=balance,
             reference_balance=reference_balance,risk_pct=risk_pct,
             risk_style=risk_style,winrate=winrate,winrate_evidence=winrate_evidence,
             action_events=action_events,source_folder=source_folder)
    cases=json.loads(Path(cases_path).read_text(encoding='utf-8'))['cases']
    result=evaluate(earlier,cases)
    result['source_sha256']={'technical_pdf':_digest(technical_pdf),
       'fxm_pdf':_digest(fxm_pdf),'cases':_digest(cases_path),
       'private_citations':_digest(citation_path)}
    path=Path(out)
    if path.exists():raise FileExistsError('NO_OVERWRITE')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='Source-only Technical + FXM + pinned Artin motor; paper, no orders')
    p.add_argument('--private-citations',type=Path,required=True)
    p.add_argument('--classroom-cases',type=Path,required=True)
    p.add_argument('--pinned-core',type=Path,required=True)
    p.add_argument('--fxm-pdf',type=Path,required=True)
    p.add_argument('--technical-pdf',type=Path,required=True)
    p.add_argument('--balance',required=True)
    p.add_argument('--reference-balance',required=True)
    p.add_argument('--risk-percent',required=True)
    p.add_argument('--style',choices=['DAY_TRADE','SCALP','FAST_SCALP'],required=True)
    p.add_argument('--winrate')
    p.add_argument('--winrate-evidence')
    p.add_argument('--teacher-action-events',type=Path)
    p.add_argument('--original-25-sessions-dir',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(citation_path=a.private_citations,cases_path=a.classroom_cases,
         core=a.pinned_core,fxm_pdf=a.fxm_pdf,technical_pdf=a.technical_pdf,
         out=a.out,balance=a.balance,reference_balance=a.reference_balance,
         risk_pct=a.risk_percent,risk_style=a.style,winrate=a.winrate,
         winrate_evidence=a.winrate_evidence,action_events=a.teacher_action_events,
         source_folder=a.original_25_sessions_dir)
    print(json.dumps({k:result[k] for k in ('original_class_cases',
          'technical_cases_checked','paper_technical_plans','orders_sent')}))

if __name__=='__main__':main()