import io, zipfile, sys, json
import numpy as np
import pandas as pd
z=zipfile.ZipFile(sys.argv[1])
names=[x for x in z.namelist() if 'M15-' in x and x.endswith('.csv')]
d=pd.concat([pd.read_csv(io.BytesIO(z.read(x))) for x in names],ignore_index=True).drop_duplicates('time').sort_values('time').reset_index(drop=True)
o,h,l,c=[d[k].to_numpy(float) for k in ('open','high','low','close')]
n=len(d); t=pd.to_datetime(d.time,unit='s',utc=True); spread=d.spread.to_numpy(float)*.01
prev=np.r_[np.nan,c[:-1]]
tr=np.maximum.reduce([h-l,np.abs(h-prev),np.abs(l-prev)])
atr=pd.Series(tr).shift(1).rolling(20).median().to_numpy()
high4=pd.Series(h).shift(1).rolling(4).max().to_numpy()
low4=pd.Series(l).shift(1).rolling(4).min().to_numpy()
signal=np.zeros(n,dtype=int)
for i in range(40,n-15):
 if not np.isfinite(atr[i]) or atr[i]<=0 or high4[i]-low4[i]>1.5*atr[i]:continue
 if c[i]>high4[i] and c[i]>o[i]:signal[i]=1
 elif c[i]<low4[i] and c[i]<o[i]:signal[i]=-1
def run(a,b,session):
 eq=1000.;peak=eq;dd=0.;rows=[];opps=0;i=max(a,40)
 while i<b-15:
  s=signal[i]
  if not s or (session and not 12<=t[i].hour<18):i+=1;continue
  opps+=1;entry=o[i+1];dist=max(1.,1.2*atr[i]);cost_per_lot=(spread[i+1]+.6)*100+7
  lots=np.floor(min(1.,max(0,eq)*.01/(dist*100+cost_per_lot))*100)/100
  if lots<.01:i+=1;continue
  last=min(i+12,b-1);ex=c[last];reason='timeout'
  for j in range(i+1,last+1):
   if (l[j]<=entry-dist if s==1 else h[j]>=entry+dist):ex=entry-s*dist;last=j;reason='stop';break
   if (h[j]>=entry+1.5*dist if s==1 else l[j]<=entry-1.5*dist):ex=entry+s*1.5*dist;last=j;reason='target';break
  gross=s*(ex-entry)*100*lots;cost=cost_per_lot*lots;pnl=gross-cost
  eq+=pnl;peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
  rows.append(dict(time=str(t[i]),side=int(s),lots=float(lots),gross=float(gross),cost=float(cost),pnl=float(pnl),reason=reason));i=last+1
 days=pd.DataFrame(rows).assign(day=lambda x:x.time.str[:10]).groupby('day').pnl.sum() if rows else pd.Series(dtype=float)
 return dict(opportunities=opps,trades=len(rows),wins=sum(x['pnl']>0 for x in rows),gross_wins=round(sum(max(0,x['gross']) for x in rows),2),gross_losses=round(sum(min(0,x['gross']) for x in rows),2),costs=round(sum(x['cost'] for x in rows),2),net=round(eq-1000,2),max_dd_pct=round(dd*100,2),active_days=len(days),days_net_ge_50=int((days>=50).sum()),rows=rows)
cut=int(n*.7);results={}
for tag,session in [('all_hours',False),('liquid_hours_12_18_utc',True)]:
 results[tag]={}
 for part,(a,b) in [('development',(0,cut)),('holdout',(cut,n))]:
  r=run(a,b,session)
  pd.DataFrame(r.pop('rows')).to_csv('v5_compression_'+tag+'_'+part+'.csv',index=False)
  results[tag][part]=r
out={'hypothesis':'Compression breakout; 12-18 UTC as independent loss filter','n_bars':n,'split':str(t[cut]),'assumptions':'$100/price unit/lot; spread points*.01; 0.60 price slippage roundtrip; $7/lot roundtrip; 1% risk; min .01 lot; stop first; next-bar open; 12-bar timeout','results':results}
with open('v5_compression_session_result.json','w') as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
