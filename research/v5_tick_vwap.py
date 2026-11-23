# V5 intraday tick-VWAP reversion. Private Eplanet CSV is NOT committed.
# Reproduction: python research/v5_tick_vwap.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
import sys, json
import pandas as pd, numpy as np
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True);d['day']=d.dt.dt.date
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(32).median().shift(1)
v=d.tick_volume.clip(lower=1);p=(d.high+d.low+d.close)/3
d['vwap']=(p*v).groupby(d.day).cumsum()/v.groupby(d.day).cumsum()
d['bar']=d.groupby('day').cumcount()+1
d['eff']=(d.close-d.close.shift(32)).abs()/d.close.diff().abs().rolling(32).sum()
d['spmed']=d.spread.rolling(32).median().shift(1)
out={}
for label,start,end in [('train','2025-11-05','2026-06-15'),('holdout','2026-06-15','2026-11-06')]:
 for guard in (False,True):
  equity=peak=1000.;gp=gl=cost=dd=0.;opp=rej=n=0;days={};i=40
  while i<len(d)-9:
   r=d.iloc[i];t=r['dt']
   if not(pd.Timestamp(start,tz='UTC')<=t<pd.Timestamp(end,tz='UTC')):i+=1;continue
   a=r.atr
   if not np.isfinite(a) or a<=0 or not 12<=r.bar<=75:i+=1;continue
   delta=r.close-r.vwap
   long=delta< -1.6*a and r.close>r.open and r.close>r.low+.65*(r.high-r.low)
   short=delta>1.6*a and r.close<r.open and r.close<r.high-.65*(r.high-r.low)
   if not(long or short):i+=1;continue
   opp+=1
   if guard and (r.eff>.35 or r.spread>1.1*r.spmed or r.high-r.low>2.5*a):rej+=1;i+=1;continue
   side=1 if long else -1;entry=float(d.open.iloc[i+1]);stop=1.15*a
   target=min(2.2*a,abs(float(r.vwap)-entry))
   if target<.5*a:rej+=1;i+=1;continue
   fee=(r.spread*.01+2*.25)*100+7
   lot=np.floor(min(.10,.01*equity/(100*stop+fee))*100)/100
   if lot<.01:rej+=1;i+=1;continue
   exitp=float(d.close.iloc[i+8]);ex=i+8
   for j in range(i+1,i+9):
    b=d.iloc[j];sl=b.low<=entry-stop if long else b.high>=entry+stop
    tp=b.high>=entry+target if long else b.low<=entry-target
    if sl or tp:exitp=entry+side*(-stop if sl else target);ex=j;break
   gross=side*(exitp-entry)*100*lot;fees=fee*lot;net=gross-fees
   gp+=max(gross,0);gl+=min(gross,0);cost+=fees;equity+=net
   peak=max(peak,equity);dd=max(dd,peak-equity);n+=1
   day=str(d.dt.iloc[ex].date());days[day]=days.get(day,0)+net;i=ex+1
  out[label+('_guard' if guard else '_base')]={'opportunities':opp,'rejected':rej,'trades':n,'gross_profit':round(gp,2),'gross_loss':round(gl,2),'cost':round(cost,2),'net':round(equity-1000,2),'max_closed_drawdown':round(dd,2),'days_ge_50':sum(x>=50 for x in days.values())}
print(json.dumps(out,indent=2))
