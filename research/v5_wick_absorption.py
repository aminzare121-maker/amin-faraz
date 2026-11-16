"""Research-only: high-volume rejection wick, opposite-direction control, volatility exclusion.
Usage: python research/v5_wick_absorption.py Eplanet_M15_20251105_20261105_merged.csv
Private input stays local. No MT5 orders.
"""
import sys, json
import numpy as np
import pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
n=len(d); cut=int(n*.65)
a=(d.high-d.low).rolling(32).median().shift(1).to_numpy()
v=d.tick_volume.rolling(32).median().shift(1).to_numpy()
span=(d.high-d.low).to_numpy(); body=abs(d.close-d.open).to_numpy()
up=(d.high-np.maximum(d.open,d.close)).to_numpy()
down=(np.minimum(d.open,d.close)-d.low).to_numpy()
T=d.time.to_numpy(); O=d.open.to_numpy(); H=d.high.to_numpy(); L=d.low.to_numpy(); C=d.close.to_numpy(); V=d.tick_volume.to_numpy(); S=d.spread.to_numpy()
signal=np.where((down>span*.6)&(body<span*.3)&(V>v*1.5)&(span>a*.8),1,np.where((up>span*.6)&(body<span*.3)&(V>v*1.5)&(span>a*.8),-1,0))
threshold=np.nanquantile(a[:cut],.6); trades=[]
for name,mult in [("reversal",1),("continuation_control",-1)]:
 occupied=-1
 for i in np.flatnonzero(signal):
  if i<35 or i+5>=n or i<=occupied or T[i+1]-T[i]!=900: continue
  atr=a[i]
  if not np.isfinite(atr) or atr<=0:continue
  side=int(signal[i])*mult
  lot=max(.01,min(.07,np.floor(10/(2*atr*100)*100)/100))
  entry=O[i+1]; sl=entry-side*2*atr; tp=entry+side*2*atr
  end=i+5; exitp=C[end]; adverse=0
  for j in range(i+1,i+6):
   if T[j]-T[j-1]!=900: end=j-1;exitp=C[end];break
   adverse=max(adverse,(entry-L[j]) if side==1 else (H[j]-entry))
   if (side==1 and L[j]<=sl) or (side==-1 and H[j]>=sl):exitp=sl;end=j;break
   if (side==1 and H[j]>=tp) or (side==-1 and L[j]<=tp):exitp=tp;end=j;break
  cost=(S[i+1]*.01+.20)*100*lot+7*lot
  gross=(exitp-entry)*side*100*lot
  trades.append(dict(method=name,i=int(i),date=str(pd.to_datetime(T[i],unit="s",utc=True).date()),gross=float(gross),cost=float(cost),pnl=float(gross-cost),filtered=bool(atr<=threshold),adverse=float(adverse*100*lot)))
  occupied=end
out=[]
for method in ("reversal","continuation_control"):
 for period in ("train","test"):
  for filtered in (False,True):
   z=[r for r in trades if r["method"]==method and (r["i"]<cut)==(period=="train") and (r["filtered"] or not filtered)]
   pnl=np.array([r["pnl"] for r in z]); gross=np.array([r["gross"] for r in z])
   eq=1000+np.cumsum(pnl)
   dd=float(np.max(np.maximum.accumulate(np.r_[1000,eq])[1:]-eq)) if len(eq) else 0.
   days={}
   for r in z:days[r["date"]]=days.get(r["date"],0)+r["pnl"]
   out.append(dict(method=method,period=period,filtered=filtered,trades=len(z),gross_wins=round(float(gross[gross>0].sum()),2),gross_losses=round(float(gross[gross<0].sum()),2),costs=round(sum(r["cost"] for r in z),2),net=round(float(pnl.sum()),2),closed_drawdown=round(dd,2),max_adverse_single_trade=round(max([r["adverse"] for r in z],default=0),2),days_ge_50=int(sum(x>=50 for x in days.values())),days_with_trades=len(days)))
print(json.dumps(dict(rows=n,cut=cut,results=out),ensure_ascii=False,indent=2))
# Limitations: OHLC not tick replay, stop-first, assumed $0.20/oz slippage and $7/lot commission; no swap, margin, stop-out.
