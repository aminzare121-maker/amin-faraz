# Research hypothesis: high-volume impulse exhaustion vs continuation.
# Run with: python v5_impulse_exhaustion.py /path/to/private/Eplanet_M15_20251105_20261105_merged.csv
import pandas as pd,numpy as np,json,sys
D=pd.read_csv(sys.argv[1]);n=len(D)
o,h,l,c=[D[k].to_numpy(float) for k in ['open','high','low','close']]
t=pd.to_datetime(D.time,unit='s',utc=True);prev=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,abs(h-prev),abs(l-prev)])
atr=pd.Series(tr).shift(1).rolling(40).median().to_numpy()
vol=D.tick_volume.to_numpy(float);vm=pd.Series(vol).shift(1).rolling(40).median().to_numpy()
shock=(abs(c-o)>2.0*atr)&(vol>1.6*vm)&(abs(c-o)>0.65*(h-l))
cut=int(n*.7)
def run(a,b,mode):
 eq=1000.;peak=eq;maxdd=0.;trades=[];opportunities=0;i=max(a,50)
 while i<b-9:
  if not shock[i] or not np.isfinite(atr[i]):i+=1;continue
  opportunities+=1;side=int(np.sign(c[i]-o[i]))*(1 if mode=='follow' else -1)
  entry=o[i+1];dist=max(1.,atr[i]*1.3);costper=(D.spread.iloc[i+1]*.01+.6)*100+7
  lots=np.floor(min(1.,eq*.01/(dist*100+costper))*100)/100
  if lots<.01:i+=1;continue
  end=min(i+8,b-1);exitprice=c[end];reason='timeout'
  for j in range(i+1,end+1):
   if (l[j]<=entry-dist if side==1 else h[j]>=entry+dist):
    exitprice=entry-side*dist;end=j;reason='stop';break
   if (h[j]>=entry+side*dist*1.5 if side==1 else l[j]<=entry+side*dist*1.5):
    exitprice=entry+side*dist*1.5;end=j;reason='target';break
  gross=side*(exitprice-entry)*100*lots;cost=costper*lots;pnl=gross-cost
  eq+=pnl;peak=max(peak,eq);maxdd=max(maxdd,(peak-eq)/peak)
  trades.append(dict(time=str(t[i]),side=side,lots=lots,gross=gross,cost=cost,pnl=pnl,reason=reason));i=end+1
 days=pd.DataFrame(trades).assign(day=lambda x:x.time.str[:10]).groupby('day').pnl.sum() if trades else pd.Series(dtype=float)
 return dict(opportunities=opportunities,trades=len(trades),gross_wins=round(sum(max(0,x['gross']) for x in trades),2),gross_losses=round(sum(min(0,x['gross']) for x in trades),2),costs=round(sum(x['cost'] for x in trades),2),net=round(eq-1000,2),max_dd_pct=round(maxdd*100,2),active_days=len(days),days_ge_50=int((days>=50).sum()),win_rate_pct=round(100*sum(x['pnl']>0 for x in trades)/len(trades),2) if trades else 0)
result={'hypothesis':'High-volume large impulse: exhaustion reversal vs continuation','bars':n,'cut_utc':str(t[cut]),'cost_model':'spread points * .01 + $0.60 price roundtrip slippage, $7 per lot roundtrip commission; $100/price unit/lot; risk 1%; stop first; next bar open','methods':{m:{'development':run(0,cut,m),'holdout':run(cut,n,m)} for m in ['reverse','follow']}}
print(json.dumps(result,indent=2))
