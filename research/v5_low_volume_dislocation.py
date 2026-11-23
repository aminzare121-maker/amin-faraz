"""Reproduce V5 low-volume dislocation research from PRIVATE Eplanet CSV. No trading API."""
import pandas as pd, numpy as np, json
from pathlib import Path
import sys
p=Path(sys.argv[1]); d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(32).median().shift(1)
d['volmed']=d.tick_volume.rolling(32).median().shift(1)
d['median']=d.close.rolling(32).median().shift(1)
d['spmed']=d.spread.rolling(32).median().shift(1)
out={}
for split,start,end in [('train','2025-11-05','2026-06-15'),('holdout','2026-06-15','2026-11-06')]:
 for guarded in (False,True):
  cash=peak=1000.; dd=gp=gl=fees=0.; n=opp=filtered=0; daily={}; lots_used=[]; i=35
  while i<len(d)-9:
   t=d.dt.iloc[i]
   if not(pd.Timestamp(start,tz='UTC')<=t<pd.Timestamp(end,tz='UTC')):i+=1;continue
   r=d.iloc[i]; atr=r.atr
   if not np.isfinite(atr) or atr<=0:i+=1;continue
   drift=r.close-d.close.iloc[i-3]; distance=r.close-r['median']
   if abs(drift)<1.25*atr or abs(distance)<1.75*atr or np.sign(drift)!=np.sign(distance) or r.tick_volume>=.85*r.volmed:i+=1;continue
   opp+=1
   if guarded and (r.spread>min(35,1.15*r.spmed) or r.high-r.low>2*atr):filtered+=1;i+=1;continue
   side=-int(np.sign(drift)); entry=float(d.open.iloc[i+1]);stop=1.15*atr;target=1.3*atr
   fee_per_lot=(float(r.spread)*.01+.25)*100+7
   lots=np.floor(min(.10,.01*cash/(100*stop+fee_per_lot))*100)/100
   if lots<.01:filtered+=1;i+=1;continue
   price=float(d.close.iloc[i+8]);jexit=i+8
   for j in range(i+1,i+9):
    b=d.iloc[j]
    sl=b.low<=entry-stop if side==1 else b.high>=entry+stop
    tp=b.high>=entry+target if side==1 else b.low<=entry-target
    if sl:price=entry-side*stop;jexit=j;break
    if tp:price=entry+side*target;jexit=j;break
   gross=side*(price-entry)*100*lots;fee=fee_per_lot*lots;net=gross-fee
   gp+=max(0,gross);gl+=min(0,gross);fees+=fee;cash+=net;peak=max(peak,cash);dd=max(dd,peak-cash)
   n+=1;lots_used.append(float(lots))
   day=str(d.dt.iloc[jexit].date());daily[day]=daily.get(day,0)+net;i=jexit+1
  out[split+('_guard' if guarded else '_base')]={'opportunities':opp,'filtered':filtered,'trades':n,'gross_profit':round(gp,2),'gross_loss':round(gl,2),'cost':round(fees,2),'net':round(cash-1000,2),'max_closed_drawdown':round(dd,2),'days_ge_50':int(sum(v>=50 for v in daily.values())),'active_days':len(daily),'min_lot':min(lots_used) if lots_used else None,'max_lot':max(lots_used) if lots_used else None}
print(json.dumps(out,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
