"""Reproducible Eplanet M15 liquidity sweep study. Usage: python research/v5_liquidity_sweep.py PRIVATE_CSV_PATH"""
import sys,json,hashlib
import numpy as np
import pandas as pd
from pathlib import Path
p=Path(sys.argv[1])
d=pd.read_csv(p).sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["dt"]=pd.to_datetime(d.time,unit="s",utc=True)
prev=d.close.shift(1)
tr=pd.concat([d.high-d.low,(d.high-prev).abs(),(d.low-prev).abs()],axis=1).max(axis=1)
d["atr"]=tr.shift(1).rolling(20).mean()
d["hi20"]=d.high.shift(1).rolling(20).max()
d["lo20"]=d.low.shift(1).rolling(20).min()
up=(d.high>d.hi20+.12*d.atr)&(d.close<d.hi20)&((d.high-d.close)>.45*(d.high-d.low))
down=(d.low<d.lo20-.12*d.atr)&(d.close>d.lo20)&((d.close-d.low)>.45*(d.high-d.low))
d["side"]=np.select([up,down],[-1,1],0)
cut=pd.Timestamp("2026-06-15",tz="UTC")
end=pd.Timestamp("2026-11-06",tz="UTC")
def run(part,guard=False):
    equity=peak=1000.
    dd=gp=gl=cost=0.
    trades=[]
    opp=blocked=0
    i=25
    while i<len(d)-9:
        row=d.iloc[i]
        day=row["dt"]
        if not ((part=="train" and day<cut) or (part=="oos" and cut<=day<end)):
            i+=1;continue
        side=int(row["side"])
        if not side:
            i+=1;continue
        opp+=1
        nxt=d.iloc[i+1]
        atr=float(row["atr"])
        if not np.isfinite(atr) or atr<=0 or nxt["time"]-row["time"]!=900:
            blocked+=1;i+=1;continue
        if guard and ((row.high-row.low)>2.5*atr or row.spread>35 or row.tick_volume>2.2*d.tick_volume.iloc[i-20:i].median()):
            i+=1;continue
        entry=float(nxt.open)
        stop=entry-side*1.1*atr
        target=entry+side*1.5*atr
        lots=min(.10,np.floor(equity*.01/(1.1*atr*100)*100)/100)
        if lots<.01:
            blocked+=1;i+=1;continue
        ex=float(d.iloc[i+8].close)
        last=i+8
        for j in range(i+1,i+9):
            bar=d.iloc[j]
            sl=bar.low<=stop if side==1 else bar.high>=stop
            tp=bar.high>=target if side==1 else bar.low<=target
            if sl or tp:
                ex=stop if sl else target
                last=j;break
        gross=side*(ex-entry)*100*lots
        fee=(float(row.spread)*.01+.30)*100*lots
        net=gross-fee
        equity+=net
        peak=max(peak,equity)
        dd=max(dd,peak-equity)
        gp+=max(0,gross);gl+=min(0,gross);cost+=fee
        trades.append({"time":str(nxt["dt"]),"lot":round(lots,2),"gross":round(gross,4),"cost":round(fee,4),"net":round(net,4)})
        i=last+1
    daily={}
    for t in trades:
        key=t["time"][:10]
        daily[key]=daily.get(key,0)+t["net"]
    return {"opportunities":opp,"trades":len(trades),"blocked":blocked,"gross_profit":round(gp,2),"gross_loss":round(gl,2),"cost":round(cost,2),"net":round(equity-1000,2),"max_closed_drawdown":round(dd,2),"days_ge_50":sum(x>=50 for x in daily.values()),"days_traded":len(daily),"ledger":trades}
result={part:{name:run(part,guard) for name,guard in (("base",False),("guard",True))} for part in ("train","oos")}
result["meta"]={"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"rows":len(d),"decision":"REJECT; no demo orders","cost_model":"spread points * $0.01/oz + $0.30/oz roundtrip; 100oz/lot assumed"}
print(json.dumps(result,indent=2,default=lambda x:int(x) if isinstance(x,np.integer) else float(x)))
