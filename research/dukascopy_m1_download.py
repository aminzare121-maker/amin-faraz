#!/usr/bin/env python3
"""Research-only Dukascopy XAUUSD BI5 downloader with retry and explicit coverage audit."""
import argparse,csv,datetime as dt,json,lzma,struct,time,urllib.request,urllib.error
from pathlib import Path
UTC=dt.timezone.utc
def run(start,end,out,retries=2,timeout=8):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    rows=[];fail=[];successful=[]
    hour=start
    while hour<end:
        url=f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{hour.year}/{hour.month-1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"
        error=None
        for attempt in range(retries):
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*"})
                with urllib.request.urlopen(req,timeout=timeout) as r: raw=r.read()
                payload=lzma.decompress(raw)
                if len(payload)%20: raise ValueError("BI5 record length mismatch")
                hourrows=[]
                for offset in range(0,len(payload),20):
                    ms,ask,bid,_,_=struct.unpack_from(">IIIff",payload,offset)
                    if ms>=3600000 or not(ask>=bid>0):continue
                    hourrows.append((hour+dt.timedelta(milliseconds=ms),bid,ask))
                if not hourrows:raise ValueError("no valid ticks")
                rows.extend(hourrows);successful.append(hour.isoformat());error=None;break
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError,lzma.LZMAError,ValueError) as e:
                error=f"{type(e).__name__}: {e}"
                if isinstance(e,urllib.error.HTTPError) and e.code in (400,401,403,404):break
                if attempt+1<retries:time.sleep(1+attempt)
        if error:fail.append({"hour":hour.isoformat(),"error":error})
        hour+=dt.timedelta(hours=1)
    expected=int((end-start).total_seconds()/3600)
    grouped={}
    if rows:
        rows.sort()
        median=sorted(x[1] for x in rows)[len(rows)//2]
        scale=1000 if median>100000 else (100 if median>10000 else 1)
        for ts,bid,ask in rows:
            minute=ts.replace(second=0,microsecond=0)
            price=bid/scale
            x=grouped.setdefault(minute,[price,price,price,price,0,0])
            x[1]=max(x[1],price);x[2]=min(x[2],price);x[3]=price;x[4]+=1;x[5]+=(ask-bid)/scale
        with out.open("w",newline="") as f:
            w=csv.writer(f);w.writerow(["time_utc","open","high","low","close","ticks","mean_spread"])
            for k,x in sorted(grouped.items()):w.writerow([k.isoformat(),*x[:5],round(x[5]/x[4],5)])
    report={"requested_hours":expected,"successful_hours":len(successful),"failed_hours":len(fail),"m1_candles":len(grouped),"ticks":len(rows),"failures":fail,"complete":not fail and len(successful)==expected}
    report_path=out.with_suffix(".coverage.json")
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="failures"},indent=2),flush=True)
    if fail:print("First failures:",fail[:8],flush=True)
    if not report["complete"]:raise SystemExit("INCOMPLETE DATA: coverage report written; refusing success")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",default="2026-11-03");p.add_argument("--end",default="2026-11-04");p.add_argument("--out",default="research/data/dukascopy_xauusd_m1.csv");p.add_argument("--retries",type=int,default=2);a=p.parse_args()
    run(dt.datetime.fromisoformat(a.start).replace(tzinfo=UTC),dt.datetime.fromisoformat(a.end).replace(tzinfo=UTC),a.out,a.retries)
