import pandas as pd,numpy as np,json
d=pd.read_csv('Eplanet_M15_20251105_20261105_merged.csv').sort_values('time').drop_duplicates('time').reset_index(drop=True)
c=d.close.to_numpy();o=d.open.to_numpy();h=d.high.to_numpy();l=d.low.to_numpy();n=len(d);split=int(.6*n)
imp=c-np.roll(c,6);path=pd.Series(np.abs(np.diff(c,prepend=c[0]))).rolling(6).sum().to_numpy()
eff=np.abs(imp)/np.maximum(path,1e-9);atr=pd.Series(h-l).rolling(96).median().shift(1).to_numpy()
sig=(eff>.78)&(np.abs(imp)>1.1*atr)&(np.abs(imp)<2.8*atr);sig[:100]=False
def run(guard=False):
 equity=1000.;peak=equity;dd=0.;ledger=[];opp=0;i=split
 while i<n-5:
  j=i-1
  if not sig[j] or not np.isfinite(atr[j]):i+=1;continue
  opp+=1;side=1 if imp[j]>0 else -1;dist=float(atr[j])
  if guard and (1.46/dist>.12 or h[j]-l[j]>2*dist):i+=1;continue
  lots=np.floor(equity*.01/(dist*100)*100)/100
  if lots<.01:i+=1;continue
  lots=min(lots,.1);qty=lots*100;entry=o[i];sl=entry-side*dist;tp=entry+side*1.8*dist;exitp=None
  for k in range(i,min(i+4,n)):
   if side==1:
    if o[k]<=sl:exitp=o[k]
    elif o[k]>=tp:exitp=tp
    elif l[k]<=sl:exitp=sl
    elif h[k]>=tp:exitp=tp
   else:
    if o[k]>=sl:exitp=o[k]
    elif o[k]<=tp:exitp=tp
    elif h[k]>=sl:exitp=sl
    elif l[k]<=tp:exitp=sl
   if exitp is not None:break
  if exitp is None:exitp=c[min(i+3,n-1)];k=min(i+3,n-1)
  gross=(exitp-entry)*side*qty;cost=qty*1.46;net=gross-cost;equity+=net;peak=max(peak,equity);dd=max(dd,peak-equity)
  ledger.append(dict(time=int(d.time.iloc[i]),lots=float(lots),gross=float(gross),cost=float(cost),net=float(net)));i=k+1
 days={}
 for x in ledger:
  day=pd.to_datetime(x['time'],unit='s',utc=True).date().isoformat();days[day]=days.get(day,0)+x['net']
 return dict(opportunities=opp,trades=len(ledger),gross=round(sum(x['gross'] for x in ledger),2),cost=round(sum(x['cost'] for x in ledger),2),net=round(sum(x['net'] for x in ledger),2),max_closed_drawdown=round(dd,2),days_ge_50=sum(v>=50 for v in days.values()),ledger=ledger)
print(json.dumps(dict(bars=n,split=split,base=run(),guard=run(True)),indent=2))
