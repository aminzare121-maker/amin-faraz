import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean();d['ema']=d.close.ewm(span=48,adjust=False).mean();d['slow']=d.close.ewm(span=192,adjust=False).mean()
slope=(d.ema-d.ema.shift(12))/d.atr
up=(d.ema>d.slow)&(slope>.45)&(d.low.shift(1)<d.ema.shift(1))&(d.close.shift(1)<d.ema.shift(1))&(d.close>d.ema)&(d.close>d.open)&(d.close>d.high.shift(1))
dn=(d.ema<d.slow)&(slope<-.45)&(d.high.shift(1)>d.ema.shift(1))&(d.close.shift(1)>d.ema.shift(1))&(d.close<d.ema)&(d.close<d.open)&(d.close<d.low.shift(1))
sig=np.where(up,1,np.where(dn,-1,0));cut=pd.Timestamp('2026-07-21',tz='UTC');out={}
for mode in ('trend','countertrend'):
 for part in ('train','oos'):
  equity=1000.;peak=1000.;maxdd=0.;trades=[];opp=0;last=-1
  for i in np.flatnonzero(sig):
   if i<220 or i+5>=len(d) or (d.dt.iloc[i]>=cut)!=(part=='oos'):continue
   opp+=1
   if i<=last or d.time.iloc[i+1]-d.time.iloc[i]!=900 or d.time.iloc[i+4]-d.time.iloc[i+1]!=2700:continue
   atr=float(d.atr.iloc[i]);side=int(sig[i])*(1 if mode=='trend' else -1);entry=float(d.open.iloc[i+1]);stopdist=max(2.5,1.25*atr);targetdist=1.6*stopdist
   lots=np.floor((equity*.01)/(stopdist*100)*100)/100
   if lots<.01:continue
   lots=min(1.,lots);stop=entry-side*stopdist;target=entry+side*targetdist;exit=float(d.close.iloc[i+4]);exitbar=i+4
   for j in range(i+1,i+5):
    lo=float(d.low.iloc[j]);hi=float(d.high.iloc[j]);hitstop=lo<=stop if side==1 else hi>=stop;hittarget=hi>=target if side==1 else lo<=target
    if hitstop or hittarget:exit=stop if hitstop else target;exitbar=j;break
   gross=(exit-entry)*side*100*lots;cost=(.26+.6)*100*lots+7*lots;net=gross-cost;equity+=net;peak=max(peak,equity);maxdd=max(maxdd,(peak-equity)/peak);last=exitbar
   trades.append((str(d.dt.iloc[i].date()),gross,cost,net))
  days={x[0] for x in trades}
  out[mode+'_'+part]=dict(opportunities=int(opp),trades=int(len(trades)),gross_wins=round(sum(x[1] for x in trades if x[1]>0),2),gross_losses=round(sum(x[1] for x in trades if x[1]<0),2),cost=round(sum(x[2] for x in trades),2),net=round(sum(x[3] for x in trades),2),max_drawdown_pct=round(maxdd*100,2),days_traded=int(len(days)),days_net_ge_50=int(sum(sum(x[3] for x in trades if x[0]==day)>=50 for day in days)))
print(json.dumps(out,indent=2))
