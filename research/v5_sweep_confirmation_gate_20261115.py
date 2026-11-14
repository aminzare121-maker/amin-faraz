# V5 sweep-reclaim: one completed candle confirmation; Eplanet M15 only
# Run: python research/v5_sweep_confirmation_gate_20261115.py path/to/Eplanet_M15_20251105_20261105_merged.csv
import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[d[x].to_numpy(float) for x in ['open','high','low','close']]
n=len(d);cut=int(.7*n);p=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,abs(h-p),abs(l-p)])
atr=pd.Series(tr).shift(1).rolling(20).mean().to_numpy()
hi=pd.Series(h).shift(1).rolling(16).max().to_numpy()
lo=pd.Series(l).shift(1).rolling(16).min().to_numpy()
side=np.where((l<lo-.1*atr)&(c>lo)&(c>o)&(c<hi),1,np.where((h>hi+.1*atr)&(c<hi)&(c<o)&(c>lo),-1,0))
spread=d.spread.to_numpy(float)*.01
def run(a,b,confirm):
 eq=1000.;peak=eq;dd=0.;signals=0;eligible=0;rows=[];i=max(a,50)
 while i<b-11:
  s=int(side[i])
  if s==0 or not np.isfinite(atr[i]) or atr[i]<=0:i+=1;continue
  signals+=1
  if confirm and not (s*(c[i+1]-c[i])>0 and s*(c[i+1]-o[i+1])>0):i+=1;continue
  eligible+=1;k=i+(2 if confirm else 1);stop=max(1.5,1.1*atr[i]);entry=o[k]
  cost=(spread[k]+.6)*100+7
  lots=np.floor(min(1.,eq*.01/(stop*100+cost))*100)/100
  if lots<.01:i+=1;continue
  last=min(k+7,b-1);xp=c[last]
  for j in range(k,last+1):
   if (l[j]<=entry-stop if s==1 else h[j]>=entry+stop):xp=entry-s*stop;last=j;break
   if (h[j]>=entry+1.5*stop if s==1 else l[j]<=entry-1.5*stop):xp=entry+s*1.5*stop;last=j;break
  pnl=s*(xp-entry)*100*lots-cost*lots;eq+=pnl;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
  rows.append((str(pd.to_datetime(d.time.iloc[k],unit='s',utc=True).date()),pnl,cost*lots))
  i=last+1
 f=pd.DataFrame(rows,columns=['day','pnl','cost'])
 daily=f.groupby('day').pnl.sum() if len(f) else pd.Series(dtype=float)
 return dict(signals_seen=signals,eligible=eligible,trades=len(f),wins=int((f.pnl>0).sum()) if len(f) else 0,losses=int((f.pnl<=0).sum()) if len(f) else 0,net_usd=round(eq-1000,2),gross_usd=round(eq-1000+f.cost.sum(),2) if len(f) else 0,cost_usd=round(f.cost.sum(),2) if len(f) else 0,max_drawdown_pct=round(dd*100,2),trading_days=len(daily),days_ge_50=int((daily>=50).sum()))
out={'holdout_start':str(pd.to_datetime(d.time.iloc[cut],unit='s',utc=True))}
for name,(a,b) in {'development':(0,cut),'holdout':(cut,n)}.items():
 out[name]={'baseline':run(a,b,False),'confirm':run(a,b,True)}
print(json.dumps(out,indent=2))
