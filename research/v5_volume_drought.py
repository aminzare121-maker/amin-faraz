"""Eplanet M15 low-tick-volume drought experiment. Private CSV supplied locally."""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['ema']=d.close.ewm(span=48,adjust=False).mean()
d['atr']=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1).rolling(20).mean()
d['vol_med']=d.tick_volume.shift(1).rolling(40).median()
low=d.tick_volume<d.vol_med*.65
prev=low.shift(1).fillna(False)&low.shift(2).fillna(False)
up=prev&(d.close>d.high.shift(1))&(d.close>d.ema)&(d.ema>d.ema.shift(8))
down=prev&(d.close<d.low.shift(1))&(d.close<d.ema)&(d.ema<d.ema.shift(8))
signals=np.where(up,1,np.where(down,-1,0))
cut=pd.Timestamp('2026-07-21',tz='UTC');out={}
for direction in ['continuation','reversal']:
 trades=[];last=-1;equity=1000
 for i in np.flatnonzero(signals):
  if i<50 or i+5>=len(d) or i<=last:continue
  if d.time.iloc[i+1]-d.time.iloc[i]!=900 or d.time.iloc[i+5]-d.time.iloc[i+1]!=3600:continue
  if not np.isfinite(d.atr.iloc[i]) or d.atr.iloc[i]<=0:continue
  side=signals[i]*(1 if direction=='continuation' else -1)
  entry=d.open.iloc[i+1];exit=d.close.iloc[i+4];dist=max(3.,float(d.atr.iloc[i])*1.5)
  lots=np.floor(equity*.01/(dist*100)*100)/100
  if lots<.01:continue
  lots=min(lots,1.);stop=entry-side*dist
  for j in range(i+1,i+5):
   if (side==1 and d.low.iloc[j]<=stop) or (side==-1 and d.high.iloc[j]>=stop):
    exit=stop;break
  gross=(exit-entry)*side*100*lots
  cost=(.26+.6)*100*lots+7*lots
  net=gross-cost;equity+=net
  trades.append(dict(date=str(d.dt.iloc[i].date()),oos=bool(d.dt.iloc[i]>=cut),net=round(net,4),gross=round(gross,4),cost=round(cost,4)))
  last=i+4
 for part in ['train','oos']:
  t=[x for x in trades if x['oos']==(part=='oos')]
  vals=np.array([x['net'] for x in t]);cum=1000+np.cumsum(vals)
  peaks=np.maximum.accumulate(np.r_[1000,cum])
  dd=float(np.max((peaks[1:]-cum)/peaks[1:])) if len(t) else 0
  daily={day:sum(x['net'] for x in t if x['date']==day) for day in set(x['date'] for x in t)}
  out[direction+'_'+part]=dict(trades=int(len(t)),gross_wins=round(sum(x['gross'] for x in t if x['gross']>0),2),gross_losses=round(sum(x['gross'] for x in t if x['gross']<0),2),cost=round(sum(x['cost'] for x in t),2),net=round(float(sum(vals)),2),max_drawdown_pct=round(dd*100,2),days_traded=int(len(daily)),days_net_ge_50=int(sum(v>=50 for v in daily.values())))
print(json.dumps(out,indent=2))
