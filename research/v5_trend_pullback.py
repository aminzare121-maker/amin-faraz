# Reproducible research, private CSV must be provided locally.
# Dependencies: pandas, numpy. Usage: python research/v5_trend_pullback.py PATH_TO_EPLANET_CSV
import sys, json
import pandas as pd
import numpy as np
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["dt"]=pd.to_datetime(d.time,unit="s",utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d["atr"]=tr.rolling(20).mean().shift(1)
d["ema20"]=d.close.ewm(span=20,adjust=False).mean().shift(1)
d["ema80"]=d.close.ewm(span=80,adjust=False).mean().shift(1)
d["volratio"]=(d.high-d.low).shift(1)/d.atr
cut=pd.Timestamp("2026-06-15",tz="UTC")
def test(guard):
    balances={"train":1000.,"test":1000.}; trades=[]; opp={"train":0,"test":0};blocked={"train":0,"test":0};busy=-1
    for i in range(85,len(d)-9):
        if i<=busy:continue
        r=d.iloc[i];a=r["atr"]
        if not np.isfinite(a) or a<=0:continue
        side=1 if r.ema20>r.ema80 and r.close>r.ema80 else -1 if r.ema20<r.ema80 and r.close<r.ema80 else 0
        if not side or not(side*(d.close.iloc[i-2]-d.open.iloc[i-2])<0 and side*(d.close.iloc[i-1]-d.open.iloc[i-1])<0 and side*(r.close-r.open)>0):continue
        if abs(r.close-r.ema20)>1.2*a:continue
        s="train" if r["dt"]<cut else "test";opp[s]+=1
        if guard and (r.spread>35 or r.volratio>1.5 or r["dt"].hour in [21,22,23]):blocked[s]+=1;continue
        entry=d.open.iloc[i+1];distance=max(1.2*a,2.)
        lot=np.floor(min(.10,balances[s]*.01/(distance*100))/.01)*.01
        if lot<.01:blocked[s]+=1;continue
        stop=entry-side*distance;target=entry+side*2*distance;price=d.close.iloc[i+8];end=i+8
        for j in range(i+1,i+9):
            lo,hi=d.low.iloc[j],d.high.iloc[j]
            if (lo<=stop if side==1 else hi>=stop):price=stop;end=j;break
            if (hi>=target if side==1 else lo<=target):price=target;end=j;break
        gross=side*(price-entry)*100*lot
        cost=((r.spread+d.spread.iloc[end])/2)*.01*100*lot+.20*100*lot+7*lot
        net=gross-cost;balances[s]+=net;busy=end
        trades.append(dict(segment=s,time=str(r["dt"]),lots=float(lot),gross=float(gross),cost=float(cost),net=float(net)))
    result={}
    for s in ["train","test"]:
        t=[x for x in trades if x["segment"]==s];v=np.array([x["net"] for x in t]);equity=np.r_[1000,1000+np.cumsum(v)]
        days={}
        for x in t:days[x["time"][:10]]=days.get(x["time"][:10],0)+x["net"]
        result[s]=dict(opportunities=opp[s],blocked=blocked[s],trades=len(t),gross_profit=round(sum(max(0,x["gross"]) for x in t),2),gross_loss=round(sum(min(0,x["gross"]) for x in t),2),costs=round(sum(x["cost"] for x in t),2),net=round(float(v.sum()),2),max_closed_drawdown=round(float(max(np.maximum.accumulate(equity)-equity)),2),days_over_50=sum(x>=50 for x in days.values()),active_days=len(days))
    return result
print(json.dumps({"alpha":test(False),"risk_guard":test(True)},indent=2))
