"""Reproduce V5 compression breakout. Requires private Eplanet CSV supplied via --csv. Research only."""
import argparse, json, numpy as np, pandas as pd
p=argparse.ArgumentParser();p.add_argument('--csv',required=True);a=p.parse_args()
d=pd.read_csv(a.csv).sort_values('time').drop_duplicates('time').reset_index(drop=True)
o,h,l,c=[d[k].to_numpy(float) for k in ('open','high','low','close')];n=len(d)
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));tr[0]=h[0]-l[0]
atr=pd.Series(tr).rolling(40).mean().shift(1).to_numpy();split=int(n*.6)
def run(start,end,ratio,guard=False):
 eq=1000.;peak=eq;dd=0;opp=0;ledger=[];i=max(start,50)
 while i<min(end,n-10):
  av=atr[i];hi=max(h[i-8:i]);lo=min(l[i-8:i]);width=hi-lo
  if not np.isfinite(av) or av<=0 or not (.35*av<=width<=ratio*av):i+=1;continue
  side=1 if c[i]>hi+.08*av else -1 if c[i]<lo-.08*av else 0
  if not side:i+=1;continue
  opp+=1
  if guard and (tr[i]>2.5*av or d.spread.iloc[i]>30):i+=1;continue
  entry=o[i+1];stop=av;target=2*av
  lot=np.floor(min(.15,eq*.01/(stop*100))/.01)*.01
  if lot<.01:i+=1;continue
  jexit=min(i+8,end-1);ex=c[jexit]
  for j in range(i+1,min(i+9,end)):
   if (side==1 and l[j]<=entry-stop) or (side==-1 and h[j]>=entry+stop):ex=entry-side*stop;jexit=j;break
   if (side==1 and h[j]>=entry+target) or (side==-1 and l[j]<=entry-target):ex=entry+side*target;jexit=j;break
  gross=(ex-entry)*side*lot*100;cost=lot*(7+100*(.26+.60));net=gross-cost
  eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq)
  ledger.append(dict(time=int(d.time.iloc[jexit]),lot=float(lot),gross=float(gross),cost=float(cost),net=float(net)))
  i=jexit+1
 days={}
 for x in ledger:
  day=pd.to_datetime(x['time'],unit='s',utc=True).strftime('%Y-%m-%d');days[day]=days.get(day,0)+x['net']
 return dict(opportunities=opp,trades=len(ledger),gross=round(sum(x['gross'] for x in ledger),2),costs=round(sum(x['cost'] for x in ledger),2),net=round(eq-1000,2),drawdown=round(dd,2),days_over_50=sum(v>=50 for v in days.values()))
training={str(v):run(50,split,v) for v in (.9,1.2,1.5,1.8)}
choice=max((.9,1.2,1.5,1.8),key=lambda v:training[str(v)]['net'])
print(json.dumps(dict(rows=n,choice=choice,training=training,holdout=run(split,n,choice),guard=run(split,n,choice,True)),indent=2))
