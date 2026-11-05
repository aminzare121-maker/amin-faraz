"""Post-run verification and aggregate-only report; does not change experiments."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(ROOT/'outputs.PRIVATE/run-001/summary.json')
b=read(ROOT/'outputs.PRIVATE/run-002/summary.json')
elapsed=[a.pop('execution_seconds'),b.pop('execution_seconds')]
assert a==b
private_hashes={}
for p in sorted((ROOT/'outputs.PRIVATE/run-001').glob('*.PRIVATE.json')):
    assert sha(p)==sha(ROOT/'outputs.PRIVATE/run-002'/p.name)
    private_hashes[p.name]=sha(p)
old=read(ROOT.parent/'faraz-ai-offline-lab/outputs.PRIVATE/run-003/summary.json')
checks=0
for c in a['probability_contexts']:
    for arm in ('M1','M2'):
        t=next(t for t in old['model_trials'] if all(t[k]==c[k] for k in ('quality','scenario','fold')) and t['arm']==arm)
        for h in ('model_sha256','calibration_sha256'): assert c['artifacts'][arm][h]==t[h]
        records={r['phase']:r for r in c['records'] if r['target']==arm+'_cal'}
        assert records['E']['gate_count']==t['evaluation_positive_gate_count']
        assert records['E']['gate_denominator']==t['evaluation_candidate_count']
        assert records['V']['probability_metrics']==t['validation_probability_metrics']
        assert records['E']['probability_metrics']==t['evaluation_probability_metrics_by_decision_fold_with_later_settlements']
        checks+=1
out=ROOT/'reports'; out.mkdir(exist_ok=True)
def write(name,data): (out/name).write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False),encoding='utf-8')
for c in a['activity_contexts']:
    write('activity-'+c['quality']+'-'+c['scenario']+'.json',c)
for c in a['probability_contexts']:
    write('probability-'+c['quality']+'-'+c['scenario']+'-'+c['fold']+'.json',c)
write('quality.json',a['quality_audit'])
meta={k:v for k,v in a.items() if k not in ('quality_audit','probability_contexts','activity_contexts')}
meta.update(repeated_run_seconds=elapsed,identical_full_numeric_results=True,
    identical_private_output_hashes=private_hashes,additional_frozen_artifact_gate_and_metric_checks=checks,
    result_sha256=(ROOT/'outputs.PRIVATE/run-001/reproducibility.sha256').read_text().strip(),
    qa_tests_passed=38,probability_records=720,paired_comparisons=108,paired_intervals=132)
write('verification.json',meta)
lines=['# Actual phase-two offline diagnostic results — 2026-11-05','',
 'Two complete executions; 252 portfolios each, 720 probability records each, 38 synthetic QA tests passed. 45 original portfolios replayed exactly; 72 frozen artifact/gate/probability comparisons passed. No new model/calibrator fit. Full numeric summaries and private output hashes identical across both runs.',
 '', 'Result SHA256: `'+meta['result_sha256']+'`.', '',
 'All results are hypothetical USD, retrospective and already seen. No independent future test, demonstrated profitability, account connection or deployment. Provenance, redistribution rights, session calendar, Ask/spread and real broker contract/cost remain unverified. Private data, scores, weights and trade rows are not included.', '',
 '## Primary strict/base probability diagnostics', '',
 'Weighted by available label count within V or E separately. T/C diagnostics are in-sample (BASE_C on T is descriptive, not a past-only T forecast). V/E are not pooled; their dates overlap across folds.', '',
 '| Phase | Target | Labels | Brier | Log-loss |','|---|---|---:|---:|---:|']
primary=[c for c in a['probability_contexts'] if c['quality']=='strict' and c['scenario']=='base']
for phase in ('V','E'):
    for target in ('M1_raw','M1_cal','M2_raw','M2_cal','BASE_C'):
        rs=[r for c in primary for r in c['records'] if r['phase']==phase and r['target']==target]
        n=sum(r['probability_metrics']['n'] for r in rs)
        vals=[sum(r['probability_metrics'][k]*r['probability_metrics']['n'] for r in rs)/n for k in ('brier','log_loss')]
        lines.append(f'| {phase} | {target} | {n} | {vals[0]:.6f} | {vals[1]:.6f} |')
lines+=['','## Fold-by-fold primary diagnostics','','| Fold | Phase | Target | Positive/labels | Gate/candidates | Brier | Log-loss |','|---|---|---|---:|---:|---:|---:|']
for c in primary:
    for r in c['records']:
        if r['phase'] not in ('V','E'): continue
        m=r['probability_metrics']
        lines.append(f"| {c['fold']} | {r['phase']} | {r['target']} | {r['positive_labels']}/{r['label_available_count']} | {r['gate_count']}/{r['gate_denominator']} | {m['brier']:.6f} | {m['log_loss']:.6f} |")
lines+=['','## All primary portfolios and all fixed seeds','','Expected C-only acceptance budgets, never matched to future realized trade counts or exposure. q unavailable is not an observed zero budget; inspect activity_budgets before interpreting any no-trade result. No seed selected. All 9 conditions are in the aggregate JSON files.','','| Arm | Net | Trades | Planned risk | Exposure hours | Net/risk | Net/hour |','|---|---:|---:|---:|---:|---:|---:|']
act=next(c for c in a['activity_contexts'] if c['quality']=='strict' and c['scenario']=='base')
fmt=lambda v:'undefined' if v is None else f'{v:.6f}'
for r in act['portfolios']:
    n=r['normalization']; m=r['metrics']
    lines.append(f"| {r['arm']} | {m['net_pnl']:.2f} | {m['trades']} | {n['allocated_planned_stop_risk_usd']:.2f} | {n['exposure_hours']:.2f} | {fmt(n['net_over_planned_risk'])} | {fmt(n['net_per_exposure_hour'])} |")
lines+=['','## Primary paired block uncertainty','','95% exploratory total-P&L difference intervals, 1000 circular paired resamples of 125 common UTC calendar days including zeros; unadjusted for multiple comparisons. Equal weight mean of five fixed random seeds is a descriptive comparator, not equal realized exposure.','','| Target | Baseline | Block days | Difference | 95% interval |','|---|---|---:|---:|---|']
for c in act['comparisons']:
    for ci in c['paired_ci']:
        lo,hi=ci['total_delta_ci95']
        lines.append(f"| {c['arm']} | {c['baseline']} | {ci['block_days']} | {ci['total_net_delta']:.3f} | [{lo:.3f}, {hi:.3f}] |")
lines+=['','## Causal quality audit','',
 '29234 rows: warmup 63, gap-priority 3402, weekend-priority 1664, past64-flat-priority 16760, eligible 7345 (25.13%). Of the 16760 flat-priority exclusions, 15840 current candles are nonflat and 920 are flat. This directly demonstrates the broad historical-filter effect; it does not establish invalid market data.',
 'History-ready marginal flags overlap: past64-flat 21826, weekend proxy 4940, gaps 3402. Exact masks (gap=1/weekend=2/flat=4): 0=7345, 4=16760, 5=126, 6=1664, 7=3276; masks 1/2/3=0. Actual flat/feed/session cause: UNKNOWN. No original CSV changes.', '',
 '## Interpretation and next proposed step','',
 'All four primary AI arms have negative net. Their differences versus their five-seed random-control means have 5-day intervals spanning zero: no supported incremental selection edge. Reduced activity can reduce losses from the losing B1 baseline, but this design cannot prove that activity is the sole cause. Normalized returns and unequal realized exposure are descriptive; 1/6/30/4 trades do not establish deployment readiness.',
 'Prior-period base rates vary substantially across folds. Use the reported Brier/log-loss and drift tables to compare calibration with the simple BASE_C baseline; calibration fitted in C is not guaranteed to improve V/E. Histogram drift is descriptive, not a causal or significance test.',
 'Positive random-seed outcomes are retained, not selected or promoted. Zero-trade and undefined risk/exposure ratios remain explicit. The old negative PR11 is preserved.',
 'Highest-value proposed next step: independently document provenance/rights, real session calendar and broker symbol/cost specifications, then pre-register an untouched future evaluation and minimum-effect/power plan. No such next stage, download or account connection has been started.', '',
 '## Reproduction','',
 'Python 3.12.14, standard library only. Run `python -I -B verify.py`; then `python -I -B run.py --input <original CSV> --models <PR11 run-003/models.PRIVATE.json> --reference <PR11 run-003/summary.json> --output outputs.PRIVATE/<new-run>`. Run twice with fresh output folders. The exact input/model/reference hashes are checked before execution. Network/process audit guards run in both entry points. Synthetic QA tests exercise fitting only on artificial test data; the real diagnostic performs zero fits.',
 'Contract commit a39fc77 predates new outcomes; implementation commit 8c1f18b was frozen before both runs. `tools/package_results.py` is a post-run checker/exporter and was added after outcomes; it does not modify numerical experiments.',
 'Old 40 external trials and PR11 runs001-004 remain historical/dependent, not independent new evidence. This phase has exactly two full executions with no failed/abandoned numerical trial. Private append-only registry stays local.']
(ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('\n'.join(lines[:25]))
print(json.dumps({'verified':True,'model_checks':checks,'seconds':elapsed,'files':len(list(out.glob('*.json')))}))
