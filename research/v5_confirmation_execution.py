# Research-only; no MT5 orders. Requires local PRIVATE Eplanet CSV.
import pandas as pd, numpy as np
d=pd.read_csv("Eplanet_M15_20251105_20261105_merged.csv").sort_values("time").drop_duplicates("time").reset_index(drop=True)
tr=np.maximum(d.high-d.low,np.maximum(abs(d.high-d.close.shift()),abs(d.low-d.close.shift())))
atr=tr.shift(1).rolling(32).median()
er=abs(d.close-d.close.shift(8))/d.close.diff().abs().rolling(8).sum()
split=int(.6*len(d))
def test(confirmed=False):
 cash=1000.;peak=cash;dd=0.;used=-1;opps=0;reject=0;gross=cost=0.;logs=[]
 for i in range(45,len(d)-9):
  a=float(atr.iloc[i]);e=float(er.iloc[i]);side=int(np.sign(d.close.iloc[i]-d.close.iloc[i-8]))
  if not np.isfinite(a) or a<=0 or not np.isfinite(e) or not side:continue
  if e<.72 or abs(d.close.iloc[i]-d.close.iloc[i-8])<1.1*a or abs(d.close.iloc[i]-d.open.iloc[i])>1.4*a:continue
  if d.time.iloc[i+2]-d.time.iloc[i]!=1800:continue
  j=i+2 if confirmed else i+1
  if j<split or j<=used:continue
  opps+=1
  if confirmed and (side*(d.close.iloc[i+1]-d.open.iloc[i+1])<=0 or side*(d.close.iloc[i+1]-d.close.iloc[i])<0 or d.high.iloc[i+1]-d.low.iloc[i+1]>1.5*a):
   reject+=1;continue
  stop=1.3*a;target=2*a;lot=np.floor(min(.05,cash*.01/(100*stop))/.01)*.01
  if lot<.01:reject+=1;continue
  entry=float(d.open.iloc[j]);end=min(j+5,len(d)-1);out=float(d.close.iloc[end])
  for k in range(j,end+1):
   sl=d.low.iloc[k]<=entry-stop if side==1 else d.high.iloc[k]>=entry+stop
   tp=d.high.iloc[k]>=entry+target if side==1 else d.low.iloc[k]<=entry-target
   if sl or tp:out=entry-side*stop if sl else entry+side*target;end=k;break
  g=side*(out-entry)*100*lot;c=(float(d.spread.iloc[j])/100+.30)*100*lot+7*lot
  gross+=g;cost+=c;cash+=g-c;peak=max(peak,cash);dd=max(dd,peak-cash);used=end
  logs.append((int(d.time.iloc[j]),float(lot),float(g-c)))
 days={}
 for t,lot,net in logs:
  day=str(pd.to_datetime(t,unit="s",utc=True).date());days[day]=days.get(day,0)+net
 return dict(opportunities=opps,rejected=reject,trades=len(logs),gross=round(gross,2),cost=round(cost,2),net=round(gross-cost,2),max_closed_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in days.values()),test_days=int(pd.to_datetime(d.time.iloc[split:],unit="s",utc=True).dt.date.nunique()))
print(dict(rows=len(d),baseline=test(False),confirmation=test(True)))
