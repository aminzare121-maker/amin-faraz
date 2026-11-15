import pandas as pd, numpy as np, json, sys
D=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[D[k].to_numpy(float) for k in ['open','high','low','close']];n=len(D)
t=pd.to_datetime(D.time,unit='s',utc=True);prev=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,abs(h-prev),abs(l-prev)])
atr=pd.Series(tr).shift(1).rolling(24).median().to_numpy()
ma=pd.Series(c).shift(1).rolling(32).mean().to_numpy()
side=np.zeros(n,dtype=int)
for i in range(40,n-8):
 if not np.isfinite(atr[i]) or atr[i]<=0:continue
 if c[i-3]>ma[i-3] and c[i-3]-c[i-27]>1.5*atr[i] and c[i-2]<o[i-2] and c[i-1]<o[i-1] and c[i]>o[i] and c[i]>h[i-1] and c[i]<c[i-3]:side[i]=1
 if c[i-3]<ma[i-3] and c[i-3]-c[i-27]<-1.5*atr[i] and c[i-2]>o[i-2] and c[i-1]>o[i-1] and c[i]<o[i] and c[i]<l[i-1] and c[i]>c[i-3]:side[i]=-1
spread=D.spread.to_numpy(float)*.01;cut=int(n*.7)
def test(a,b):
 equity=1000.;peak=1000.;dd=0.;rows=[];signals=0;i=max(a,40)
 while i<b-9:
  if not side[i]:i+=1;continue
  signals+=1;s=side[i];entry=o[i+1];dist=max(1.,1.15*atr[i]);cost_lot=(spread[i+1]+.6)*100+7
  lots=np.floor(min(1.,equity*.01/(dist*100+cost_lot))*100)/100
  if lots<.01:i+=1;continue
  last=min(i+8,b-1);exit_price=c[last];reason='timeout'
  for j in range(i+1,last+1):
   if (l[j]<=entry-dist if s==1 else h[j]>=entry+dist):exit_price=entry-s*dist;last=j;reason='stop';break
   if (h[j]>=entry+1.5*dist if s==1 else l[j]<=entry-1.5*dist):exit_price=entry+s*1.5*dist;last=j;reason='target';break
  gross=s*(exit_price-entry)*100*lots;cost=cost_lot*lots;pnl=gross-cost;equity+=pnl;peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
  rows.append(dict(time=str(t.iloc[i]),side=int(s),lots=float(lots),gross=float(gross),cost=float(cost),pnl=float(pnl),reason=reason));i=last+1
 daily=pd.DataFrame(rows).assign(day=lambda z:z.time.str[:10]).groupby('day').pnl.sum() if rows else pd.Series(dtype=float)
 return dict(opportunities=signals,trades=len(rows),wins=sum(r['pnl']>0 for r in rows),gross_profit=round(sum(max(0,r['gross']) for r in rows),2),gross_loss=round(sum(min(0,r['gross']) for r in rows),2),costs=round(sum(r['cost'] for r in rows),2),net=round(equity-1000,2),max_drawdown_pct=round(dd*100,2),trading_days=len(daily),days_ge_50=int((daily>=50).sum()),rows=rows)
a=test(0,cut);b=test(cut,n)
res={'hypothesis':'Trend pullback resumption after two countertrend candles and one breakout confirmation','rows':n,'split_time':str(t.iloc[cut]),'assumptions':'100 USD per $1 per lot; spread points *0.01; slippage 0.60 price roundtrip; commission $7/lot roundtrip; 1% equity risk; 0.01 minimum lot; stop first on OHLC ambiguity; no future features','development':{k:v for k,v in a.items() if k!='rows'},'holdout':{k:v for k,v in b.items() if k!='rows'}}
with open('v5_pullback_resumption_result.json','w') as f:json.dump(res,f,indent=2)
pd.DataFrame(b['rows']).to_csv('v5_pullback_resumption_holdout.csv',index=False)
print(json.dumps(res,indent=2))
