# Reproducible research entrypoint. Private Eplanet CSV is NOT committed.
# Run: python research/v5_failed_auction.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
import sys, json, hashlib
import numpy as np
import pandas as pd
from pathlib import Path
p=Path(sys.argv[1]); d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
atr=tr.shift(1).rolling(24).median()
hi=d.high.shift(1).rolling(12).max(); lo=d.low.shift(1).rolling(12).min()
buy=(d.low<lo)&(d.close>lo)&((d.close-d.low)>.55*(d.high-d.low))
sell=(d.high>hi)&(d.close<hi)&((d.high-d.close)>.55*(d.high-d.low))
signals=np.where(buy,1,np.where(sell,-1,0)); split=int(len(d)*.6)
def run(start,end,guard):
 equity=peak=1000.;dd=0.;i=max(start,36);opps=rejected=0;ledger=[]
 while i<end-9:
  s=int(signals[i])
  if not s or not np.isfinite(atr[i]) or atr[i]<=0:i+=1;continue
  opps+=1
  if guard and (d.spread[i]>30 or (d.high[i]-d.low[i])>2.5*atr[i]):
   rejected+=1;i+=1;continue
  entry=float(d.open[i+1]);dist=float(max(1.5*atr[i],2.0))
  lot=np.floor((equity*.01)/(dist*100)*100)/100
  if lot<.01:rejected+=1;i+=1;continue
  lot=min(lot,.2);stop=entry-s*dist;target=entry+s*2*dist
  price=float(d.close[i+8]);last=i+8
  for k in range(i+1,i+9):
   if (s==1 and d.low[k]<=stop) or (s==-1 and d.high[k]>=stop):price=stop;last=k;break
   if (s==1 and d.high[k]>=target) or (s==-1 and d.low[k]>=target):price=target;last=k;break
  gross=(price-entry)*s*100*lot;cost=1.46*lot/.01;net=gross-cost
  equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity)
  ledger.append({'time':int(d.time[i]),'lot':float(lot),'gross':float(gross),'cost':float(cost),'net':float(net)})
  i=last+1
 daily={}
 for t in ledger:
  day=str(pd.to_datetime(t['time'],unit='s',utc=True).date());daily[day]=daily.get(day,0)+t['net']
 return {'opportunities':opps,'rejected':rejected,'trades':len(ledger),'gross':round(sum(x['gross'] for x in ledger),2),'cost':round(sum(x['cost'] for x in ledger),2),'net':round(sum(x['net'] for x in ledger),2),'closed_drawdown':round(dd,2),'days':int(pd.to_datetime(d.time.iloc[start:end],unit='s',utc=True).dt.date.nunique()),'days_ge_50':sum(v>=50 for v in daily.values()),'ledger':ledger}
result={'bars':len(d),'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'train':{'base':run(0,split,False),'guard':run(0,split,True)},'oos':{'base':run(split,len(d),False),'guard':run(split,len(d),True)}}
print(json.dumps(result,indent=2))
