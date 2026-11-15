import pandas as pd,numpy as np,json,sys
D=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
t=pd.to_datetime(D.time,unit='s',utc=True);o,h,l,c=[D[x].to_numpy(float) for x in ('open','high','low','close')];n=len(D);cut=int(n*.7)
prev=np.r_[np.nan,c[:-1]];tr=np.maximum.reduce([h-l,abs(h-prev),abs(l-prev)]);atr=pd.Series(tr).shift(1).rolling(20).mean().to_numpy()
inside=(h<np.r_[np.nan,h[:-1]])&(l>np.r_[np.nan,l[:-1]])
range20=pd.Series(h-l).shift(1).rolling(20).median().to_numpy()
mid=np.r_[np.nan,(h[:-1]+l[:-1])/2]
side=np.where(inside&(h-l<.65*range20)&(c>o)&(c>mid),1,np.where(inside&(h-l<.65*range20)&(c<o)&(c<mid),-1,0))
hour=t.dt.hour.to_numpy();side=np.where((hour>=12)&(hour<17),side,0)
spread=D.spread.to_numpy(float)*.01
def run(a,b):
 eq=1000.;peak=eq;dd=0.;rows=[];signals=0;i=max(50,a)
 while i<b-9:
  if side[i]==0 or not np.isfinite(atr[i]) or atr[i]<=0:i+=1;continue
  signals+=1;s=int(side[i]);stop=max(1.5,atr[i]);entry=o[i+1];cost=(spread[i+1]+.6)*100+7
  lots=np.floor(min(1.,eq*.01/(stop*100+cost))*100)/100
  if lots<.01:i+=1;continue
  xp=c[i+8];last=i+8;reason='timeout'
  for j in range(i+1,i+9):
   if (l[j]<=entry-stop if s==1 else h[j]>=entry+stop):xp=entry-s*stop;last=j;reason='stop';break
   if (h[j]>=entry+1.5*stop if s==1 else l[j]<=entry-1.5*stop):xp=entry+s*1.5*stop;last=j;reason='target';break
  pnl=s*(xp-entry)*100*lots-cost*lots;eq+=pnl;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
  rows.append(dict(time=str(t[i]),side=s,lots=lots,pnl=round(pnl,4),cost=round(cost*lots,4),reason=reason));i=last+1
 daily=pd.DataFrame(rows).assign(day=lambda x:x.time.str[:10]).groupby('day').pnl.sum() if rows else pd.Series(dtype=float)
 return dict(opportunities=signals,trades=len(rows),wins=sum(x['pnl']>0 for x in rows),net_usd=round(eq-1000,2),gross_wins_usd=round(sum(max(0,x['pnl']) for x in rows),2),gross_losses_usd=round(sum(min(0,x['pnl']) for x in rows),2),cost_usd=round(sum(x['cost'] for x in rows),2),max_drawdown_pct=round(dd*100,2),days_traded=len(daily),days_ge_50=int(sum(daily>=50)))
a=run(0,cut);b=run(cut,n)
res=dict(hypothesis='Low-range inside-bar directional continuation during 12-17 UTC',n=n,cut=str(t[cut]),assumptions='1% equity risk, variable 0.01 lot increments, $100/lot/$1, spread points*.01, $0.60 roundtrip slippage, $7/lot commission; stop-first ambiguous OHLC',development=a,holdout=b)
print(json.dumps(res,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
