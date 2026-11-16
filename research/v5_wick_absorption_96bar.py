import pandas as pd,numpy as np,json,sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
r=d.high-d.low;lo=np.minimum(d.open,d.close)-d.low;hi=d.high-np.maximum(d.open,d.close)
med=r.shift(1).rolling(96,min_periods=96).median();vol=d.tick_volume.shift(1).rolling(96,min_periods=96).median()
sig=(r>1.5*med)&(d.tick_volume>1.2*vol)&(r>0)&((lo/r>.62)|(hi/r>.62))
cut=pd.Timestamp('2026-07-21',tz='UTC');out={}
for mode in ['reversal','continuation']:
 for part in ['train','oos']:
  eq=1000.;peak=eq;dd=0.;rows=[];last=-1;opps=0
  for i in np.flatnonzero(sig):
   if i<100 or i+5>=len(d) or (d.dt.iloc[i]>=cut)!=(part=='oos'):continue
   opps+=1
   if i<=last or d.time.iloc[i+1]-d.time.iloc[i]!=900 or d.time.iloc[i+5]-d.time.iloc[i+1]!=3600:continue
   direction=(1 if lo.iloc[i]>hi.iloc[i] else -1)*(1 if mode=='reversal' else -1)
   entry=float(d.open.iloc[i+1]);dist=max(2.,float(med.iloc[i])*.75)
   lots=np.floor(max(0,eq)*.01/(dist*100)*100)/100
   if lots<.01:continue
   lots=min(.5,lots);sl=entry-direction*dist;tp=entry+direction*dist*1.5
   ex=float(d.close.iloc[i+5]);last=i+5
   for j in range(i+1,i+6):
    slhit=d.low.iloc[j]<=sl if direction==1 else d.high.iloc[j]>=sl
    tphit=d.high.iloc[j]>=tp if direction==1 else d.low.iloc[j]<=tp
    if slhit or tphit:ex=sl if slhit else tp;last=j;break
   gross=(ex-entry)*direction*100*lots
   cost=(.26+.60)*100*lots+7*lots
   net=gross-cost;eq+=net;peak=max(peak,eq);dd=max(dd,peak-eq)
   rows.append({'day':str(d.dt.iloc[i].date()),'gross':gross,'cost':cost,'net':net,'lot':lots})
  days={x['day'] for x in rows};daily={day:sum(x['net'] for x in rows if x['day']==day) for day in days}
  out[mode+'_'+part]={'opportunities':int(opps),'trades':len(rows),'gross_wins':round(sum(x['gross'] for x in rows if x['gross']>0),2),'gross_losses':round(sum(x['gross'] for x in rows if x['gross']<0),2),'cost':round(sum(x['cost'] for x in rows),2),'net':round(sum(x['net'] for x in rows),2),'max_drawdown_usd':round(dd,2),'final_equity':round(eq,2),'active_days':len(days),'days_ge_50':int(sum(x>=50 for x in daily.values()))}
print(json.dumps(out,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
