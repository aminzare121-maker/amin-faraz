"""Research-only one-bar candle persistence test. CSV input; no MT5 orders."""
import pandas as pd,numpy as np,math,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
p=d.close.shift();tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.shift(1).rolling(20).mean();d['med']=d.atr.shift(1).rolling(100).median()
d['rng']=d.high-d.low;d['body']=(d.close-d.open).abs();d['vm']=d.tick_volume.shift(1).rolling(40).median()
cut=1781481600;out={}
for guard in (False,True):
 for split in ('train','test'):
  eq=peak=1000.;dd=0;busy=-1;opp=blocked=filtered=0;trades=[]
  for i in range(110,len(d)-1):
   a,b=d.iloc[i],d.iloc[i+1]
   if (a.time>=cut)!=(split=='test') or (b.time>=cut)!=(split=='test') or b.time-a.time!=900 or not np.isfinite(a.atr) or a.atr<=0:continue
   side=1 if a.close>a.open else -1
   wick=a.high-a.close if side==1 else a.close-a.low
   if not (a.body>=.65*a.rng and .65*a.atr<=a.rng<=2.3*a.atr and wick<=.12*a.rng and a.tick_volume>=a.vm):continue
   opp+=1
   if i<=busy:continue
   if guard and (a.atr>1.2*a.med or a.rng>1.5*a.atr):filtered+=1;continue
   entry=float(b.open);dist=.8*float(a.atr);stop=entry-side*dist;target=entry+side*dist
   lots=math.floor(min(.2,eq*.01/(dist*100))*100)/100
   if lots<.01:blocked+=1;continue
   hitstop=b.low<=stop if side==1 else b.high>=stop
   hittarget=b.high>=target if side==1 else b.low<=target
   price=stop if hitstop else target if hittarget else float(b.close)
   gross=side*(price-entry)*lots*100;cost=lots*100*.9;net=gross-cost
   eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq);busy=i+1
   trades.append((int(a.time),gross,cost,net))
  days={}
  for t,g,c,n in trades:
   day=pd.to_datetime(t,unit='s',utc=True).date().isoformat();days[day]=days.get(day,0)+n
  out[f'{"guard" if guard else "base"}_{split}']={'opportunities':opp,'blocked_min_lot':blocked,'filtered':filtered,'trades':len(trades),'gross_profit':round(sum(max(0,x[1]) for x in trades),2),'gross_loss':round(sum(min(0,x[1]) for x in trades),2),'costs':round(sum(x[2] for x in trades),2),'net':round(sum(x[3] for x in trades),2),'max_closed_drawdown':round(dd,2),'active_days':len(days),'days_ge_50':sum(x>=50 for x in days.values())}
print(json.dumps(out,indent=2))
