"""V5 research only. No live/MT5 orders. Run: python research/v5_liquidity_sweep.py Eplanet_M15_20251105_20261105_merged.csv"""
import sys,json
import pandas as pd
import numpy as np
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['dt']=pd.to_datetime(d.time,unit='s',utc=True)
p=d.close.shift()
tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d['atr']=tr.shift(1).rolling(20).mean()
d['hi']=d.high.shift(1).rolling(16).max()
d['lo']=d.low.shift(1).rolling(16).min()
rng=(d.high-d.low).replace(0,np.nan)
d['buy']=(d.low<d.lo)&(d.close>d.lo)&((d.close-d.low)/rng>=.65)&((d.lo-d.low)>=.10*d.atr)
d['sell']=(d.high>d.hi)&(d.close<d.hi)&((d.high-d.close)/rng>=.65)&((d.high-d.hi)>=.10*d.atr)
rows=[];occupied=-1
for i in range(40,len(d)-9):
 if i<=occupied or not (d.buy.iloc[i] or d.sell.iloc[i]):continue
 direction=1 if d.buy.iloc[i] else -1
 if d.buy.iloc[i] and d.sell.iloc[i]:continue
 entry=float(d.open.iloc[i+1]);atr=float(d.atr.iloc[i]);dist=max(1.2*atr,1.)
 if abs(entry-d.close.iloc[i])>atr:continue
 stop=entry-direction*dist;target=entry+direction*2*dist
 out=float(d.close.iloc[i+8]);reason='time';last=i+8
 for j in range(i+1,i+9):
  hitstop=(d.low.iloc[j]<=stop if direction==1 else d.high.iloc[j]>=stop)
  hittarget=(d.high.iloc[j]>=target if direction==1 else d.low.iloc[j]<=target)
  if hitstop or hittarget:
   out=stop if hitstop else target;reason='stop' if hitstop else 'target';last=j;break
 # 0.01 lot assumed 1 oz; 0.26 spread, 0.20 roundtrip slippage, 0.07 USD commission
 net=(out-entry)*direction-.26-.20-.07
 rows.append(dict(signal_time=str(d.dt.iloc[i]),exit_time=str(d.dt.iloc[last]),direction=direction,entry=entry,exit=out,reason=reason,net_usd_001lot=round(net,4),signal_index=i))
 occupied=last
r=pd.DataFrame(rows);cut=int(len(d)*.7)
result={'rows':len(d),'cutoff_utc':str(d.dt.iloc[cut]),'cost_assumptions':{'spread_price':.26,'roundtrip_slippage_price':.20,'commission_usd_per_001_lot':.07,'contract_oz_per_lot':100},'slices':{}}
for name,x in [('train',r[r.signal_index<cut]),('holdout',r[r.signal_index>=cut])]:
 daily=x.assign(day=pd.to_datetime(x.exit_time).dt.date).groupby('day').net_usd_001lot.sum()
 eq=x.net_usd_001lot.cumsum()
 result['slices'][name]={'trades':len(x),'net_usd_001lot':round(float(x.net_usd_001lot.sum()),2),'wins':int((x.net_usd_001lot>0).sum()),'losses':int((x.net_usd_001lot<=0).sum()),'max_trade_sequence_drawdown_usd_001lot':round(float((eq-eq.cummax().clip(lower=0)).min()),2),'days_with_trades':len(daily),'positive_days':int((daily>0).sum()),'days_ge_50_usd_at_001lot':int((daily>=50).sum()),'worst_day_usd':round(float(daily.min()),2),'best_day_usd':round(float(daily.max()),2)}
print(json.dumps(result,indent=2))
