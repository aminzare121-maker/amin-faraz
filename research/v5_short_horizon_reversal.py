import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['ret']=d.close.diff()
d['scale']=d.ret.abs().rolling(96,min_periods=96).median().shift(1)
d['spmed']=d.spread.rolling(96).median().shift(1)
def test(start,end,guard):
 eq=peak=1000.;dd=gp=gl=fees=0.;trades=opp=reject=0;daily={};i=100
 while i<len(d)-4:
  r=d.iloc[i];ts=r['dt']
  if not(start<=ts<end):i+=1;continue
  scale=r['scale']
  if not np.isfinite(scale) or scale<=0:i+=1;continue
  shock=r['ret']
  if abs(shock)<3.0*scale:i+=1;continue
  opp+=1
  if guard and (r.spread>r.spmed or abs(shock)>7*scale or r.high-r.low>8*scale):reject+=1;i+=1;continue
  side=-np.sign(shock);entry=float(d.open.iloc[i+1]);stop=max(2.5*scale,0.6*abs(shock));target=1.3*stop
  cost_per_lot=100*(r.spread*.01+0.4)+7
  lot=np.floor(min(.10,eq*.01/(100*stop+cost_per_lot))*100)/100
  if lot<.01:reject+=1;i+=1;continue
  ex=float(d.close.iloc[i+3]);endidx=i+3
  for j in range(i+1,i+4):
   bar=d.iloc[j];sl=entry-side*stop;tp=entry+side*target
   if bar.low<=sl<=bar.high or (side==1 and bar.low<=sl) or (side==-1 and bar.high>=sl):ex=sl;endidx=j;break
   if (side==1 and bar.high>=tp) or (side==-1 and bar.low<=tp):ex=tp;endidx=j;break
  gross=(ex-entry)*side*100*lot;fee=cost_per_lot*lot;net=gross-fee
  gp+=max(0,gross);gl+=min(0,gross);fees+=fee;eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq);trades+=1
  key=str(d.dt.iloc[endidx].date());daily[key]=daily.get(key,0)+net;i=endidx+1
 return {'opportunities':opp,'trades':trades,'rejected':reject,'gross_profit':round(gp,2),'gross_loss':round(gl,2),'costs':round(fees,2),'net':round(eq-1000,2),'max_closed_drawdown':round(dd,2),'days_ge_50':sum(x>=50 for x in daily.values()),'active_days':len(daily),'equity_end':round(eq,2)}
out={}
for name,a,b in [('train','2025-11-05','2026-06-15'),('holdout','2026-06-15','2026-11-06')]:
 out[name]={}
 for g in (False,True):out[name]['guard' if g else 'base']=test(pd.Timestamp(a,tz='UTC'),pd.Timestamp(b,tz='UTC'),g)
print(json.dumps(out,indent=2,default=lambda x:x.item()))
