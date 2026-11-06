"""Independent count reconciliation, no source data or strategy execution."""
import json,collections
from pathlib import Path
p=Path(__file__).resolve().parent
s=json.loads((p/'results/mfe-mae-results.json').read_text())
allrows=[r for r in s['metrics'] if r['period_raw']=='ALL']
assert sum(r['entries'] for r in allrows)==7693
assert sum(r['lifetime_bounds_count'] for r in allrows)==7278
assert sum(r['source_unresolved'] for r in allrows)==415
counts=collections.Counter();checks=0
keys=['entries','source_resolved','source_unresolved','lifetime_bounds_count','target_below_1R_count']
for r in allrows:
    for kind in ['month','quarter']:
        periods=[x for x in s['metrics'] if x['candidate']==r['candidate'] and x['cost']==r['cost'] and
                 x['period_raw']!='ALL' and (('-Q' in x['period_raw'])==(kind=='quarter'))]
        for k in keys:
            assert sum(x[k] for x in periods)==r[k]
            checks+=1
    counts.update(r['forward_eligibility'])
    assert sum(r['full12_first_touch'].values())==r['forward_eligibility'].get('ELIGIBLE',0)
result=dict(passed=True,monthly_quarterly_count_reconciliations=checks,
            source_entries=7693,closed_lifetime_bounds=7278,unresolved_kept_separate=415,
            forward_counts=dict(counts),first_touch_mismatch=s['first_touch_trace_mismatches'])
(p/'results/independent-count-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
