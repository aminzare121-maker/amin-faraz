# V5 path-efficiency persistence; private CSV remains local. Python 3, pandas, numpy.
import pandas as pd, numpy as np, json, sys
from pathlib import Path
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
for c in ['open','high','low','close','spread']: d[c]=pd.to_numeric(d[c])
tr=np.maximum(d.high-d.low,np.maximum(abs(d.high-d.close.shift()),abs(d.low-d.close.shift())))
atr=tr.shift(1).rolling(32).median()
er=abs(d.close-d.close.shift(8))/d.close.diff().abs().rolling(8).sum()
N=len(d); split=int(N*.6); candidates=[]
for i in range(45,N-7):
 a=atr.iloc[i];e=er.iloc[i];side=np.sign(d.close.iloc[i]-d.close.iloc[i-8])
 if not np.isfinite(a) or a<=0 or not np.isfinite(e) or side==0:continue
 if e<.72 or abs(d.close.iloc[i]-d.close.iloc[i-8])<1.1*a:continue
 if abs(d.close.iloc[i]-d.open.iloc[i])>1.4*a:continue
 if d.time.iloc[i+1]-d.time.iloc[i]>1800:continue
 candidates.append((i+1,int(side),float(a),float(e)))
def test(guard=False):
 cash=1000.;peak=1000.;dd=0.;used=0;opps=0;log=[]
 for j,side,a,e in candidates:
  if j<split or j<=used:continue
  opps+=1;spread=float(d.spread.iloc[j])/100
  if guard and (spread/a>.045 or a>8 or e<.82):continue
  stop=1.3*a;target=2*a
  lots=np.floor(min(.05,cash*.01/(100*stop))/.01)*.01
  if lots<.01:continue
  entry=float(d.open.iloc[j]);end=min(j+5,N-1);out=float(d.close.iloc[end]);reason='time'
  for k in range(j,end+1):
   sl=d.low.iloc[k]<=entry-stop if side==1 else d.high.iloc[k]>=entry+stop
   tp=d.high.iloc[k]>=entry+target if side==1 else d.low.iloc[k]<=entry-target
   if sl or tp:
    out=entry-side*stop if sl else entry+side*target
    reason='stop' if sl else 'target';end=k;break
  gross=side*(out-entry)*100*lots;cost=(spread+.30)*100*lots+7*lots;net=gross-cost
  cash+=net;peak=max(peak,cash);dd=max(dd,peak-cash);used=end
  log.append(dict(time=int(d.time.iloc[j]),lot=float(lots),gross=round(gross,4),cost=round(cost,4),net=round(net,4),reason=reason))
 days={}
 for t in log:
  day=str(pd.to_datetime(t['time'],unit='s',utc=True).date());days[day]=days.get(day,0)+t['net']
 return dict(opportunities=int(opps),trades=len(log),gross=round(sum(t['gross'] for t in log),2),cost=round(sum(t['cost'] for t in log),2),net=round(sum(t['net'] for t in log),2),max_closed_drawdown=round(dd,2),days_ge_50=int(sum(x>=50 for x in days.values())),test_days=int(pd.to_datetime(d.time.iloc[split:],unit='s',utc=True).dt.date.nunique()),log=log)
print(json.dumps(dict(base=test(),guard=test(True)),indent=2))
