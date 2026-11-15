"""Research-only anchored intraday VWAP proxy, no orders. Private CSV input."""
import pandas as pd, numpy as np, math, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
for c in ('time','open','high','low','close','tick_volume','spread'): d[c]=pd.to_numeric(d[c],errors='coerce')
date=pd.to_datetime(d.time,unit='s',utc=True).dt.date
p=(d.high+d.low+d.close)/3;w=d.tick_volume.clip(lower=1)
cw=w.groupby(date).cumsum();v=(w*p).groupby(date).cumsum()/cw
sigma=np.sqrt((w*(p-v)**2).groupby(date).cumsum()/cw)
z=(d.close-v)/sigma.replace(0,np.nan);prev=z.shift(1)
sig=np.where((prev>2)&(z<1.5)&(z>0),-1,np.where((prev< -2)&(z> -1.5)&(z<0),1,0))
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.shift(1).rolling(24).mean()
def run(start,end,factor,risk_filter):
 balance=peak=1000.;dd=0.;wins=losses=cost=0.;trades=opps=skips=0;days={};i=max(start,40)
 while i<end-6:
  s=int(sig[i])
  if not s or not np.isfinite(atr.iloc[i]):i+=1;continue
  opps+=1
  if risk_filter and d.high.iloc[i]-d.low.iloc[i]>1.3*atr.iloc[i]:skips+=1;i+=1;continue
  side=s*factor;k=i+1;raw=float(d.open.iloc[k]);spread=float(d.spread.iloc[k])*.01
  dist=max(3.,float(atr.iloc[i])*.9);lots=math.floor((balance*.01/(dist*100))*100)/100
  lots=min(lots,math.floor((balance*.5/(raw*100/200))*100)/100)
  if lots<.01:i+=1;continue
  entry=raw+side*(spread/2+.30);ex=None;jj=None
  for j in range(k,min(k+6,end)):
   hi=float(d.high.iloc[j]);lo=float(d.low.iloc[j])
   if (lo<=entry-dist if side==1 else hi>=entry+dist):ex=entry-side*dist;jj=j;break
   if (hi>=entry+1.5*dist if side==1 else lo<=entry-1.5*dist):ex=entry+side*1.5*dist;jj=j;break
  if ex is None:jj=min(k+5,end-1);ex=float(d.close.iloc[jj])
  pnl=side*(ex-entry)*lots*100-(.30*lots*100+7*lots)
  cost+=(.60+spread/2)*lots*100+7*lots
  wins+=max(0,pnl);losses+=min(0,pnl);balance+=pnl;peak=max(peak,balance);dd=max(dd,peak-balance)
  day=str(date.iloc[jj]);days[day]=days.get(day,0)+pnl;trades+=1;i=jj+1
 return dict(opportunities=opps,trades=trades,skipped_risk_filter=skips,net_usd=round(balance-1000,2),positive_pnl_after_cost=round(wins,2),negative_pnl_after_cost=round(losses,2),estimated_cost_including_entry=round(cost,2),max_closed_equity_drawdown_usd=round(dd,2),days_net_ge_50=sum(x>=50 for x in days.values()),active_days=len(days))
split=int(len(d)*.70);results={}
for name,a,b in [('train',0,split),('oos',split,len(d))]:
 for mode,f in [('fade',1),('follow',-1)]:
  for risk in (False,True):results[f'{name}_{mode}_{"riskfilter" if risk else "base"}']=run(a,b,f,risk)
print(json.dumps(dict(rows=len(d),split_index=split,results=results,assumptions='Bid M15 OHLC; spread point=.01 USD; slip .30 USD/oz each side; commission 7 USD/lot; 100oz/lot; leverage 200; no swap or intrabar stopout; all fills hypothetical'),indent=2))
