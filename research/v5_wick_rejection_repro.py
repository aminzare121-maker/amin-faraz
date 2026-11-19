# Reproduction: python research/v5_wick_rejection_repro.py /private/path/Eplanet_M15_20251105_20261105_merged.csv
import sys
import numpy as np
import pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
o,h,l,c=[d[x].to_numpy() for x in ("open","high","low","close")]
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))))
atr=pd.Series(tr).rolling(20).median().to_numpy()
hi=pd.Series(h).shift(1).rolling(20).max().to_numpy()
lo=pd.Series(l).shift(1).rolling(20).min().to_numpy()
r=np.maximum(h-l,1e-6); upper=(h-np.maximum(o,c))/r;lower=(np.minimum(o,c)-l)/r
split=int(len(d)*.6)
def run(start,end,threshold,guard=False):
 eq=peak=1000.; dd=0.; opp=0;gross=fees=0.;n=0;daily={}
 i=max(start,25)
 while i<min(end-5,len(d)-5):
  a=atr[i]
  if not np.isfinite(a) or a<=0:i+=1;continue
  side=1 if l[i]<lo[i] and lower[i]>=threshold and c[i]>lo[i] else (-1 if h[i]>hi[i] and upper[i]>=threshold and c[i]<hi[i] else 0)
  if not side:i+=1;continue
  opp+=1
  if guard and (r[i]>2*a or r[i]<.5*a):i+=1;continue
  entry=o[i+1];stop=entry-side*a;target=entry+side*1.5*a
  lot=np.floor(min(.1,max(0,eq)*.005/(a*100))*100)/100
  if lot<.01:i+=1;continue
  out=c[i+4];j=i+4
  for k in range(i+1,i+5):
   if (l[k]<=stop if side==1 else h[k]>=stop):out=stop;j=k;break
   if (h[k]>=target if side==1 else l[k]<=target):out=target;j=k;break
  g=(out-entry)*side*100*lot;f=lot*67;net=g-f
  gross+=g;fees+=f;eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq);n+=1
  day=str(pd.to_datetime(d.time.iloc[i+1],unit="s",utc=True).date());daily[day]=daily.get(day,0)+net
  i=j+1
 days=len(set(pd.to_datetime(d.time.iloc[start:end],unit="s",utc=True).dt.date))
 return dict(opportunities=opp,trades=n,gross=round(gross,2),cost=round(fees,2),net=round(gross-fees,2),drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in daily.values()),days=days)
train=[(x,run(0,split,x)) for x in (.55,.65,.75)]
chosen=max(train,key=lambda z:z[1]["net"])[0]
print("train",train,"selected",chosen)
print("OOS base",run(split,len(d),chosen))
print("OOS guard",run(split,len(d),chosen,True))
