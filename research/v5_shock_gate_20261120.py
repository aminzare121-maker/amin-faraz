"""Reproducible OHLC-only research; NEVER places orders."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
p=argparse.ArgumentParser();p.add_argument('--csv',required=True);p.add_argument('--out',required=True);a=p.parse_args()
f=Path(a.csv);d=pd.read_csv(f).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True);d['date']=d.dt.dt.strftime('%Y-%m-%d')
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.shift(1).rolling(32).median();movement=d.close.diff().abs()
eff=(d.close-d.close.shift(16)).abs()/movement.rolling(16).sum().clip(lower=.01)
pause=(d.high.rolling(3).max()-d.low.rolling(3).min())/(atr*3)
mid=(d.high.shift(1).rolling(16).max()+d.low.shift(1).rolling(16).min())/2
side=np.where((eff>.42)&(pause<1.1)&(d.close>mid)&(d.close>d.close.shift(16)),1,np.where((eff>.42)&(pause<1.1)&(d.close<mid)&(d.close<d.close.shift(16)),-1,0))
split=int(len(d)*.6);res={}
for segment,start,end in [('train',40,split),('holdout',split,len(d))]:
 res[segment]={}
 for variant in ['all','shock_gate','shock_gate_guard']:
  equity=peak=1000.;dd=gross=fees=0.;daily={};n=opp=blocked=0;last=-1;win=0
  for i in range(start,min(end-13,len(d)-13)):
   if side[i]==0 or not np.isfinite(atr.iloc[i]):continue
   if variant!='all' and float(tr.iloc[i])>2.0*float(atr.iloc[i]):continue
   opp+=1
   if i<=last:continue
   date=d.date.iloc[i+1]
   if variant.endswith('guard') and daily.get(date,0)<=-15:blocked+=1;continue
   s=int(side[i]);entry=float(d.open.iloc[i+1]);dist=float(np.clip(atr.iloc[i]*1.5,3,20));stop=entry-s*dist;target=entry+s*dist*1.8
   ex=float(d.close.iloc[i+12]);jexit=i+12
   for j in range(i+1,i+13):
    if (d.low.iloc[j]<=stop if s==1 else d.high.iloc[j]>=stop):ex=stop;jexit=j;break
    if (d.high.iloc[j]>=target if s==1 else d.low.iloc[j]<=target):ex=target;jexit=j;break
   lot=min(.1,np.floor(min(10,equity*.01)/(dist*100)*100)/100)
   if lot<.01:blocked+=1;continue
   pnl=s*(ex-entry)*100*lot;fee=87*lot;net=pnl-fee
   gross+=pnl;fees+=fee;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);n+=1;win+=net>0;daily[date]=daily.get(date,0)+net;last=jexit
  res[segment][variant]=dict(opportunities=opp,trades=n,blocked=blocked,wins=win,gross=round(gross,2),costs=round(fees,2),net=round(gross-fees,2),max_closed_drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in daily.values()),trading_days=d.iloc[start:end].date.nunique(),active_days=len(daily))
output=dict(hypothesis='Exclude entries after candle range exceeds twice trailing median true range',sha256=hashlib.sha256(f.read_bytes()).hexdigest(),candles=len(d),split=split,assumptions={'capital':1000,'roundtrip_cost_per_lot':87,'contract_oz_per_lot':100,'risk_per_trade_cap_usd':10,'variable_lot_min':.01,'variable_lot_max':.1,'max_hold_bars':12,'stop_first_intrabar':True,'shock_threshold_range_to_median_tr':2.0,'guard_daily_loss_usd':15,'caveat':'OHLC approximation, no tick-level execution or verified live spread'},results=res)
Path(a.out).write_text(json.dumps(output,indent=2,ensure_ascii=False,default=int));print(json.dumps(output,indent=2,default=int))
