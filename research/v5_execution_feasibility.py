import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift(1)
tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1)
d['hi']=d.high.shift(1).rolling(24).max();d['lo']=d.low.shift(1).rolling(24).min()
d['vmed']=d.tick_volume.shift(1).rolling(24).median()
cut=pd.Timestamp('2026-06-15',tz='UTC');out={}
for name,sd,tp,hold in [('wide_reference',1.4,2.2,8),('near_invalidation',.7,1.4,5),('near_with_shock_guard',.7,1.4,5)]:
 out[name]={}
 for split in ['train','test']:
  ids=np.flatnonzero((d.dt<cut if split=='train' else d.dt>=cut).to_numpy())
  equity=1000.;peak=equity;dd=0.;busy=-1;opps=blocked=guarded=0;trades=[]
  for i in range(max(30,int(ids[0])),int(ids[-1])-hold):
   a=d.iloc[i];atr=float(a.atr)
   if not np.isfinite(atr) or atr<=0:continue
   side=1 if a.close>a.hi+.1*atr else (-1 if a.close<a.lo-.1*atr else 0)
   if not side or a.tick_volume<1.35*a.vmed:continue
   opps+=1
   if i<=busy:continue
   if name=='near_with_shock_guard' and (a.high-a.low>2.2*atr or a.spread>35):guarded+=1;continue
   entry=float(d.open.iloc[i+1]);distance=sd*atr
   lots=min(.15,np.floor((max(0,equity)*.0075/(distance*100))*100)/100)
   if lots<.01:blocked+=1;continue
   stop=entry-side*distance;target=entry+side*tp*atr;end=i+hold;exitprice=float(d.close.iloc[end])
   for j in range(i+1,i+hold+1):
    b=d.iloc[j];s=b.low<=stop if side==1 else b.high>=stop;t=b.high>=target if side==1 else b.low<=target
    if s or t:exitprice=stop if s else target;end=j;break
   gross=side*(exitprice-entry)*lots*100;cost=lots*100*(float(a.spread)*.01+.60);net=gross-cost
   equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);busy=end
   trades.append((str(a['dt'].date()),gross,cost,net))
  days={}
  for date,g,c,n in trades:days[date]=days.get(date,0)+n
  out[name][split]=dict(opportunities=opps,blocked_min_lot=blocked,guard_rejected=guarded,trades=len(trades),gross_profit=round(sum(max(0,x[1]) for x in trades),2),gross_loss=round(sum(min(0,x[1]) for x in trades),2),costs=round(sum(x[2] for x in trades),2),net=round(sum(x[3] for x in trades),2),max_closed_drawdown=round(dd,2),active_days=len(days),days_ge_50=sum(v>=50 for v in days.values()))
print(json.dumps(out,indent=2,default=lambda x:x.item()))
