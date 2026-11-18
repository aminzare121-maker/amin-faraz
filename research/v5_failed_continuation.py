# Research only. PRIVATE CSV stays local. No MT5 orders.
import pandas as pd, numpy as np
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").drop_duplicates("time").reset_index(drop=True)
tr=np.maximum(d.high-d.low,np.maximum(abs(d.high-d.close.shift()),abs(d.low-d.close.shift())))
a=tr.rolling(32).median().shift(1).to_numpy()
o,h,l,c,sp,t=[d[x].to_numpy() for x in ["open","high","low","close","spread","time"]]
split=int(len(d)*.6)
def run(protect=False):
 cash=1000.; peak=cash;dd=0.;gross=fees=0.;last=-1;opp=blocked=0;deals=[]
 for i in range(40,len(d)-4):
  if i+1<split or not np.isfinite(a[i]) or a[i]<=0:continue
  move=c[i-1]-c[i-5];side=-int(np.sign(move))
  if not side or abs(move)<2*a[i] or np.sign(c[i]-o[i])!=side:continue
  if not ((move>0 and h[i]<h[i-1]) or (move<0 and l[i]>l[i-1])):continue
  if t[i+1]-t[i]!=900:continue
  opp+=1
  if i+1<=last:blocked+=1;continue
  stop=1.25*a[i];target=1.5*a[i]
  lot=np.floor(min(.05,max(0,cash)*.01/(100*stop))/.01)*.01
  if lot<.01:blocked+=1;continue
  if protect and np.median(tr.iloc[i-8:i])>1.7*np.median(tr.iloc[i-40:i-8]):blocked+=1;continue
  entry=o[i+1];out=c[i+3];end=i+3
  for j in range(i+1,i+4):
   sl=(l[j]<=entry-stop) if side==1 else (h[j]>=entry+stop)
   tp=(h[j]>=entry+target) if side==1 else (l[j]<=entry-target)
   if sl or tp:out=entry-side*stop if sl else entry+side*target;end=j;break
  g=side*(out-entry)*100*lot;fee=(sp[i+1]/100+.30)*100*lot+7*lot
  gross+=g;fees+=fee;cash+=g-fee;peak=max(peak,cash);dd=max(dd,peak-cash)
  deals.append((int(t[i+1]),g-fee));last=end
 days={}
 for stamp,net in deals:
  day=str(pd.to_datetime(stamp,unit="s",utc=True).date());days[day]=days.get(day,0)+net
 return dict(opportunities=opp,blocked=blocked,trades=len(deals),gross=round(gross,2),cost=round(fees,2),net=round(gross-fees,2),max_closed_dd=round(dd,2),days_ge_50=sum(x>=50 for x in days.values()))
print({"rows":len(d),"test_days":pd.to_datetime(d.time.iloc[split:],unit="s",utc=True).dt.date.nunique(),"baseline":run(),"protector":run(True)})
