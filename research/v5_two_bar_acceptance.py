"""Two-bar acceptance after quiet range. Research-only, no orders."""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean().shift(1)
d['quiet']=tr.shift(2).rolling(8).mean()/tr.shift(2).rolling(48).mean()
d['sprmed']=d.spread.shift(1).rolling(48).median()
cut=pd.Timestamp('2026-06-15',tz='UTC');out={}
for guard in (False,True):
 equity=1000.;busy=-1;trades=[];opps={'train':0,'test':0};blocked={'train':0,'test':0}
 for i in range(60,len(d)-9):
  a=d.iloc[i];b=d.iloc[i-1];atr=a.atr
  if not np.isfinite(atr) or atr<=0 or not np.isfinite(a.quiet):continue
  side=1 if a.close>a.open and b.close>b.open else (-1 if a.close<a.open and b.close<b.open else 0)
  if not side or a.quiet>=.85:continue
  if side*(a.close-b.close)<.35*atr or side*(b.close-d.close.iloc[i-2])<.15*atr:continue
  if side==1 and (a.close-a.low)/max(.01,a.high-a.low)<.72:continue
  if side==-1 and (a.high-a.close)/max(.01,a.high-a.low)<.72:continue
  split='test' if a['dt']>=cut else 'train';opps[split]+=1
  if i<=busy:continue
  if guard and (a.spread>max(35,1.25*a.sprmed) or tr.iloc[i]>2*atr or a['dt'].hour in (21,22,23)):continue
  entry=float(d.open.iloc[i+1]);stopdist=.8*atr;targetdist=1.6*atr
  lots=min(.15,np.floor((max(0,equity)*.01/(stopdist*100))*100)/100)
  if lots<.01:blocked[split]+=1;continue
  stop=entry-side*stopdist;target=entry+side*targetdist
  exitprice=float(d.close.iloc[i+8]);end=i+8
  for j in range(i+1,i+9):
   c=d.iloc[j];hitstop=(c.low<=stop if side==1 else c.high>=stop);hittarget=(c.high>=target if side==1 else c.low<=target)
   if hitstop or hittarget:exitprice=stop if hitstop else target;end=j;break
  gross=side*(exitprice-entry)*lots*100;cost=lots*100*(.60+float(a.spread)*.01);net=gross-cost
  equity+=net;busy=end
  trades.append(dict(date=str(a['dt'].date()),split=split,gross=gross,cost=cost,net=net,lots=float(lots)))
 out['guard' if guard else 'base']={}
 for split in ('train','test'):
  t=[x for x in trades if x['split']==split];v=np.array([x['net'] for x in t]);curve=np.r_[0,v.cumsum()];days={}
  for x in t:days[x['date']]=days.get(x['date'],0)+x['net']
  out['guard' if guard else 'base'][split]=dict(opportunities=opps[split],risk_blocked=blocked[split],trades=len(t),gross_profit=round(sum(max(0,x['gross']) for x in t),2),gross_loss=round(sum(min(0,x['gross']) for x in t),2),cost=round(sum(x['cost'] for x in t),2),net=round(v.sum(),2),max_closed_drawdown=round(float(max(np.maximum.accumulate(curve)-curve)),2),days_ge_50=sum(x>=50 for x in days.values()),active_days=len(days))
print(json.dumps(out,indent=2,default=lambda x:x.item()))
