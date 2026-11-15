# Cost-efficiency research gate; requires private Eplanet CSV locally, never commit data
# Run: python research/v5_cost_efficiency_gate.py path/to/Eplanet_M15_20251105_20261105_merged.csv
import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[d[x].to_numpy(float) for x in ('open','high','low','close')]
n=len(d);cut=int(.7*n);p=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,abs(h-p),abs(l-p)])
atr=pd.Series(tr).shift(1).rolling(20).mean().to_numpy()
hi=pd.Series(h).shift(1).rolling(16).max().to_numpy()
lo=pd.Series(l).shift(1).rolling(16).min().to_numpy()
spread=d.spread.to_numpy(float)*.01
side=np.where((l<lo-.1*atr)&(c>lo)&(c>o)&(c<hi),1,np.where((h>hi+.1*atr)&(c<hi)&(c<o)&(c>lo),-1,0))
def run(a,b,gate):
 eq=1000.;peak=eq;dd=0.;rows=[];candidates=0;rejected=0;i=max(a,50)
 while i<b-10:
  if not np.isfinite(atr[i]) or atr[i]<=0 or side[i]==0:i+=1;continue
  candidates+=1;s=int(side[i]);stop=max(1.5,1.1*atr[i]);cost=(spread[i]+.6)*100+7
  if gate and cost/(stop*100)>.08:rejected+=1;i+=1;continue
  entry=o[i+1];actual_cost=(spread[i+1]+.6)*100+7
  lots=np.floor(min(1.,eq*.01/(stop*100+actual_cost))*100)/100
  if lots<.01:i+=1;continue
  last=min(i+8,b-1);xp=c[last]
  for j in range(i+1,last+1):
   if (l[j]<=entry-stop if s==1 else h[j]>=entry+stop):xp=entry-s*stop;last=j;break
   if (h[j]>=entry+1.5*stop if s==1 else l[j]<=entry-1.5*stop):xp=entry+s*1.5*stop;last=j;break
  pnl=s*(xp-entry)*100*lots-actual_cost*lots;eq+=pnl;peak=max(eq,peak);dd=max(dd,(peak-eq)/peak)
  rows.append((pnl,actual_cost*lots,str(pd.to_datetime(d.time.iloc[i],unit='s',utc=True))[:10]));i=last+1
 daily=pd.DataFrame(rows,columns=['pnl','cost','day']).groupby('day').pnl.sum() if rows else pd.Series(dtype=float)
 return dict(candidates=candidates,rejected=rejected,trades=len(rows),wins=sum(x[0]>0 for x in rows),gross_profit=round(sum(max(0,x[0]) for x in rows),2),gross_loss=round(sum(min(0,x[0]) for x in rows),2),net=round(eq-1000,2),cost=round(sum(x[1] for x in rows),2),max_dd_pct=round(dd*100,2),days_traded=len(daily),days_ge_50=int(sum(daily>=50)))
result={'hypothesis':'transaction cost <= 8% of 1R','development':{'baseline':run(0,cut,False),'cost_gate':run(0,cut,True)},'holdout':{'baseline':run(cut,n,False),'cost_gate':run(cut,n,True)}}
print(json.dumps(result,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
