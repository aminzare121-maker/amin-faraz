import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift()
tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.shift().rolling(32).median()
d['vol']=d.tick_volume.shift().rolling(32).median()
d['range']=d.high-d.low
signals=[]
for i in range(40,len(d)-7):
 if any(d.time.iloc[k]-d.time.iloc[k-1]!=900 for k in (i-1,i,i+1)):continue
 a=float(d.atr.iloc[i-1]);v=float(d.vol.iloc[i-1]);j=i-1
 if not np.isfinite(a) or a<=0 or not np.isfinite(v) or v<=0:continue
 if d['range'].iloc[j]<1.6*a or d.tick_volume.iloc[j]<1.5*v:continue
 if not(d.high.iloc[i]<d.high.iloc[j] and d.low.iloc[i]>d.low.iloc[j]):continue
 if d['range'].iloc[i]>.65*d['range'].iloc[j]:continue
 s=int(np.sign(d.close.iloc[j]-d.open.iloc[j]))
 if s:signals.append((i,s,a,float(d['range'].iloc[i])))
split=pd.Timestamp('2026-07-21',tz='UTC')
def run(direction,filtered,oos):
 equity=peak=1000.;dd=0.;wins=losses=cost=0.;n=0;last=-1;days={};eligible=0
 for i,s,a,r in signals:
  if bool(d.dt.iloc[i]>=split)!=oos:continue
  if filtered and r>.85*a:continue
  eligible+=1
  if i<=last:continue
  side=s*direction;entry=float(d.open.iloc[i+1]);stop=entry-side*1.2*a;target=entry+side*1.8*a
  lot=np.floor(min(.20,equity*.01/(1.2*a*100))*100)/100
  if lot<.01:continue
  price=float(d.close.iloc[i+6]);end=i+6
  for k in range(i+1,i+7):
   if d.time.iloc[k]-d.time.iloc[k-1]!=900:price=float(d.close.iloc[k-1]);end=k-1;break
   if (d.low.iloc[k]<=stop if side==1 else d.high.iloc[k]>=stop):price=stop;end=k;break
   if (d.high.iloc[k]>=target if side==1 else d.low.iloc[k]<=target):price=target;end=k;break
  last=end;gross=(price-entry)*side*100*lot;fee=(.26+.60)*100*lot+7*lot
  net=gross-fee;equity+=net;peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
  wins+=max(0,gross);losses+=min(0,gross);cost+=fee;n+=1
  day=str(d.dt.iloc[i].date());days[day]=days.get(day,0)+net
 return dict(opportunities=eligible,trades=n,gross_winners=round(wins,2),gross_losers=round(losses,2),costs=round(cost,2),net=round(equity-1000,2),max_drawdown_pct=round(dd*100,2),active_days=len(days),days_ge_50=sum(x>=50 for x in days.values()))
result={'rows':len(d),'split':'2026-07-21 UTC','costs':'spread .26/oz + slippage .30/oz per side + $7/lot round trip','results':{name:{'train':run(side,f,False),'oos':run(side,f,True)} for name,side,f in [('continuation',1,False),('reversal',-1,False),('continuation_compression_filter',1,True),('reversal_compression_filter',-1,True)]}}
print(json.dumps(result,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
