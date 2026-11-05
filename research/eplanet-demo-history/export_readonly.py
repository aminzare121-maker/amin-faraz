"""PR27 hardened DEMO adaptation. Local history only; no account credentials/output.

Reuses PR27 SDK range-read/CSV/hash workflow. Exact already-running terminal;
half-open closed bars; immutable chunks, resume, mode checks, bounded tick windows.
"""
import argparse,csv,hashlib,json,math,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
EXE=Path('C:/Users/Pixel/AppData/Roaming/ePlanet MetaTrader 5 Terminal/terminal64.exe')
SYMBOL='XAUUSD.st'
_bound_identity=None  # transient only; never serialized or printed

def utc(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def hashfile(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,path)
def pids():
    command="Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq '"+str(EXE)+"'} | Select-Object -ExpandProperty Id"
    p=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,check=True)
    return [int(v) for v in p.stdout.split()]

def check(mt5):
    global _bound_identity
    t,a=mt5.terminal_info(),mt5.account_info()
    if not t or not a or not t.connected:raise RuntimeError('TERMINAL_DISCONNECTED')
    if a.trade_mode!=mt5.ACCOUNT_TRADE_MODE_DEMO:raise RuntimeError('EXPECTED_DEMO_ABORT_NO_LOGIN')
    if 'eplanet' not in str(a.server).lower() or Path(t.path).resolve()!=EXE.parent.resolve():raise RuntimeError('BROKER_OR_TERMINAL_MISMATCH')
    identity=(a.login,a.server)
    if _bound_identity is None:_bound_identity=identity
    elif identity!=_bound_identity:raise RuntimeError('ACCOUNT_CHANGED_DURING_READ')
    s=mt5.symbol_info(SYMBOL)
    if not s or not s.visible:raise RuntimeError('SYMBOL_NOT_ALREADY_VISIBLE')
    return s

def bar_qa(rows,start,end):
    invalid=duplicates=out_of_order=outside=0;previous=None;gaps=[];seen=set()
    for x in rows:
        t=int(x['time']);prices=[float(x[k]) for k in ('open','high','low','close')]
        o,h,l,c=prices
        if not all(math.isfinite(p) and p>0 for p in prices) or not l<=min(o,c)<=max(o,c)<=h:invalid+=1
        if t%900 or t<start or t+900>end:outside+=1
        if t in seen:duplicates+=1
        if previous is not None:
            if t<previous:out_of_order+=1
            if t-previous>900:gaps.append({'from_utc':utc(previous+900),'to_utc':utc(t),'missing_slots':(t-previous)//900-1,'classification':'UNKNOWN_SESSION'})
        seen.add(t);previous=t
    return {'rows':len(rows),'invalid_ohlc':invalid,'duplicates':duplicates,'out_of_order':out_of_order,'outside_or_unclosed':outside,
            'first_utc':utc(int(rows[0]['time'])) if len(rows) else None,'last_open_utc':utc(int(rows[-1]['time'])) if len(rows) else None,
            'gaps':gaps,'structural_pass':bool(len(rows)) and not any((invalid,duplicates,out_of_order,outside)),
            'complete_session_coverage':'UNKNOWN','spread_cost_validated':False}

def tick_qa(rows,start,end):
    invalid=outside=order=identical=0;last=None;seen=set()
    for x in rows:
        t=int(x['time_msc']);bid=float(x['bid']);ask=float(x['ask'])
        if not all(math.isfinite(v) and v>0 for v in (bid,ask)) or ask<bid:invalid+=1
        if not start*1000<=t<end*1000:outside+=1
        if last is not None and t<last:order+=1
        key=(t,bid,ask,int(x['flags']))
        if key in seen:identical+=1
        seen.add(key);last=t
    return {'rows':len(rows),'invalid_bid_ask':invalid,'outside':outside,'out_of_order':order,'identical_quote_records':identical,
            'same_millisecond_records_retained':True,'structural_pass':bool(len(rows)) and not any((invalid,outside,order))}

def chunk(mt5,folder,manifest,kind,start,end):
    identity=f'{kind}-{start}-{end}'
    existing=manifest['chunks'].get(identity)
    if existing:
        for field in ('raw','csv'):
            if hashfile(folder/existing[field])!=existing[field+'_sha256']:raise RuntimeError('RESUME_HASH_MISMATCH')
        return existing,False
    check(mt5)
    raw_rows=(mt5.copy_rates_range(SYMBOL,mt5.TIMEFRAME_M15,datetime.fromtimestamp(start,timezone.utc),datetime.fromtimestamp(end-1,timezone.utc)) if kind=='M15' else
              mt5.copy_ticks_range(SYMBOL,datetime.fromtimestamp(start,timezone.utc),datetime.fromtimestamp(end-0.001,timezone.utc),mt5.COPY_TICKS_ALL))
    if raw_rows is None:raise RuntimeError('SDK_HISTORY_ERROR_'+str(mt5.last_error()[0]))
    check(mt5)
    if len(raw_rows)>100000:raise RuntimeError('CHUNK_LIMIT_EXCEEDED')
    # Exact received bytes retained before normalization; no raw overwrite.
    raw=folder/(identity+'.bin');csvpath=folder/(identity+'.csv')
    if raw.exists() or csvpath.exists():raise RuntimeError('UNCOMMITTED_CHUNK_REQUIRES_REVIEW')
    with raw.open('xb') as f:f.write(raw_rows.tobytes())
    # SDK can return boundary ticks; keep original bytes, restrict derivative by requested half-open range.
    rows=raw_rows[(raw_rows['time']>=start)&(raw_rows['time']+900<=end)] if kind=='M15' else raw_rows[(raw_rows['time_msc']>=start*1000)&(raw_rows['time_msc']<end*1000)]
    with csvpath.open('x',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(raw_rows.dtype.names)
        for row in rows:writer.writerow([v.item() for v in row])
    qa=bar_qa(rows,start,end) if kind=='M15' else tick_qa(rows,start,end)
    entry={'kind':kind,'start_utc':utc(start),'end_exclusive_utc':utc(end),'received_utc':datetime.now(timezone.utc).isoformat(),
           'mode':'DEMO','symbol':SYMBOL,'timezone':'UTC_SDK_NO_OFFSET_APPLIED','source':'Eplanet_MT5',
           'raw':raw.name,'raw_sha256':hashfile(raw),'csv':csvpath.name,'csv_sha256':hashfile(csvpath),
           'raw_dtype':raw_rows.dtype.descr,'raw_rows':len(raw_rows),'boundary_rows_excluded':len(raw_rows)-len(rows),'qa':qa}
    manifest['chunks'][identity]=entry;write_json(folder/'manifest.json',manifest);time.sleep(.3)
    return entry,True

def run(stage,folder):
    import MetaTrader5 as mt5
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    manifest_path=folder/'manifest.json'
    if manifest_path.exists():manifest=json.loads(manifest_path.read_text())
    else:
        end=int(time.time())//900*900
        manifest={'schema':1,'mode':'DEMO','end':end,'start':end-365*86400,'chunks':{},'licence_evidence':'EPLANET_TICKET_207852_1405-08-14_13:59:29','collector_sha256':hashfile(Path(__file__))}
    if manifest['mode']!='DEMO' or manifest['collector_sha256']!=hashfile(Path(__file__)):raise RuntimeError('MANIFEST_VERSION_MISMATCH')
    before=pids()
    if len(before)!=1:raise RuntimeError('EXACT_EXISTING_TERMINAL_REQUIRED')
    if not mt5.initialize(str(EXE),timeout=10000):raise RuntimeError('ATTACH_FAILED_'+str(mt5.last_error()[0]))
    started=time.monotonic();calls=0
    try:
        check(mt5)
        if pids()!=before:raise RuntimeError('TERMINAL_PROCESS_CHANGED')
        end=manifest['end'];sample_start=end-7*86400
        if stage=='year' and not manifest.get('sample_pass'):raise RuntimeError('SAMPLE_PASS_REQUIRED')
        start=sample_start if stage=='sample' else manifest['start']
        stop=end if stage=='sample' else sample_start
        days=1 if stage=='sample' else 28
        cursor=start
        while cursor<stop:
            next_end=min(cursor+days*86400,stop)
            entry,new=chunk(mt5,folder,manifest,'M15',cursor,next_end);calls+=int(new)
            # Empty session windows are retained but not individually required to trade.
            if entry['qa']['rows'] and not entry['qa']['structural_pass']:raise RuntimeError('BAR_QA_FAILED')
            cursor=next_end
        import numpy as np
        bars=[]
        for c in manifest['chunks'].values():
            if c['kind']=='M15':
                dtype=np.dtype([tuple(x) for x in c['raw_dtype']]);arr=np.frombuffer((folder/c['raw']).read_bytes(),dtype=dtype)
                a=int(datetime.fromisoformat(c['start_utc']).timestamp());b=int(datetime.fromisoformat(c['end_exclusive_utc']).timestamp())
                bars.append(arr[(arr['time']>=a)&(arr['time']+900<=b)])
        joined=np.sort(np.concatenate(bars),order='time');qa=bar_qa(joined,start if stage=='sample' else manifest['start'],end)
        boundary_ok=bool(len(joined)) and int(joined[0]['time'])-(start if stage=='sample' else manifest['start'])<=3*86400 and end-(int(joined[-1]['time'])+900)<=3*86400
        accepted=qa['structural_pass'] and boundary_ok and (stage!='sample' or qa['rows']>=200)
        manifest[stage+'_pass']=accepted
        write_json(manifest_path,manifest)
        if accepted:
            tick_start=end-(600 if stage=='sample' else 1800)
            for a in range(tick_start,end,300):
                _,new=chunk(mt5,folder,manifest,'TICK',a,min(a+300,end));calls+=int(new)
        summary={'stage':stage,'mode':'DEMO','sdk_version':mt5.__version__,'requested_from_utc':utc(start if stage=='sample' else manifest['start']),
                 'requested_end_exclusive_utc':utc(end),'qa':qa,'boundary_tolerance_pass':boundary_ok,'sample_or_year_structural_acceptance':accepted,
                 'not_full_completeness_certificate':True,'tick_chunks':[{'start':c['start_utc'],'end':c['end_exclusive_utc'],'qa':c['qa'],'sha256':c['raw_sha256']} for c in manifest['chunks'].values() if c['kind']=='TICK'],
                 'new_sdk_history_calls':calls,'elapsed_seconds':round(time.monotonic()-started,3),'same_terminal_process':pids()==before,
                 'orders_sent':0,'account_changed':False,'raw_uploaded':False,'missingness_note':'All gaps unclassified until official session/holiday calendar; leading/trailing absence also requires review',
                 'manifest_sha256':hashfile(manifest_path),'collector_sha256':hashfile(Path(__file__))}
        write_json(folder/(stage+'-qa.json'),summary)
        print(json.dumps({k:v for k,v in summary.items() if k not in ('qa','tick_chunks')},ensure_ascii=False))
        print(json.dumps({'rows':qa['rows'],'first':qa['first_utc'],'last':qa['last_open_utc'],'gaps':len(qa['gaps']),'tick_rows':sum(c['qa']['rows'] for c in summary['tick_chunks'])}))
        return accepted
    finally:mt5.shutdown()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=('sample','year'),required=True);p.add_argument('--output',required=True);a=p.parse_args()
    raise SystemExit(0 if run(a.stage,a.output) else 2)
