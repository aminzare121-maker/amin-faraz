"""Research-only failed-auction reversal. Input: Eplanet-derived OHLC JSONL. No broker connection."""
import pandas as pd, numpy as np, math, json, sys
d=pd.read_json(sys.argv[1],lines=True).rename(columns={'raw_open_epoch_no_certified_utc_offset':'time'}).sort_values('time').reset_index(drop=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.shift(1).rolling(20).mean()
d['hi']=d.high.shift(1).rolling(12).max();d['lo']=d.low.shift(1).rolling(12).min()
d['atr_med']=d.atr.shift(1).rolling(80).median()
cut=1781481600; results={}
for guard in (False,True):
 for split in ('train','test'):
  boundary=int(np.searchsorted(d.time.to_numpy(),cut));start,end=(100,boundary) if split=='train' else (boundary,len(d))
  eq=peak=1000.;dd=0.;busy=-1;opps=blocked=filtered=0;trades=[]
  for i in range(start,end-7):
   a=d.iloc[i];atr=a.atr
   if not np.isfinite(atr) or atr<=0 or not a.prior_bar_contiguous:continue
   side=1 if (a.low<a.lo-.12*atr and a.close>a.lo+.08*atr and a.close<a.hi) else (-1 if (a.high>a.hi+.12*atr and a.close<a.hi-.08*atr and a.close>a.lo) else 0)
   if not side:continue
   opps+=1
   if i<=busy:continue
   if guard and (a.range_abs>1.8*atr or atr>1.35*a.atr_med):filtered+=1;continue
   entry=float(d.open.iloc[i+1]);stop=float(a.low-.12*atr if side==1 else a.high+.12*atr);distance=side*(entry-stop)
   if distance<=0:blocked+=1;continue
   lots=min(.15,math.floor((eq*.01/(distance*100))*100)/100)
   if lots<.01:blocked+=1;continue
   target=entry+side*1.5*distance;price=float(d.close.iloc[i+6]);last=i+6;reason='timeout'
   for j in range(i+1,i+7):
    b=d.iloc[j];hs=b.low<=stop if side==1 else b.high>=stop;ht=b.high>=target if side==1 else b.low<=target
    if hs or ht:price=stop if hs else target;last=j;reason='stop' if hs else 'target';break
   gross=side*(price-entry)*lots*100;cost=lots*100*.90;net=gross-cost
   eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq);busy=last
   trades.append({'epoch':int(a.time),'lots':lots,'gross':round(gross,4),'cost':round(cost,4),'net':round(net,4),'reason':reason})
  days={}
  for t in trades:
   day=pd.to_datetime(t['epoch'],unit='s',utc=True).date().isoformat();days[day]=days.get(day,0)+t['net']
  results[f'{"guard" if guard else "base"}_{split}']={'opportunities':opps,'blocked_min_lot':blocked,'filtered':filtered,'trades':len(trades),'gross_profit':round(sum(max(0,t['gross']) for t in trades),2),'gross_loss':round(sum(min(0,t['gross']) for t in trades),2),'costs':round(sum(t['cost'] for t in trades),2),'net':round(sum(t['net'] for t in trades),2),'max_closed_drawdown':round(dd,2),'active_days':len(days),'days_ge_50':sum(v>=50 for v in days.values())}
print(json.dumps(results,indent=2))
