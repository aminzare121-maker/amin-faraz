# V5 research: sweep-reclaim tick-volume exhaustion; private data passed as argv[1]
import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[d[k].to_numpy(float) for k in ('open','high','low','close')]
v=d.tick_volume.to_numpy(float);n=len(d);cut=int(.7*n)
p=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,abs(h-p),abs(l-p)])
atr=pd.Series(tr).shift(1).rolling(20).mean().to_numpy()
vm=pd.Series(v).shift(1).rolling(20).median().to_numpy()
hi=pd.Series(h).shift(1).rolling(16).max().to_numpy()
lo=pd.Series(l).shift(1).rolling(16).min().to_numpy()
spread=d.spread.to_numpy(float)*.01
side=np.where((l<lo-.1*atr)&(c>lo)&(c>o)&(c<hi),1,np.where((h>hi+.1*atr)&(c<hi)&(c<o)&(c>lo),-1,0))
def run(a,b,gate=False):
 eq=1000.;peak=eq;dd=0.;rows=[];opps=0;reject=0;i=max(a,50)
 while i<b-10:
  if side[i]==0 or not np.isfinite(atr[i]) or not np.isfinite(vm[i]) or vm[i]<=0:i+=1;continue
  opps+=1
  if gate and v[i]<1.5*vm[i]:reject+=1;i+=1;continue
  s=int(side[i]);stop=max(1.5,1.1*atr[i]);entry=o[i+1];cost=(spread[i+1]+.6)*100+7
  lots=np.floor(min(1.,eq*.01/(stop*100+cost))*100)/100
  if lots<.01:i+=1;continue
  end=min(i+8,b-1);xp=c[end]
  for j in range(i+1,end+1):
   if (l[j]<=entry-stop if s==1 else h[j]>=entry+stop):xp=entry-s*stop;end=j;break
   if (h[j]>=entry+1.5*stop if s==1 else l[j]<=entry-1.5*stop):xp=entry+s*1.5*stop;end=j;break
  gross=s*(xp-entry)*100*lots;fee=cost*lots;pnl=gross-fee
  eq+=pnl;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
  rows.append((str(pd.to_datetime(d.time.iloc[i],unit='s',utc=True).date()),pnl,gross,fee));i=end+1
 daily=pd.DataFrame(rows,columns=['day','pnl','gross','cost']).groupby('day').pnl.sum() if rows else pd.Series(dtype=float)
 return dict(opportunities=opps,rejected=reject,trades=len(rows),wins=sum(r[1]>0 for r in rows),gross_gain=round(sum(max(0,r[2]) for r in rows),2),gross_loss=round(sum(min(0,r[2]) for r in rows),2),net=round(eq-1000,2),cost=round(sum(r[3] for r in rows),2),drawdown_pct=round(dd*100,2),days_ge_50=int((daily>=50).sum()),trading_days=len(daily))
r={'hypothesis':'sweep-reclaim candle tick volume >= 1.5x preceding 20-bar median','split_time':str(pd.to_datetime(d.time.iloc[cut],unit='s',utc=True)),'assumptions':'100 USD per price dollar per lot; spread*0.01; 0.60 USD slippage + 7 USD commission per lot; 1% equity risk; stop-first ambiguous bars','development':{'baseline':run(0,cut),'volume_gate':run(0,cut,True)},'holdout':{'baseline':run(cut,n),'volume_gate':run(cut,n,True)}}
print(json.dumps(r,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
