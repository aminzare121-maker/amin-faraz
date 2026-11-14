import pandas as pd,numpy as np,json
from pathlib import Path
import sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[d[k].to_numpy(float) for k in ['open','high','low','close']]
n=len(d); cut=int(.7*n); spread=d.spread.to_numpy(float)*.01
tr=np.maximum.reduce([h-l,abs(h-np.r_[np.nan,c[:-1]]),abs(l-np.r_[np.nan,c[:-1]])])
atr=pd.Series(tr).rolling(20).mean().to_numpy()
ema=pd.Series(c).ewm(span=100,adjust=False).mean().to_numpy()
ph=pd.Series(h).shift(1).rolling(12).max().to_numpy()
pl=pd.Series(l).shift(1).rolling(12).min().to_numpy()
pa=pd.Series(atr).shift(1).rolling(48).median().to_numpy()
t=pd.to_datetime(d.time,unit='s',utc=True)
def test(start,end):
 eq=1000.;peak=eq;dd=0.;rows=[];i=max(start,150)
 while i<end-12:
  if not np.isfinite(pa[i]) or atr[i]<=0 or pa[i]<=0:i+=1;continue
  compress=atr[i-1]<.85*pa[i]; expand=(h[i]-l[i])>1.25*atr[i-1]
  side=1 if c[i]>ph[i] and c[i]>ema[i] and c[i]>o[i] else (-1 if c[i]<pl[i] and c[i]<ema[i] and c[i]<o[i] else 0)
  if not (compress and expand and side):i+=1;continue
  stop=max(1.5,atr[i]);cost=(spread[i+1]+.6)*100+7
  if cost/(stop*100)>.24:i+=1;continue
  entry=o[i+1];lots=np.floor(min(1.,eq*.01/(stop*100+cost))*100)/100
  if lots<.01:i+=1;continue
  last=min(i+9,end-1);xp=c[last];reason='timeout'
  for j in range(i+1,last+1):
   if (l[j]<=entry-stop if side==1 else h[j]>=entry+stop):xp=entry-side*stop;last=j;reason='stop';break
   if (h[j]>=entry+1.8*stop if side==1 else l[j]<=entry-1.8*stop):xp=entry+side*1.8*stop;last=j;reason='target';break
  pnl=side*(xp-entry)*100*lots-cost*lots;eq+=pnl;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
  rows.append(dict(day=str(t.iloc[i].date()),pnl=pnl,cost=cost*lots,reason=reason));i=last+1
 f=pd.DataFrame(rows);daily=f.groupby('day').pnl.sum() if len(f) else pd.Series(dtype=float)
 return dict(trades=len(f),net_usd=round(eq-1000,2),max_drawdown_pct=round(dd*100,2),wins=int((f.pnl>0).sum()),losses=int((f.pnl<=0).sum()),days_with_trades=len(daily),days_ge_50=int((daily>=50).sum()),total_cost_usd=round(f.cost.sum(),2))
print(json.dumps(dict(rows=n,holdout_start=str(t.iloc[cut]),development=test(0,cut),holdout=test(cut,n)),indent=2))
