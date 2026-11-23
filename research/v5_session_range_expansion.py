"""Research only. Run: python v5_session_range_expansion.py Eplanet_M15.csv"""
import sys,json
import numpy as np,pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True);d['day']=d.dt.dt.date;d['hour']=d.dt.dt.hour
p=d.close.shift(1);tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1);d['volmed']=d.tick_volume.shift(1).rolling(32).median()
r=d[(d.hour>=7)&(d.hour<9)].groupby('day').agg(rhi=('high','max'),rlo=('low','min'),n=('high','size'))
d=d.join(r,on='day');d['range']=d.rhi-d.rlo
cut=pd.Timestamp('2026-06-15',tz='UTC');out={}
for guard in (False,True):
 result={}
 for split,mask in [('train',d.dt<cut),('test',d.dt>=cut)]:
  equity=1000.;peak=equity;dd=0.;busy=-1;used=set();opps=0;blocked=0;trades=[]
  ids=np.flatnonzero(mask.to_numpy());first,last=int(ids[0]),int(ids[-1])
  for i in range(max(first,60),last-12):
   a=d.iloc[i];b=d.iloc[i-1]
   if not (9<=a.hour<15 and a.n>=7 and np.isfinite(a.atr) and a.atr>0 and np.isfinite(a.volmed)):continue
   if a.day in used:continue
   side=1 if a.close>a.rhi and b.close<=b.rhi else (-1 if a.close<a.rlo and b.close>=b.rlo else 0)
   if not side or abs(a.close-a.open)<.35*a.atr or a.tick_volume<1.15*a.volmed:continue
   if not (.7*a.atr<=a['range']<=5*a.atr):continue
   opps+=1
   if i<=busy:continue
   if guard and (a.spread>30 or tr.iloc[i]>2.2*a.atr or a.hour>=13):continue
   entry=float(d.open.iloc[i+1]);sd=max(.75*a.atr,abs(entry-(a.rhi if side==1 else a.rlo))+.15*a.atr)
   lots=min(.15,np.floor((equity*.01/(sd*100))*100)/100)
   if lots<.01:blocked+=1;continue
   used.add(a.day);stop=entry-side*sd;target=entry+side*1.8*sd;end=i+8;exitprice=float(d.close.iloc[end]);why='time'
   for j in range(i+1,i+9):
    c=d.iloc[j];s=(c.low<=stop if side==1 else c.high>=stop);t=(c.high>=target if side==1 else c.low<=target)
    if s or t:exitprice=stop if s else target;end=j;why='stop' if s else 'target';break
   gross=side*(exitprice-entry)*lots*100;cost=lots*100*(float(a.spread)*.01+.60)
   net=gross-cost;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity);busy=end
   trades.append(dict(date=str(a.day),signal_time=str(a['dt']),side=side,lots=round(lots,2),gross=round(gross,4),cost=round(cost,4),net=round(net,4),exit=why))
  days={}
  for x in trades:days[x['date']]=days.get(x['date'],0)+x['net']
  result[split]=dict(opportunities=opps,risk_blocked=blocked,trades=len(trades),gross_profit=round(sum(max(0,x['gross']) for x in trades),2),gross_loss=round(sum(min(0,x['gross']) for x in trades),2),costs=round(sum(x['cost'] for x in trades),2),net=round(sum(x['net'] for x in trades),2),max_closed_drawdown=round(dd,2),days_ge_50=sum(x>=50 for x in days.values()),active_days=len(days),trades_detail=trades)
 out['guard' if guard else 'base']=result
print(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item()))
