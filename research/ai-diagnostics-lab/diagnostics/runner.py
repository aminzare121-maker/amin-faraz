"""Reconstruct frozen inference and run every preregistered diagnostic arm."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from faraz_lab import learning
from faraz_lab import runner as frozen
from faraz_lab.data import load_csv, build_signals, QUALITIES, DATA_SHA256
from faraz_lab.signals import b1, b2
from faraz_lab.simulator import simulate_event
from faraz_lab.types import Policy, Symbol
from diagnostics.probabilities import diagnose_fold, TARGETS
from diagnostics.controls import evaluate_activity
from diagnostics.quality import audit_quality

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = '1d7b3ea2f9fd5ea56924d22b43525f3d3bf6fb58d749a3b2cf6cb342e18a6761'
REFERENCE_SHA = '31c89702382cefdbf8502fa01a0d9b68d62e1554361c7e12b142badd4389ea9c'
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def manifest():
    paths = [ROOT/'CONTRACT.md', *ROOT.glob('*.py'), *ROOT.glob('diagnostics/*.py'), *ROOT.glob('faraz_lab/*.py'), *ROOT.glob('tests/*.py')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}
def forbidden_fit(*args, **kwargs):
    raise RuntimeError('No fitting is authorized in this implementation')
def run(args):
    started = time.perf_counter()
    output = Path(args.output).resolve()
    if output.parent != (ROOT/'outputs.PRIVATE').resolve() or output.exists():
        raise ValueError('Output must be a new directory directly under outputs.PRIVATE')
    reference = json.loads(Path(args.reference).read_text(encoding='utf-8'))
    assert frozen.digest({k:v for k,v in reference.items() if k != 'execution_seconds'}) == REFERENCE_SHA
    assert sha(args.models) == MODEL_SHA
    before = manifest()
    for path in ROOT.glob('faraz_lab/*.py'):
        assert sha(path) == reference['code_manifest'][path.relative_to(ROOT).as_posix()]
    models = json.loads(Path(args.models).read_text(encoding='utf-8'))
    for module in (learning, frozen):
        for name in ('fit_logistic', 'fit_tree', 'fit_calibrator', 'experiment_models'):
            if hasattr(module, name):
                setattr(module, name, forbidden_fit)
    bars, metadata = load_csv(args.input)
    assert sha(args.input) == DATA_SHA256
    output.mkdir(parents=True)
    registry = ROOT/'experiments.registry.PRIVATE.jsonl'
    def register(record):
        with registry.open('a', encoding='utf-8') as f:
            f.write(frozen.canonical(record)+'\n')
    register({'event':'start', 'output':output.name, 'code_sha256':frozen.digest(before)})
    summary = {'schema':1, 'code_manifest':before, 'code_sha256':frozen.digest(before),
        'data':metadata, 'models_sha256':MODEL_SHA, 'reference_sha256':REFERENCE_SHA,
        'python':platform.python_version(), 'new_fits':0, 'threshold':.55,
        'quality_audit':audit_quality(bars), 'probability_contexts':[], 'activity_contexts':[],
        'prior_trials':'40 external trials and PR11 runs001-004 preserved; retrospective dependent development',
        'limitations':reference['limitations'], 'independent_future_test':False,
        'deployment_authorized':False}
    policy, spec = Policy(), Symbol()
    replay_count = 0
    for quality in QUALITIES:
        signals, _ = build_signals(bars, quality, b1)
        second, _ = build_signals(bars, quality, b2)
        for scenario in frozen.SCENARIOS:
            print(f'RUN {quality}/{scenario.name}', flush=True)
            group = next(g for g in models if g['quality']==quality and g['scenario']==scenario.name)
            events = {i:e for i,c in signals.items() if (e:=simulate_event(bars,c,scenario,policy,spec)) is not None}
            scores = {t:{} for t in TARGETS}
            budgets = {}
            for fold in frozen.folds():
                artifacts = {a['arm']:a for a in group['artifacts'] if a['fold']==fold['name']}
                pub, maps, q = diagnose_fold(fold,signals,events,bars,artifacts,scenario,policy)
                pub.update(quality=quality,scenario=scenario.name)
                summary['probability_contexts'].append(pub)
                budgets[fold['name']] = q
                for target in TARGETS:
                    scores[target].update(maps[target])
            public, private = evaluate_activity(bars,signals,second,scores,budgets,scenario,policy,spec,frozen.folds(),primary=quality=='strict' and scenario.name=='base')
            public.update(quality=quality,scenario=scenario.name)
            for row in public['portfolios']:
                old_arm = {'M1_cal':'M1','M2_cal':'M2'}.get(row['arm'],row['arm'])
                if old_arm in ('B0','B1','B2','M1','M2'):
                    old = next(r for r in reference['portfolio_results'] if r['quality']==quality and r['scenario']==scenario.name and r['arm']==old_arm)
                    assert row['metrics']==old['metrics'], (quality,scenario.name,old_arm,'metrics mismatch')
                    assert row['fold_daily_net']==old['fold_daily_net']
                    replay_count += 1
            summary['activity_contexts'].append(public)
            (output/f'{quality}-{scenario.name}.PRIVATE.json').write_text(frozen.canonical(private),encoding='utf-8')
            register({'event':'condition_complete','quality':quality,'scenario':scenario.name,'portfolios':28})
    assert len(summary['probability_contexts'])==36 and replay_count==45
    assert before==manifest() and sha(args.input)==DATA_SHA256 and sha(args.models)==MODEL_SHA
    summary.update(reference_portfolios_exactly_replayed=replay_count,portfolio_trials=252,
        source_data_models_unchanged=True, execution_seconds=round(time.perf_counter()-started,3))
    digest = frozen.digest({k:v for k,v in summary.items() if k!='execution_seconds'})
    (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False),encoding='utf-8')
    (output/'reproducibility.sha256').write_text(digest+'\n',encoding='ascii')
    register({'event':'complete','output':output.name,'reproducibility_sha256':digest})
    print(json.dumps({'complete':True,'portfolios':252,'replayed':45,'seconds':summary['execution_seconds'],'sha256':digest}),flush=True)
def main():
    parser=argparse.ArgumentParser()
    for name in ('input','models','reference','output'):
        parser.add_argument('--'+name,required=True)
    run(parser.parse_args())
