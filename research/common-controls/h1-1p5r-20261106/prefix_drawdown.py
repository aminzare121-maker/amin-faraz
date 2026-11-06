"""Reconstruct continuous-prefix sampled DD from saved results; no replay."""
import argparse,csv,json,hashlib
from pathlib import Path
from decimal import Decimal as D
from h1_lab import liquidation,dd
p=argparse.ArgumentParser()
for n in ('raw-dir','private-trace','out'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args()
m=json.loads((a.raw_dir/'manifest.json').read_text());bars={}
for c in m['chunks'].values():
    if c['kind']!='M15':continue
    path=a.raw_dir/c['csv']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==c['csv_sha256']
    for r in csv.DictReader(path.open()):
        bars[int(r['time'])]={k:D(r[k]) for k in ('open','high','low','close')}
cells=json.loads(a.private_trace.read_text());result=[]
for method in sorted({c['candidate'] for c in cells}):
    for cost in ('base','envelope'):
        settings=dict(spread='.3',slippage='.1',commission_roundtrip_per_lot='0') if cost=='base' else dict(spread='.50',slippage='.20',commission_roundtrip_per_lot='10')
        cs=[c for c in cells if c['candidate']==method and c['cost']==cost and c['cohort']=='continuous_known_prefix']
        for arm,name in enumerate(('baseline_overlay','H1_1p5R')):
            points=[D(10000)];nets=[];cash=D(10000);censored=False
            for c in cs:
                assert D(c['starting_equity'][arm])==cash
                for r in c['rows'][arm]:
                    points.append(cash+liquidation(bars[r['entry_time']]['open'],r,settings))
                    for t in range(r['entry_time'],r['exit_time'],900):
                        if t+900==r['exit_time']:
                            if r['net_scenario_usd'] is None:censored=True;break
                            net=D(r['net_scenario_usd']);cash+=net;nets.append(net);points.append(cash)
                        else:points.append(cash+liquidation(bars[t]['close'],r,settings))
                    if censored:break
                if censored:break
            peak=D(10000);absolute=relative=D(0)
            for v in points:
                peak=max(peak,v);absolute=max(absolute,peak-v);relative=max(relative,(peak-v)/peak)
            result.append(dict(candidate=method,cost=cost,arm=name,
                observed_prefix_closed_dd=dd(nets),observed_prefix_sampled_mtm_dd_usd=str(absolute),
                observed_prefix_sampled_mtm_dd_fraction=str(relative),sample_points=len(points),
                arm_path_censored=censored,shared_controller_blocked=cs[-1]['unknown'],
                full_year_dd='UNKNOWN',exact_intrabar_mtm_dd='UNMEASURABLE'))
a.out.write_text(json.dumps(dict(replay_performed=False,metrics=result,
    input_private_trace_sha256=hashlib.sha256(a.private_trace.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
print('PREFIX_DRAWDOWN_RECONSTRUCTED_NO_REPLAY')
