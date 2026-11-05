"""Read existing results only; no strategy replay, trading, or database writes."""
import json,sqlite3,hashlib
from collections import Counter
from contextlib import closing
from pathlib import Path
from registry import digest
from test_selector import bars
from test_real_stage import fixture

ROOT=Path(__file__).resolve().parent
RUN='66121ec43b886035c7500c0dc86ab267b91b5c47c8197a7231a17a2c60f04499'

def result(path,run):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        row=db.execute('SELECT result,result_sha FROM reusable_runs WHERE id=?',(run,)).fetchone()
    if row is None:raise ValueError('MISSING_RUN')
    value=json.loads(row[0])
    if digest(value)!=row[1]:raise ValueError('RESULT_TAMPER')
    return value,row[1]

def analyze(report):
    reasons=Counter();combinations=Counter();examples={};groups={};total=paired=0
    for candidate in report['candidates']:
        for scenario,metrics in candidate['validation'].items():
            group=Counter()
            for index,row in enumerate(metrics['rows']):
                for control in row['matched_controls']:
                    total+=1;group[control['status']]+=1
                    if control['status']=='PAIRED_SCENARIO_ONLY':paired+=1;continue
                    why=control['reasons'];reasons.update(why);combinations[' + '.join(sorted(why))]+=1
                    for reason in why:
                        examples.setdefault(reason,dict(candidate=candidate['id'],scenario=scenario,row_index=index,
                            seed=control['seed'],entry_time=row['entry_time'],
                            candidate_duration=control['candidate_duration_seconds'],control_duration=control['duration_seconds'],
                            candidate_capital=control['candidate_capital_before'],control_capital=control['capital_before'],
                            candidate_net=row['net'],control_net=control['net'],
                            candidate_exit_reason=row['trace']['exit_reason'],control_exit_reason=control['trace']['exit_reason'],
                            reasons=why,control_trace_sha=digest(control)))
            groups[candidate['id']+'/'+scenario]=dict(group)
    return dict(total=total,paired=paired,incomparable=total-paired,reason_counts=dict(reasons),
                mutually_exclusive_combinations=dict(combinations),groups=groups,examples=examples,
                note='Reason counts overlap; combinations sum to incomparable; no threshold or seed changed')

def recover():
    baseline=json.loads((ROOT/'stage7-private-exposure-inventory.json').read_text())
    recipes={'test_selector.bars':bars(),'test_real_stage.fixture':fixture(),
             'stage4_qa.actual':[dict(b,available=b['observed_at'],time_basis='synthetic-UTC') for b in fixture()]}
    by_hash={digest(v):(k,v) for k,v in recipes.items()};out=[];seen=set()
    for old in baseline['rows']:
        if old['run'] in seen:continue
        seen.add(old['run']);matches=[by_hash[h] for h in old['datasets'].values() if h in by_hash]
        item=dict(run=old['run'],status='NEEDS_REVIEW',exposure_time='UNKNOWN',actual_market_utc='NOT_APPLICABLE_SYNTHETIC',
                  dataset_hashes=old['datasets'],protocol_hash=old['protocol_hash'],intended_interval=None)
        if len(matches)==1:
            name,data=matches[0];item.update(recipe=name,dataset_hash_matched=True)
            split=old['split'];bounds=split.get('holdout')
            if not isinstance(bounds,list) and type(split.get('holdout_start')) is int:bounds=[split['holdout_start'],split['bars']]
            if isinstance(bounds,list) and len(bounds)==2:
                a,b=bounds
                if type(a) is int and type(b) is int and 0<=a<b<=len(data):
                    item['intended_interval']=[data[a]['time'],data[b-1]['time']+900]
                    item['interval_basis']='HASH_MATCHED_SYNTHETIC_RECIPE_AND_STORED_SPLIT_NOT_EXPOSURE_RECEIPT'
        out.append(item)
    return dict(runs=out,recipes_hash_matched=sum(x.get('dataset_hash_matched',False) for x in out),
        intended_intervals_recovered=sum(x['intended_interval'] is not None for x in out),
        complete_exposures_verified=0,exposure_time_unknown=len(out),
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('test_selector.py','test_real_stage.py','stage4_qa.py','verify_stage.py')},
        financial_gate='BLOCKED',rollback='ROLLBACK_PROTECTION_UNVERIFIED')

def main():
    report,sha=result(ROOT/'selector-research.sqlite',RUN)
    counts=analyze(report);counts.update(run=RUN,result_sha=sha,synthetic=True)
    assert (counts['total'],counts['paired'],counts['incomparable'])==(2890,334,2556)
    assert sum(counts['mutually_exclusive_combinations'].values())==2556
    (ROOT/'stage8-incomparable-analysis.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    recovery=recover();(ROOT/'stage8-evidence-recovery.json').write_text(json.dumps(recovery,indent=2),encoding='utf-8')
    print(json.dumps({'counts':{k:counts[k] for k in ('total','paired','incomparable','reason_counts','mutually_exclusive_combinations')},
                      'recovery':{k:v for k,v in recovery.items() if k not in ('runs','source_hashes')}}))

if __name__=='__main__':main()
