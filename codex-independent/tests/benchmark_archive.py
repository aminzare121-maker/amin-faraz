"""Synthetic archive batching benchmark, never MT5 or video performance."""
import argparse,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from candle_archive import CandleArchive

def run(count=100):
    rows=[dict(time=900*(i+1),open=2300,high=2302,low=2298,close=2301,
               tick_volume=i+1,spread=20,real_volume=0) for i in range(count)]
    results={}
    with tempfile.TemporaryDirectory() as folder:
        for mode,batch_size in [('one_bar_transactions',1),('batched_transaction',count)]:
            archive=CandleArchive(Path(folder)/mode);totals={k:0.0 for k in ['validation','processing','storage','verification','total']}
            started=time.perf_counter()
            for i in range(0,len(rows),batch_size):
                result=archive.ingest(rows[i:i+batch_size],current_bar_open=900*(count+2))
                for k in totals:totals[k]+=result['timings_seconds'][k]
            elapsed=time.perf_counter()-started;verified=archive.verify()
            results[mode]=dict(rows=verified['count'],head_sha256=verified['head_sha256'],
                wall_seconds=elapsed,stage_seconds=totals,archive_integrity_verified=True)
        if results['one_bar_transactions']['head_sha256']!=results['batched_transaction']['head_sha256']:
            raise ValueError('BATCHING_CHANGED_ARCHIVE_OUTPUT')
    return dict(schema='synthetic_archive_batch_benchmark_v1',synthetic_input=True,
        actual_mt5_receiving_seconds=None,video_extraction_measured=False,
        same_canonical_archive_head=True,modes=results,orders_enabled=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--count',type=int,default=100);args=parser.parse_args()
    if not 1<=args.count<=10000:parser.error('count must be 1..10000')
    print(json.dumps(run(args.count),indent=2))
