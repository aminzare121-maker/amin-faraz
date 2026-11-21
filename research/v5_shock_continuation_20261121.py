"""Research only. No MT5 execution. Usage: python script.py private_Eplanet.csv"""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
assert {'time','open','high','low','close'}.issubset(d.columns)
d['date']=pd.to_datetime(d.time,unit='s',utc=True).dt.date
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.rolling(32,min_periods=32).mean().shift(1).to_numpy()
o,h,l,c=[d[k].to_numpy() for k in ['open','high','low','close']]
dates=sorted(d.date.unique());split=int(.6*len(dates));train=set(dates[:split]);test=set(dates[split:]);datesarr=d.date.to_numpy()
def run(dayset,threshold,guard):
 eq=1000.;peak=1000.;maxdd=0.;gp=gl=fees=0.;trades=opps=skip=0;daily={};active_until=-1
 for i in range(33,len(d)-5):
  if datesarr[i] not in dayset or i<=active_until:continue
  if not np.isfinite(atr[i]) or atr[i]<=0:continue
  body=c[i]-o[i];direction=1 if body>0 else -1
  opposing=(min(o[i],c[i])-l[i]) if direction==1 else (h[i]-max(o[i],c[i]))
  if abs(body)<threshold*atr[i] or opposing>0.2*abs(body):continue
  opps+=1;stop=1.5*atr[i];lot=np.floor((eq*.01/(stop*100))*100)/100
  if lot<.01:skip+=1;continue
  lot=min(.2,lot);oz=lot*100;entry=o[i+1];end=i+4;exitprice=c[end]
  if guard:
   sl=entry-direction*stop
   for k in range(i+1,end+1):
    if (direction==1 and l[k]<=sl) or (direction==-1 and h[k]>=sl):
     exitprice=min(sl,o[k]) if direction==1 else max(sl,o[k]);end=k;break
  raw=direction*(exitprice-entry)*oz;fee=.45*oz;net=raw-fee
  eq+=net;peak=max(peak,eq);maxdd=max(maxdd,peak-eq)
  gp+=max(raw,0);gl+=min(raw,0);fees+=fee;trades+=1
  day=str(datesarr[i]);daily[day]=daily.get(day,0)+net;active_until=end
 return dict(opportunities=opps,trades=trades,skipped_min_lot=skip,gross_profit=round(gp,2),gross_loss=round(gl,2),estimated_cost=round(fees,2),net=round(eq-1000,2),max_closed_drawdown=round(maxdd,2),days_ge_50=sum(v>=50 for v in daily.values()),days_evaluated=len(dayset),days_traded=len(daily),days_loss=sum(v<0 for v in daily.values()))
r={'rows':len(d),'split_days':[len(train),len(test)],'assumptions':'100 oz/lot; min 0.01 lot; 1% equity risk sizing; max 0.20 lot; $0.45/oz round-trip proxy; 4 bars holding; UTC; OHLC only','train':{},'out_of_sample':{}}
for threshold in [1.0,1.5,2.0]:
 for guard in [False,True]:
  key=f'body_{threshold}_guard_{guard}';r['train'][key]=run(train,threshold,guard);r['out_of_sample'][key]=run(test,threshold,guard)
print(json.dumps(r,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
