import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d['atr']=tr.rolling(20).mean();d['base']=d.atr.shift(1).rolling(96).median()
shock=(tr.shift(1)>2.2*d.base.shift(1))&(d.tick_volume.shift(1)>d.tick_volume.shift(2).rolling(96).median()*1.4)
inside=(d.high<d.high.shift(1))&(d.low>d.low.shift(1))
side=np.where(d.close.shift(1)>d.open.shift(1),1,-1)
signal=shock&inside&(d.atr>0)&(d.base>0)
cut=pd.Timestamp('2026-07-21',tz='UTC');out={}
for mode in ['continuation','fade']:
 for part in ['train','oos']:
  eq=1000.;peak=eq;dd=0.;rows=[];last=-1;opps=0
  for i in np.flatnonzero(signal):
   if i<120 or i+7>=len(d) or (d.dt.iloc[i]>=cut)!=(part=='oos'):continue
   opps+=1
   if i<=last or d.time.iloc[i+1]-d.time.iloc[i]!=900 or d.time.iloc[i+6]-d.time.iloc[i+1]!=4500:continue
   direction=int(side[i])*(1 if mode=='continuation' else -1)
   entry=float(d.open.iloc[i+1]);dist=max(2.5,float(d.atr.iloc[i])*1.15)
   lots=np.floor(eq*.01/(dist*100)*100)/100
   if lots<.01:continue
   lots=min(1.,lots);sl=entry-direction*dist;tp=entry+direction*dist*1.7
   ex=float(d.close.iloc[i+6]);last=i+6
   for j in range(i+1,i+7):
    hit_sl=d.low.iloc[j]<=sl if direction==1 else d.high.iloc[j]>=sl
    hit_tp=d.high.iloc[j]>=tp if direction==1 else d.low.iloc[j]<=tp
    if hit_sl or hit_tp:
     ex=sl if hit_sl else tp;last=j;break
   gross=(ex-entry)*direction*100*lots;cost=(.26+.60)*100*lots+7*lots
   net=gross-cost;eq+=net;peak=max(eq,peak);dd=max(dd,(peak-eq)/peak)
   rows.append({'day':str(d.dt.iloc[i].date()),'gross':gross,'cost':cost,'net':net})
  daily={day:sum(r['net'] for r in rows if r['day']==day) for day in {r['day'] for r in rows}}
  out[mode+'_'+part]={'opportunities':int(opps),'trades':int(len(rows)),'gross_wins':round(sum(r['gross'] for r in rows if r['gross']>0),2),'gross_losses':round(sum(r['gross'] for r in rows if r['gross']<0),2),'cost':round(sum(r['cost'] for r in rows),2),'net':round(sum(r['net'] for r in rows),2),'max_drawdown_pct':round(dd*100,2),'trading_days':int(len(daily)),'days_ge_50':int(sum(v>=50 for v in daily.values()))}
print(json.dumps(out,ensure_ascii=False,indent=2))
