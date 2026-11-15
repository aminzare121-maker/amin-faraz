import pandas as pd, numpy as np, json, sys
from pathlib import Path
df=pd.read_csv(sys.argv[1]); df['dt']=pd.to_datetime(df.time,unit='s',utc=True);df['day']=df.dt.dt.date;df['hour']=df.dt.dt.hour
records=[]
for day,g in df.groupby('day'):
 early=g[(g.hour>=7)&(g.hour<8)]; trade=g[(g.hour>=8)&(g.hour<13)]
 if len(early)!=4 or len(trade)<8:continue
 hi=early.high.max();lo=early.low.min();rng=hi-lo
 prev=df[df.dt<early.dt.iloc[0]].tail(96)
 if len(prev)<96:continue
 atr=(prev.high-prev.low).median()
 if not (.5*atr<rng<5*atr):continue
 for mode in ['breakout','fade']:
  idx=trade.index[(trade.close>hi)|(trade.close<lo)]
  if len(idx)==0:continue
  loc=df.index.get_loc(idx[0])
  if loc+1>=len(df) or df.day.iloc[loc+1]!=day:continue
  side=1 if df.close.iloc[loc]>hi else -1
  if mode=='fade':side=-side
  entry=df.open.iloc[loc+1];stopdist=max(atr*1.5,2.)
  lots=round(min(.2,max(0,np.floor((10/(stopdist*100))/.01)*.01)),2)
  if lots<.01:continue
  exitprice=df.close.iloc[min(loc+12,len(df)-1)]
  for j in range(loc+1,min(loc+13,len(df))):
   if df.day.iloc[j]!=day:break
   if (side==1 and df.low.iloc[j]<=entry-stopdist) or (side==-1 and df.high.iloc[j]>=entry+stopdist):
    exitprice=entry-side*stopdist;break
   if (side==1 and df.high.iloc[j]>=entry+2*stopdist) or (side==-1 and df.low.iloc[j]<=entry-2*stopdist):
    exitprice=entry+side*2*stopdist;break
   exitprice=df.close.iloc[j]
  gross=(exitprice-entry)*side*100*lots;cost=(.26+.6)*100*lots+7*lots
  records.append(dict(day=str(day),mode=mode,lots=lots,gross=gross,cost=cost,net=gross-cost))
r=pd.DataFrame(records)
out={'rows':len(df),'split':'2026-07-21 UTC','cost_model':'spread .26/oz, slippage .30/oz per side, commission $7/lot RT; stop first','results':{}}
for mode in ['breakout','fade']:
 for period,subset in [('train',r[r.day<'2026-07-21']),('oos',r[r.day>='2026-07-21'])]:
  q=subset[subset['mode']==mode].sort_values('day')
  equity=1000+q.net.cumsum();dd=(equity.cummax().clip(lower=1000)-equity).max() if len(q) else 0
  out['results'][mode+'_'+period]=dict(opportunities=len(q),trades=len(q),gross_winners=round(q.loc[q.gross>0,'gross'].sum(),2),gross_losers=round(q.loc[q.gross<0,'gross'].sum(),2),costs=round(q.cost.sum(),2),net=round(q.net.sum(),2),max_drawdown_usd=round(float(dd),2),days_ge_50=int((q.groupby('day').net.sum()>=50).sum()),trading_days=int(q.day.nunique()))
print(json.dumps(out,indent=2))
