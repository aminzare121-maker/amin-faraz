# V5 day-extreme rejection, reproducible research (private Eplanet CSV stays local)
import pandas as pd, numpy as np
d=pd.read_csv('Eplanet_M15_20251105_20261105_merged.csv').sort_values('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True); d['day']=d.dt.dt.date
d['hi']=d.groupby('day').high.cummax().shift(1); d['lo']=d.groupby('day').low.cummin().shift(1)
d['n']=d.groupby('day').cumcount(); d['atr']=(d.high-d.low).rolling(24).mean().shift(1)
up=(d.high>d.hi)&(d.close<d.hi)&((d.high-d.close)>abs(d.close-d.open))
dn=(d.low<d.lo)&(d.close>d.lo)&((d.close-d.low)>abs(d.close-d.open))
ok=(d.n>=12)&d.dt.dt.hour.between(12,20)&(d.atr>0)&((d.high-d.low)<3*d.atr)
d['signal']=np.where(ok&up,-1,np.where(ok&dn,1,0))
cut=int(len(d)*.65); threshold=d.loc[:cut-1,'atr'].quantile(.75)
rows=[];last=None
for i in np.flatnonzero(d.signal.to_numpy()):
 if i+5>=len(d) or d.at[i,'day']==last or d.at[i+1,'day']!=d.at[i,'day']:continue
 atr=d.at[i,'atr']; lot=min(.07,max(.01,np.floor(10/(2*atr*100)/.01)*.01))
 side=d.at[i,'signal']; gross=(d.at[i+5,'close']-d.at[i+1,'open'])*100*lot*side
 cost=(d.at[i+1,'spread']*.01+.20)*100*lot+7*lot
 rows.append((i,str(d.at[i,'day']),gross,cost,d.at[i,'atr']<=threshold))
 last=d.at[i,'day']
t=pd.DataFrame(rows,columns=['i','day','gross','cost','filtered'])
for period,z in [('train',t[t.i<cut]),('test',t[t.i>=cut])]:
 for side in [1,-1]:
  for filt in [False,True]:
   x=z[z.filtered] if filt else z
   pnl=x.gross*side-x.cost; equity=1000+pnl.cumsum()
   dd=(pd.concat([pd.Series([1000]),equity],ignore_index=True).cummax().iloc[1:].to_numpy()-equity.to_numpy()).max() if len(x) else 0
   print(period,'reversal' if side==1 else 'continuation','filter' if filt else 'all',len(x),round(pnl.sum(),2),round(dd,2),round(x.cost.sum(),2),int((pnl>=50).sum()))
# OHLC-only, no actual tick execution, stopout, swap, or guaranteed fill.
