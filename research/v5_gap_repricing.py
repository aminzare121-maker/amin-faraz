"""Eplanet gap repricing research. python v5_gap_repricing.py PRIVATE_CSV output.json"""
import sys,json,math,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
p=Path(sys.argv[1])
d=pd.read_csv(p).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['atr']=(d.high-d.low).shift(1).rolling(20).mean()
cut=pd.Timestamp('2026-06-15',tz='UTC')
end=pd.Timestamp('2026-11-06',tz='UTC')
def run(part,guard):
 eq=peak=1000.;gp=gl=cost=dd=0.;opp=blocked=0;ledger=[];i=21
 while i<len(d)-13:
  r=d.iloc[i];old=d.iloc[i-1];atr=float(r.atr);gap=float(r.open-old.close);elapsed=int(r.time-old.time)
  if not ((r['dt']<cut if part=='train' else cut<=r['dt']<end)) or not (1800<=elapsed<=259200 and np.isfinite(atr) and atr>0 and abs(gap)>=.45*atr):
   i+=1;continue
  opp+=1;side=-1 if gap>0 else 1
  confirm=side*(r.close-r.open)>0 and abs(r.close-r.open)>=.08*atr
  if not confirm or d.iloc[i+1].time-r.time!=900:
   blocked+=1;i+=1;continue
  if guard and (abs(gap)>1.8*atr or r.spread>35 or r.high-r.low>2.5*atr):
   blocked+=1;i+=1;continue
  entry=float(d.iloc[i+1].open);stop=entry-side*1.2*atr;target=float(old.close)
  if side*(target-entry)<=0:
   blocked+=1;i+=1;continue
  lots=min(.10,math.floor(eq*.01/(1.2*atr*100)*100)/100)
  if lots<.01:
   blocked+=1;i+=1;continue
  ex=float(d.iloc[i+12].close);last=i+12
  for j in range(i+1,i+13):
   b=d.iloc[j];sl=b.low<=stop if side==1 else b.high>=stop;tp=b.high>=target if side==1 else b.low<=target
   if sl or tp:
    ex=stop if sl else target;last=j;break
  gross=side*(ex-entry)*100*lots;fee=(float(r.spread)*.01+.30)*100*lots;net=gross-fee
  eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq)
  gp+=max(gross,0);gl+=min(gross,0);cost+=fee
  ledger.append({'time':str(d.iloc[i+1]['dt']),'lot':lots,'gross':round(gross,4),'cost':round(fee,4),'net':round(net,4),'gap':round(gap,3)})
  i=last+1
 days={}
 for t in ledger:days[t['time'][:10]]=days.get(t['time'][:10],0)+t['net']
 return dict(opportunities=opp,blocked=blocked,trades=len(ledger),gross_profit=round(gp,2),gross_loss=round(gl,2),cost=round(cost,2),net=round(eq-1000,2),max_closed_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in days.values()),days_traded=len(days),ledger=ledger)
res={k:{v:run(k,v=='guard') for v in ('base','guard')} for k in ('train','oos')}
res['meta']={'rows':len(d),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':'REJECT; no orders','cost_model':'spread points*0.01 USD/oz + 0.30 USD/oz, 100oz/lot assumed'}
Path(sys.argv[2]).write_text(json.dumps(res,indent=2))
print(json.dumps({k:{v:{a:b for a,b in val.items() if a!='ledger'} for v,val in res[k].items()} for k in ('train','oos')},indent=2))
