"""V5 gap-reversion audit. Requires private Eplanet CSV locally; do not commit CSV."""
import pandas as pd, numpy as np, json, sys
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['date']=pd.to_datetime(d.time,unit='s',utc=True).dt.date
d['gap']=d.open-d.close.shift(1)
d['baseline']=d.gap.abs().shift(1).rolling(96,min_periods=50).median()
d['atr']=(d.high-d.low).shift(1).rolling(32,min_periods=25).mean()
d['eligible']=(d.gap.abs()>=np.maximum(.35,3*d.baseline))&(d.gap.abs()<=2*d.atr)&(d.atr>0)
d['lots']=np.clip(np.floor((5/(d.atr*100))/0.01)*0.01,.01,.10)
d.loc[d.atr*100*.01>5,'lots']=0
d['gross']=-np.sign(d.gap)*(d.close-d.open)*100*d.lots
d['cost']=d.lots/0.01*.46
d['net']=d.gross-d.cost
split=int(len(d)*.6); threshold=float(d.iloc[:split].atr.quantile(.75)); results={}
for period,frame in [('train',d.iloc[:split]),('test',d.iloc[split:])]:
 for guard in [False,True]:
  z=frame[frame.eligible&(frame.lots>0)&((frame.atr<=threshold) if guard else True)]
  eq=1000+z.net.cumsum()
  results[period+('_guard' if guard else '_base')]={'opportunities':int(frame.eligible.sum()),'trades':len(z),'gross':round(float(z.gross.sum()),2),'cost':round(float(z.cost.sum()),2),'net':round(float(z.net.sum()),2),'max_closed_drawdown':round(float((eq.cummax().clip(lower=1000)-eq).max()),2) if len(eq) else 0,'days_ge_50':int((z.groupby('date').net.sum()>=50).sum()),'days':frame.date.nunique()}
print(json.dumps(results,indent=2))
