"""V5 wick rejection research. Run with pandas/numpy and private Eplanet CSV locally."""
import pandas as pd
import numpy as np
import json
from pathlib import Path

def evaluate(df, start, end, ratio, mode="fade", guard=False):
    equity=peak=1000.
    gross=cost=drawdown=0.
    busy=-1
    opportunities=0
    trades=[]
    daily={}
    for i in range(max(25,start),end-5):
        a=df.iloc[i]
        width=a.high-a.low
        if not np.isfinite(a.atr) or a.atr<=0 or not .6*a.atr<=width<=3*a.atr:
            continue
        if max(a.upper,a.lower)<ratio*width or abs(a.upper-a.lower)<.25*width:
            continue
        if any(np.diff(df.time.iloc[i:i+5].to_numpy())!=900):
            continue
        opportunities+=1
        if i<=busy or (guard and (a.spread>30 or width>1.8*a.atr)):
            continue
        direction=(-1 if a.upper>a.lower else 1)*(1 if mode=="fade" else -1)
        entry=float(df.open.iloc[i+1])
        risk=max(2.,.85*a.atr)
        lots=min(.15,np.floor((equity*.01)/(risk*100)*100)/100)
        if lots<.01:
            continue
        sl=entry-direction*risk
        tp=entry+direction*1.4*risk
        price=float(df.close.iloc[i+4])
        last=i+4
        for j in range(i+1,i+5):
            b=df.iloc[j]
            stop=b.low<=sl if direction==1 else b.high>=sl
            target=b.high>=tp if direction==1 else b.low<=tp
            if stop or target:
                price=sl if stop else tp
                last=j
                break
        pnl=(price-entry)*direction*100*lots
        fee=100*lots*(float(df.spread.iloc[i+1])*.01+.30)+7*lots
        net=pnl-fee
        gross+=pnl
        cost+=fee
        equity+=net
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
        busy=last
        day=str(df.dt.iloc[last].date())
        daily[day]=daily.get(day,0)+net
        trades.append(dict(bar=i,lots=lots,net=round(net,3)))
    return dict(opportunities=opportunities,trades=len(trades),gross=round(gross,2),costs=round(cost,2),net=round(gross-cost,2),max_closed_drawdown=round(drawdown,2),days_ge_50=sum(v>=50 for v in daily.values()),ledger=trades)

def main(path):
    df=pd.read_csv(path).sort_values("time").drop_duplicates("time").reset_index(drop=True)
    df["dt"]=pd.to_datetime(df.time,unit="s",utc=True)
    tr=pd.concat([df.high-df.low,(df.high-df.close.shift()).abs(),(df.low-df.close.shift()).abs()],axis=1).max(axis=1)
    df["atr"]=tr.rolling(20).mean().shift(1)
    df["upper"]=df.high-df[["open","close"]].max(axis=1)
    df["lower"]=df[["open","close"]].min(axis=1)-df.low
    cut=int(len(df)*.6)
    training={(mode,r):evaluate(df,0,cut,r,mode) for mode in ("fade","continue") for r in (.55,.65,.75)}
    selected=max(training,key=lambda k:training[k]["net"])
    result=dict(rows=len(df),selected=selected,train_net=training[selected]["net"],holdout=evaluate(df,cut,len(df),selected[1],selected[0]),guard=evaluate(df,cut,len(df),selected[1],selected[0],True))
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    import sys
    main(Path(sys.argv[1]))
