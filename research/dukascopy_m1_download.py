#!/usr/bin/env python3
"""Download Dukascopy XAUUSD hourly tick BI5 and aggregate M1 CSV. Research only."""
import argparse,csv,datetime as dt,lzma,struct,time,urllib.request,urllib.error
from pathlib import Path
UTC=dt.timezone.utc
def run(start,end,out):
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    rows=[];fail=[]
    hour=start
    while hour<end:
        url=f"https://datafeed.dukascopy.com/datafeed/XAUUSD/{hour.year}/{hour.month-1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=25) as r: raw=r.read()
            payload=lzma.decompress(raw)
            if len(payload)%20:raise ValueError("BI5 record length mismatch")
            for offset in range(0,len(payload),20):
                ms,ask,bid,askvol,bidvol=struct.unpack(">IIIff",payload[offset:offset+20])
                if ask<=0 or bid<=0 or ask<bid:continue
                ts=hour+dt.timedelta(milliseconds=ms)
                rows.append((ts,bid,ask))
        except Exception as e:fail.append((hour.isoformat(),str(e)[:180]))
        hour+=dt.timedelta(hours=1)
        time.sleep(.1)
    if not rows:raise RuntimeError("No tick data downloaded: "+repr(fail[:4]))
    rows.sort()
    # Dukascopy XAUUSD prices use 1/1000 scaling; raw integer prices should be validated.
    median=sorted(x[1] for x in rows)[len(rows)//2]
    scale=1000 if median>100000 else (100 if median>10000 else 1)
    grouped={}
    for ts,bid,ask in rows:
        minute=ts.replace(second=0,microsecond=0)
        price=bid/scale
        x=grouped.setdefault(minute,[price,price,price,price,0,0])
        x[1]=max(x[1],price);x[2]=min(x[2],price);x[3]=price;x[4]+=1;x[5]+=(ask-bid)/scale
    with out.open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["time_utc","open","high","low","close","ticks","mean_spread"])
        for k,x in sorted(grouped.items()):w.writerow([k.isoformat(),*x[:5],round(x[5]/x[4],5)])
    print({"ticks":len(rows),"m1_candles":len(grouped),"hours_failed":len(fail),"sample_failures":fail[:5],"price_scale":scale,"output":str(out)})
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",default="2026-11-02");p.add_argument("--end",default="2026-11-05");p.add_argument("--out",default="research/data/dukascopy_xauusd_m1.csv");a=p.parse_args()
    run(dt.datetime.fromisoformat(a.start).replace(tzinfo=UTC),dt.datetime.fromisoformat(a.end).replace(tzinfo=UTC),a.out)
