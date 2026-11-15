# V5 tick-volume divergence: reproducible OHLC-only study
# Run: python research/v5_volume_divergence.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
import sys, json
import numpy as np
import pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['atr']=(d.high-d.low).rolling(32).mean().shift(1)
a=d.close-d.open; b=a.shift(1); v=d.tick_volume
signal=np.where((a>0)&(b>0)&(d.close>d.close.shift(1))&(v<v.shift(1)*.7),-1,np.where((a<0)&(b<0)&(d.close<d.close.shift(1))&(v<v.shift(1)*.7),1,0))
cut=int(len(d)*.65);threshold=d.iloc[:cut].atr.quantile(.65)
rows=[];occupied=-1
for i in np.flatnonzero(signal):
 if i<33 or i+5>=len(d) or i<=occupied or d.time.iloc[i+1]-d.time.iloc[i]!=900:continue
 atr=float(d.atr.iloc[i])
 if not np.isfinite(atr) or atr<=0:continue
 lot=max(.01,min(.07,np.floor(10/(2*atr*100)*100)/100))
 entry=float(d.open.iloc[i+1]);side=int(signal[i]);sl=entry-side*2*atr;tp=entry+side*2*atr
 exit_price=float(d.close.iloc[i+5]);end=i+5
 for j in range(i+1,i+6):
  if d.time.iloc[j]-d.time.iloc[j-1]!=900:
   end=j-1;exit_price=float(d.close.iloc[end]);break
  if (side==1 and d.low.iloc[j]<=sl) or (side==-1 and d.high.iloc[j]>=sl):
   exit_price=sl;end=j;break
  if (side==1 and d.high.iloc[j]>=tp) or (side==-1 and d.low.iloc[j]<=tp):
   exit_price=tp;end=j;break
 cost=(float(d.spread.iloc[i+1])*.01+.20)*100*lot+7*lot
 gross=(exit_price-entry)*side*100*lot
 rows.append(dict(i=i,date=str(d.dt.iloc[i].date()),gross=gross,cost=cost,pnl=gross-cost,filtered=atr<=threshold))
 occupied=end
t=pd.DataFrame(rows)
for period,z in [('train',t[t.i<cut]),('test',t[t.i>=cut])]:
 for filt in (False,True):
  x=z[z.filtered] if filt else z
  eq=1000+x.pnl.cumsum()
  dd=(pd.concat([pd.Series([1000]),eq],ignore_index=True).cummax().iloc[1:].to_numpy()-eq.to_numpy()).max() if len(x) else 0
  days=x.groupby('date').pnl.sum()
  print(period,'filtered' if filt else 'all',len(x),round(x.loc[x.gross>0,'gross'].sum(),2),round(x.loc[x.gross<0,'gross'].sum(),2),round(x.cost.sum(),2),round(x.pnl.sum(),2),round(float(dd),2),int((days>=50).sum()))
# Simplifications: no tick replay, real slippage, margin, stop-out or swap; not for live execution.
