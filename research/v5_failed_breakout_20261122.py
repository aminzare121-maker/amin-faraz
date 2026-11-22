import pandas as pd,numpy as np,json
p='Eplanet_M15_20251105_20261105_merged.csv'
d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True);d['day']=d.dt.dt.date
hi=d.high.shift(1).rolling(20).max();lo=d.low.shift(1).rolling(20).min()
atr=(pd.concat([(d.high-d.low),(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)).shift(1).rolling(20).mean()
side=np.where((d.high>hi+0.12*atr)&(d.close<hi)&(d.close>d.open),-1,np.where((d.low<lo-0.12*atr)&(d.close>lo)&(d.close<d.open),1,0))
split=int(len(d)*.60)
def run(guard=False):
 eq=1000.;peak=eq;dd=0;grosswin=grossloss=fees=0.;n=opp=0;daily={};i=30
 while i<len(d)-5:
  s=int(side[i]);a=float(atr.iloc[i])
  if s==0 or not np.isfinite(a) or a<=0:i+=1;continue
  if i<split:i+=1;continue
  opp+=1
  if guard and (d.high.iloc[i]-d.low.iloc[i])>1.6*a:i+=1;continue
  entry=float(d.open.iloc[i+1]);stopdist=max(1.1*a,2.0)
  lots=np.floor(min(.10,eq*.01/stopdist/100)/.01)*.01
  if lots<.01:i+=1;continue
  oz=lots*100;stop=entry-s*stopdist;target=entry+s*1.5*stopdist
  exitp=float(d.close.iloc[i+4]);jexit=i+4
  for j in range(i+1,i+5):
   h=float(d.high.iloc[j]);l=float(d.low.iloc[j])
   if (l<=stop if s==1 else h>=stop):exitp=stop;jexit=j;break
   if (h>=target if s==1 else l<=target):exitp=target;jexit=j;break
  pnl=s*(exitp-entry)*oz
  fee=oz*(.26+.30+.07);net=pnl-fee
  grosswin+=max(0,pnl);grossloss+=min(0,pnl);fees+=fee;eq+=net;n+=1
  day=str(d.day.iloc[i+1]);daily[day]=daily.get(day,0)+net
  peak=max(peak,eq);dd=max(dd,peak-eq);i=jexit+1
 return dict(opportunities=opp,trades=n,gross_profit=round(grosswin,2),gross_loss=round(grossloss,2),cost=round(fees,2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),days_ge_50=int(sum(x>=50 for x in daily.values())),active_days=len(daily),out_of_sample_start=str(d.dt.iloc[split]))
r={'hypothesis':'failed 20-bar range breakout mean reversion','base':run(False),'volatility_guard':run(True),'assumptions':'1% equity risk, 0.01 lot increments, 100 oz/lot, estimated spread+slippage+commission 0.63 USD/oz roundtrip; stop first on ambiguous candles; 60/40 chronological split'}
open('v5_failed_breakout_20261122.json','w').write(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
