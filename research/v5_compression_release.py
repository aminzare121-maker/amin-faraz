import json,sys,numpy as np,pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift(1);tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1);d['vm']=d.tick_volume.shift(1).rolling(40).median()
d['hi']=d.high.shift(1).rolling(4).max();d['lo']=d.low.shift(1).rolling(4).min()
d['compress']=(d.hi-d.lo)<1.15*d.atr
cut=pd.Timestamp('2026-06-15',tz='UTC');out={}
for variant in ['base','shock_guard']:
 out[variant]={}
 for split in ['train','test']:
  ids=np.flatnonzero((d.dt<cut if split=='train' else d.dt>=cut).to_numpy())
  equity=peak=1000.;dd=0.;busy=-1;opps=blocked=guarded=0;trades=[]
  for i in range(max(40,int(ids[0])),int(ids[-1])-8):
   a=d.iloc[i];atr=a.atr
   if not np.isfinite(atr) or atr<=0 or not a.compress:continue
   side=1 if a.close>a.hi else (-1 if a.close<a.lo else 0)
   if not side or np.sign(a.close-a.open)!=side or abs(a.close-a.open)<.35*atr or a.tick_volume<1.1*a.vm:continue
   opps+=1
   if i<=busy:continue
   if variant=='shock_guard' and (a.high-a.low>1.7*atr or a.spread>45):guarded+=1;continue
   entry=float(d.open.iloc[i+1]);lots=min(.15,np.floor(equity*.0075/(atr*100)*100)/100)
   if lots<.01:blocked+=1;continue
   stop=entry-side*atr;target=entry+side*1.8*atr;end=i+8;ex=float(d.close.iloc[end])
   for j in range(i+1,i+9):
    b=d.iloc[j];s=b.low<=stop if side==1 else b.high>=stop;t=b.high>=target if side==1 else b.low<=target
    if s or t:ex=stop if s else target;end=j;break
   gross=side*(ex-entry)*lots*100;cost=lots*100*(a.spread*.01+.60);net=gross-cost
   equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);busy=end
   trades.append((str(a['dt'].date()),gross,cost,net))
  days={}
  for date,g,c,n in trades:days[date]=days.get(date,0)+n
  out[variant][split]=dict(opportunities=opps,blocked_min_lot=blocked,guard_rejected=guarded,trades=len(trades),gross_profit=round(sum(max(0,x[1]) for x in trades),2),gross_loss=round(sum(min(0,x[1]) for x in trades),2),costs=round(sum(x[2] for x in trades),2),net=round(sum(x[3] for x in trades),2),max_closed_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in days.values()))
print(json.dumps(out,indent=2,default=lambda x:x.item()))
