import pandas as pd, numpy as np
# Reproducible research; requires private CSV locally; never commit market data.
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["gap"]=d.open-d.close.shift()
d["range"]= (d.high-d.low).rolling(96,min_periods=96).median().shift(1)
split=int(len(d)*.6)
def evaluate(start,end,k):
 equity=1000.; peak=1000.; dd=0.; last=-1; opp=0; trades=[]; dates={}
 for i in range(start,end-5):
  if i<=last: continue
  a=d.iloc[i];r=a["range"]
  if not np.isfinite(r) or r<=0 or abs(a.gap)<k*r: continue
  opp+=1; side=-np.sign(a.gap); entry=a.open; stop=entry-side*r; target=d.close.iloc[i-1]
  lot=np.floor(min(.1,equity*.01/(r*100+63))/.01)*.01
  if lot<.01:continue
  px=d.close.iloc[i+3]; endbar=i+3
  for j in range(i,i+4):
   b=d.iloc[j]
   if (b.low<=stop if side>0 else b.high>=stop):px=stop;endbar=j;break
   if (b.high>=target if side>0 else b.low<=target):px=target;endbar=j;break
  gross=side*(px-entry)*100*lot;cost=63*lot;net=gross-cost
  equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);last=endbar
  day=pd.to_datetime(a.time,unit="s",utc=True).date();dates[day]=dates.get(day,0)+net
  trades.append((gross,cost,net))
 return dict(opportunities=opp,trades=len(trades),gross=round(sum(t[0] for t in trades),2),cost=round(sum(t[1] for t in trades),2),net=round(sum(t[2] for t in trades),2),drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in dates.values()))
train={k:evaluate(97,split,k) for k in (.5,1,1.5,2)}
k=max(train,key=lambda x:train[x]["net"])
print("selected",k,"train",train[k],"holdout",evaluate(split,len(d),k))
