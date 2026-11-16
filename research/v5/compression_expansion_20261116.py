import pandas as pd
import numpy as np
import json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
r=d.high-d.low
m=r.rolling(96,min_periods=96).median().shift(1)
signal=(r.shift(1).rolling(4).mean()<.65*m)&(r>1.35*m)&((d.close-d.open).abs()>.65*r)
side=np.sign(d.close-d.open)
cut=int(d.time.quantile(.7))
records=[]; equity=1000.; last=-10
for i in np.flatnonzero(signal.to_numpy()):
    if i+5>=len(d) or i<=last+4: continue
    if d.time.iloc[i+1]-d.time.iloc[i]>1800 or d.time.iloc[i+4]-d.time.iloc[i+1]>4500: continue
    last=i
    dist=max(2*float(m.iloc[i]),1.)
    lots=min(.1,max(.01,np.floor((equity*.01/(dist*100))/.01)*.01))
    if dist*100*lots>equity*.01+1e-9: continue
    pnl=(int(side.iloc[i])*(float(d.close.iloc[i+4])-float(d.open.iloc[i+1]))-.8)*100*lots
    equity+=pnl
    records.append((int(d.time.iloc[i]),round(pnl,2)))
out={}
for name,a in [('train',[p for t,p in records if t<cut]),('out_of_sample',[p for t,p in records if t>=cut])]:
    a=np.array(a); eq=1000+np.cumsum(a)
    out[name]={'trades':len(a),'wins':round(float(a[a>0].sum()),2),'losses':round(float(a[a<0].sum()),2),'net':round(float(a.sum()),2),'closed_trade_dd':round(float(np.max(np.maximum.accumulate(np.r_[1000,eq])[1:]-eq)),2) if len(a) else 0}
print(json.dumps(out,indent=2))
