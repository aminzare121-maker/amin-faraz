# Reproducible research: volume-weighted 32-bar reclaim, Eplanet M15
# Requires private CSV as positional argument; never commit market data.
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
p=(d.high+d.low+d.close)/3
v=d.tick_volume.clip(lower=1)
w=(p*v).rolling(32).sum()/v.rolling(32).sum()
a=(d.high-d.low).rolling(32).mean()
side=np.where((d.close>w)&(d.close.shift()<=w.shift())&(w>w.shift(4))&(d.close>d.open),1,np.where((d.close<w)&(d.close.shift()>=w.shift())&(w<w.shift(4))&(d.close<d.open),-1,0))
split=int(len(d)*.6)
trades=[]; equity=1000.; busy=-1
for i in range(40,len(d)-5):
    if i==split: equity=1000.
    if i<=busy or side[i]==0: continue
    direction=int(side[i]); entry=float(d.open[i+1]); risk=max(2.,min(12.,float(a[i])*1.2))
    lot=min(.10,max(.01,np.floor((equity*.005/(risk*100))*100)/100))
    stop=entry-direction*risk
    exit_price=float(d.close[i+4]); end=i+4
    for j in range(i+1,i+5):
        if (direction==1 and d.low[j]<=stop) or (direction==-1 and d.high[j]>=stop):
            exit_price=min(float(d.open[j]),stop) if direction==1 else max(float(d.open[j]),stop)
            end=j; break
    gross=direction*(exit_price-entry)*lot*100; cost=.4*lot*100
    net=gross-cost; equity+=net; busy=end
    trades.append(dict(i=i,time=int(d.time[i]),gross=float(gross),cost=float(cost),net=float(net),lot=float(lot)))
def summarize(ts):
    curve=np.r_[0,np.cumsum([t["net"] for t in ts])]
    return dict(trades=len(ts),gross=round(sum(t["gross"] for t in ts),2),cost=round(sum(t["cost"] for t in ts),2),net=round(sum(t["net"] for t in ts),2),drawdown=round(float(np.max(np.maximum.accumulate(curve)-curve)),2))
train=[t for t in trades if t["i"]<split]; test=[t for t in trades if t["i"]>=split]
daily={}; guarded=[]
for t in test:
    day=pd.to_datetime(t["time"],unit="s",utc=True).strftime("%Y-%m-%d")
    if daily.get(day,0)<=-15: continue
    guarded.append(t); daily[day]=daily.get(day,0)+t["net"]
print(json.dumps(dict(train=summarize(train),holdout=summarize(test),guard=summarize(guarded)),indent=2))
