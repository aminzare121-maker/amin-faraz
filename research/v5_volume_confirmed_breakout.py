"""Volume-confirmed Donchian breakout, Eplanet M15. Research only; never sends orders."""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['atr']=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean().shift(1)
d['hi']=d.high.shift(1).rolling(24).max();d['lo']=d.low.shift(1).rolling(24).min()
d['vol']=d.tick_volume.shift(1).rolling(24).median();d['spr']=d.spread.shift(1).rolling(24).median()
cut=pd.Timestamp('2026-06-15',tz='UTC');result={}
for guarded in (False,True):
 equity=1000.;busy=-1;trades=[]
 for i in range(30,len(d)-9):
  a=d.iloc[i];atr=a.atr
  if not np.isfinite(atr) or atr<=0:continue
  side=1 if a.close>a.hi+.1*atr else (-1 if a.close<a.lo-.1*atr else 0)
  if not side or a.tick_volume<1.35*a.vol or i<=busy:continue
  if guarded and (a.high-a.low>2.5*atr or a.spread>max(35,1.3*a.spr) or a['dt'].hour in (21,22,23)):continue
  entry=float(d.open.iloc[i+1]);stop=entry-side*1.4*atr;target=entry+side*2.2*atr
  lots=min(.15,np.floor((max(0,equity)*.0075/(1.4*atr*100))*100)/100)
  if lots<.01:continue
  out=float(d.close.iloc[i+8]);busy=i+8
  for j in range(i+1,i+9):
   b=d.iloc[j];hs=b.low<=stop if side==1 else b.high>=stop;ht=b.high>=target if side==1 else b.low<=target
   if hs or ht:out=stop if hs else target;busy=j;break
  cost=lots*100*(.60+float(a.spread)*.01)
  gross=side*(out-entry)*lots*100;net=gross-cost;equity+=net
  trades.append((a['dt'],gross,cost,net))
 result['guard' if guarded else 'base']={}
 for split in ('train','test'):
  t=[x for x in trades if (x[0]>=cut)==(split=='test')]
  v=np.array([x[3] for x in t]);curve=np.r_[0,v.cumsum()]
  days={}
  for dt,g,c,n in t:days[str(dt.date())]=days.get(str(dt.date()),0)+n
  result['guard' if guarded else 'base'][split]=dict(trades=len(t),gross_profit=round(sum(max(0,x[1]) for x in t),2),gross_loss=round(sum(min(0,x[1]) for x in t),2),cost=round(sum(x[2] for x in t),2),net=round(v.sum(),2),max_closed_drawdown=round(max(np.maximum.accumulate(curve)-curve),2),days_ge_50=sum(n>=50 for n in days.values()),trading_days=len(days))
print(json.dumps(result,indent=2))
