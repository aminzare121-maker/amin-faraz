"""Research only: M15 spread regime. No live orders. Input CSV stays private."""
import argparse,json,hashlib
import numpy as np,pandas as pd
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--csv',required=True);p.add_argument('--out',required=True);a=p.parse_args()
f=Path(a.csv);d=pd.read_csv(f).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['date']=pd.to_datetime(d.time,unit='s',utc=True).dt.strftime('%Y-%m-%d')
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.shift(1).rolling(32).median()
eff=(d.close-d.close.shift(16)).abs()/d.close.diff().abs().rolling(16).sum().clip(lower=.01)
pause=(d.high.rolling(3).max()-d.low.rolling(3).min())/(atr*3)
mid=(d.high.shift(1).rolling(16).max()+d.low.shift(1).rolling(16).min())/2
side=np.where((eff>.42)&(pause<1.1)&(d.close>mid)&(d.close>d.close.shift(16)),1,np.where((eff>.42)&(pause<1.1)&(d.close<mid)&(d.close<d.close.shift(16)),-1,0))
upper=d.high-np.maximum(d.open,d.close);lower=np.minimum(d.open,d.close)-d.low
adverse=np.where(side==1,upper,lower)/tr.clip(lower=.01)
split=int(len(d)*.6);res={}
for segment,start,end in [('train',40,split),('holdout',split,len(d))]:
 res[segment]={}
 for variant in ['all','close_0p6','close_0p8']:
  equity=peak=1000.;dd=gross=fees=0.;daily={};n=opp=excluded=blocked=wins=0;last=-1
  for i in range(start,min(end-25,len(d)-25)):
   if side[i]==0 or not np.isfinite(atr.iloc[i]):continue
   opp+=1
   # Next-open displacement is known when the order would be placed.
   rng=max(float(d.high.iloc[i]-d.low.iloc[i]),.01)
   clv=(float(d.close.iloc[i]-d.low.iloc[i])/rng if side[i]==1 else float(d.high.iloc[i]-d.close.iloc[i])/rng)
   if variant=='close_0p6' and clv<.6:excluded+=1;continue
   if variant=='close_0p8' and clv<.8:excluded+=1;continue
   if adverse[i]>=.45:excluded+=1;continue
   if i<=last:continue
   date=d.date.iloc[i+1]
   s=int(side[i]);entry=float(d.open.iloc[i+1]);dist=float(np.clip(atr.iloc[i]*1.5,3,20));stop=entry-s*dist;target=entry+s*dist*1.8
   horizon=12;ex=float(d.close.iloc[i+horizon]);jexit=i+horizon
   for j in range(i+1,i+horizon+1):
    if (d.low.iloc[j]<=stop if s==1 else d.high.iloc[j]>=stop):ex=stop;jexit=j;break
    if (d.high.iloc[j]>=target if s==1 else d.low.iloc[j]<=target):ex=target;jexit=j;break
    if j==i+3:
     mfe=max(s*(float(d.high.iloc[k])-entry) if s==1 else s*(float(d.low.iloc[k])-entry) for k in range(i+1,j+1))
     if mfe<.25*dist:ex=float(d.close.iloc[j]);jexit=j;break
   lot=min(.1,np.floor(min(10,equity*.01)/(dist*100)*100)/100)
   if lot<.01:blocked+=1;continue
   pnl=s*(ex-entry)*100*lot;fee=87*lot;net=pnl-fee
   gross+=pnl;fees+=fee;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);n+=1;wins+=net>0;daily[date]=daily.get(date,0)+net;last=jexit
  res[segment][variant]=dict(opportunities=opp,excluded=excluded,trades=n,blocked=blocked,wins=wins,gross=round(gross,2),costs=round(fees,2),net=round(gross-fees,2),max_closed_drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in daily.values()),trading_days=d.iloc[start:end].date.nunique(),active_days=len(daily))
out=dict(hypothesis='Directional close location at completed signal candle',sha256=hashlib.sha256(f.read_bytes()).hexdigest(),candles=len(d),split=split,assumptions=dict(capital=1000,roundtrip_cost_per_lot=87,contract_oz_per_lot=100,risk_cap_usd=10,lot_min=.01,lot_max=.1,stop_first_intrabar=True,caveat='OHLC; estimated costs; no real tick sequence'),results=res)
Path(a.out).write_text(json.dumps(out,indent=2,ensure_ascii=False,default=int));print(json.dumps(out,indent=2,default=int))
