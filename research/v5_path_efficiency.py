# V5 research: directional path efficiency, M15, no live orders
# Input private CSV supplied locally: Eplanet_M15_20251105_20261105_merged.csv
import pandas as pd, numpy as np, json, hashlib, sys
from pathlib import Path
p=Path(sys.argv[1]); d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
c=d.close.to_numpy(); o=d.open.to_numpy(); t=d.time.to_numpy()
atr=pd.Series(d.high.to_numpy()-d.low.to_numpy()).rolling(32,min_periods=32).median().shift(1).to_numpy()
path=pd.Series(abs(np.diff(c,prepend=np.nan))).rolling(6,min_periods=6).sum().shift(1).to_numpy()
net=pd.Series(c).shift(1).to_numpy()-pd.Series(c).shift(7).to_numpy()
valid=(abs(net)/np.maximum(path,1e-9)>.82)&(abs(net)>1.4*atr)&np.isfinite(atr)
for j in range(1,7):
    valid &= (pd.Series(t).diff().shift(j-1).to_numpy()==900)
valid &= np.roll(t,-2)-t==1800
side=np.sign(net)
def run(start,end,gate):
    eq=1000.;peak=eq;dd=0.;tr=[];i=start
    while i<end-2:
        if valid[i] and (not gate or (1.3<=atr[i]<=10 and d.spread.iloc[i]<=26)):
            dist=max(2*atr[i],1.)
            lot=np.floor(min(.10,max(.01,eq*.005/(100*dist)))*100)/100
            if lot*100*dist>eq*.012:i+=1;continue
            gross=(o[i+2]-o[i])*side[i]*lot*100;cost=.86*lot*100
            eq+=gross-cost;peak=max(peak,eq);dd=max(dd,peak-eq)
            tr.append((int(t[i]),gross,cost,lot));i+=2
        else:i+=1
    days=len(pd.unique(pd.to_datetime(t[start:end],unit='s',utc=True).date))
    daily={}
    for stamp,gross,cost,lot in tr:
        day=str(pd.to_datetime(stamp,unit='s',utc=True).date());daily[day]=daily.get(day,0)+gross-cost
    return dict(trades=len(tr),gross=round(sum(x[1] for x in tr),2),cost=round(sum(x[2] for x in tr),2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),opportunity_days=len(daily),days_50=sum(x>=50 for x in daily.values()),calendar_days=days,average_per_day=round((eq-1000)/days,3),lot_min=min((x[3] for x in tr),default=None),lot_max=max((x[3] for x in tr),default=None))
cut=int(len(d)*.6)
r=dict(rows=len(d),split_index=cut,train=dict(signal=run(40,cut,False),risk_gate=run(40,cut,True)),out_of_sample=dict(signal=run(cut,len(d),False),risk_gate=run(cut,len(d),True)),sha256_data=hashlib.sha256(p.read_bytes()).hexdigest(),cost_assumption='0.86 USD/oz roundtrip, 100 oz/lot, hypothetical execution')
print(json.dumps(r,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
