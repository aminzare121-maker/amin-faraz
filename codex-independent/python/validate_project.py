"""Repeatable offline validation; never calls MT5, compiler, or network."""
import datetime as dt,hashlib,json,subprocess,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def main():
    reports=BASE/'reports';reports.mkdir(exist_ok=True);results=[]
    for optimized in (False,True):
        prefix=[sys.executable]+(['-O'] if optimized else [])
        started=time.perf_counter()
        proc=subprocess.run(prefix+['-m','unittest','discover','-s',str(BASE/'tests'),'-v'],capture_output=True,text=True)
        name='optimized' if optimized else 'normal'
        (reports/f'tests-{name}.txt').write_text(proc.stdout+proc.stderr,encoding='utf-8')
        if proc.returncode:raise RuntimeError('TESTS_FAILED_'+name)
        bench=subprocess.run(prefix+[str(BASE/'tests/benchmark_archive.py'),'--count','100'],capture_output=True,text=True)
        if bench.returncode:raise RuntimeError('BENCHMARK_FAILED_'+name)
        data=json.loads(bench.stdout)
        results.append(dict(mode=name,tests_passed=True,elapsed_with_benchmark_seconds=time.perf_counter()-started,
            test_log=f'tests-{name}.txt',synthetic_archive_benchmark=data))
    source_files=sorted(p for folder in ('python','tests','mql5') for p in (BASE/folder).glob('*') if p.suffix in ('.py','.mq5','.ex5','.md','.ps1'))
    hashes={str(p.relative_to(BASE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    out=dict(schema='codex_independent_offline_validation_v1',checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        results=results,source_hashes=hashes,mt5_runtime_exercised_by_this_command=False,
        semantic_verified=False,orders_enabled=False,video_under180_measured=False)
    (reports/'offline-validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(normal_and_optimized_passed=True,source_files_hashed=len(hashes),orders_enabled=False)))
if __name__=='__main__':main()
