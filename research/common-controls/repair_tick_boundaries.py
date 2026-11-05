"""Read six missing boundary seconds only; preserve original data, append separate receipts."""
import sys,json,csv,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'eplanet-history-revision'))
import export_readonly as guard
import MetaTrader5 as mt5
root=Path(__file__).resolve().parent
source=Path('C:/Users/Pixel/Documents/PRIVATE_EPLANET_HISTORY_20261105_DEMO')
dest=source/'boundary-repair';dest.mkdir(exist_ok=True)
manifest=json.loads((source/'manifest.json').read_text())
before=guard.pids()
if len(before)!=1:raise RuntimeError('EXACT_EXISTING_TERMINAL_REQUIRED')
if not mt5.initialize(str(guard.EXE),timeout=10000):raise RuntimeError('ATTACH_FAILED')
entries=[]
try:
    guard.check(mt5)
    if guard.pids()!=before:raise RuntimeError('PROCESS_CHANGED')
    for e in manifest['chunks'].values():
        if e['kind']!='TICK':continue
        end=int(datetime.fromisoformat(e['end_exclusive_utc']).timestamp());start=end-1
        path=dest/f'{start}-{end}.csv'
        if path.exists():raise RuntimeError('ALREADY_REPAIRED_DO_NOT_RERUN')
        guard.check(mt5)
        arr=mt5.copy_ticks_range(guard.SYMBOL,datetime.fromtimestamp(start,timezone.utc),datetime.fromtimestamp(end,timezone.utc),mt5.COPY_TICKS_ALL)
        if arr is None or len(arr)>2000:raise RuntimeError('BOUNDARY_READ_FAILED')
        guard.check(mt5)
        rawpath=path.with_suffix('.bin')
        with rawpath.open('xb') as f:f.write(arr.tobytes())
        rows=arr[(arr['time_msc']>=start*1000)&(arr['time_msc']<end*1000)]
        with path.open('x',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(arr.dtype.names)
            for r in rows:w.writerow([v.item() for v in r])
        entries.append({'start_raw_epoch':start,'end_raw_epoch':end,'rows':len(rows),'csv':path.name,
            'csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest()})
        time.sleep(.3)
    out={'sdk_history_calls':6,'requested_seconds':6,'mode':'DEMO','orders':0,'old_raw_modified':False,
        'entries':entries,'added_rows':sum(e['rows'] for e in entries),'same_existing_process':guard.pids()==before,
        'timestamp_basis':'BROKER_SERVER_LABEL_NOT_VERIFIED_UTC'}
    (dest/'receipt.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    (root/'tick-boundary-repair-sanitized.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(json.dumps(out))
finally:mt5.shutdown()
