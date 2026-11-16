import pandas as pd
import numpy as np
import json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
d['atr']=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1).rolling(32).mean()
d['range']=d.high-d.low
rows=[]; equity=1000.; peak=equity
for i in range(40,len(d)-2):
 a=d.iloc[i]; b=d.iloc[i+1]
 if b.time-a.time!=900 or d.iloc[i+2].time-b.time!=900: continue
 if not (a['range']>2*a.atr and a['range']>0 and a.tick_volume>d.tick_volume.iloc[i-32:i].median()): continue
 pos=(a.close-a.low)/a['range']
 side=-1 if pos>.85 else (1 if pos<.15 else 0)
 if not side: continue
 risk_dist=max(a.atr,2.)
 lot=min(.1,max(.01,round((equity*.005)/(risk_dist*100),2)))
 entry=b.open; stop=entry-side*risk_dist; exitprice=b.close
 if side==1 and b.low<=stop: exitprice=stop
 if side==-1 and b.high>=stop: exitprice=stop
 cost=(a.spread*.01+.60)*100*lot
 pnl=side*(exitprice-entry)*100*lot-cost
 equity+=pnl; peak=max(peak,equity)
 rows.append(dict(time=str(b['dt']),pnl=round(pnl,2),equity=round(equity,2),drawdown=round(peak-equity,2),lot=lot))
r=pd.DataFrame(rows); cut=d.dt.iloc[int(len(d)*.7)]
report={'bars':len(d),'split_utc':str(cut)}
for name,z in [('train',r[pd.to_datetime(r.time,utc=True)<cut]),('out_of_sample',r[pd.to_datetime(r.time,utc=True)>=cut])]:
 report[name]={'trades':len(z),'net_usd':round(z.pnl.sum(),2),'wins':int((z.pnl>0).sum()),'losses':int((z.pnl<0).sum()),'max_closed_trade_drawdown_usd':round((z.pnl.cumsum().cummax()-z.pnl.cumsum()).max(),2) if len(z) else 0,'days_net_ge_50':int((z.groupby(z.time.str[:10]).pnl.sum()>=50).sum()) if len(z) else 0}
print(json.dumps(report,indent=2))
