from pathlib import Path
import pandas as pd, numpy as np
files=list(Path('download').glob('*xauusd*m15*.csv'))
if not files: raise SystemExit('No XAUUSD M15 CSV found in download folder')
df=pd.read_csv(files[-1]); df.columns=[str(x).lower().strip() for x in df.columns]
print('Source:',files[-1], 'Columns:',list(df.columns))
tcol=next((c for c in df if c in ('timestamp','time','date','datetime')),None)
if tcol is None: raise SystemExit('Time column not found')
for c in ('open','high','low','close'):
 if c not in df: raise SystemExit('Missing '+c)
 df[c]=pd.to_numeric(df[c],errors='coerce')
df[tcol]=pd.to_datetime(df[tcol],utc=True,errors='coerce')
df=df.dropna(subset=[tcol,'open','high','low','close']).sort_values(tcol).drop_duplicates(tcol).reset_index(drop=True)
print('Candles:',len(df),'From:',df[tcol].min(),'To:',df[tcol].max())
if len(df)<3000: raise SystemExit('Insufficient data; do not trust results')
# Signals use only prior completed candle. Execution at next bar open, exit after 4 bars.
# Conservative spread/slippage approximation in price dollars, not account dollars.
results=[]; close=df.close.to_numpy(); op=df.open.to_numpy(); times=df[tcol]
for lookback in (4,8,16,32,64):
 for threshold in (0.0,0.001,0.002,0.004):
  momentum=pd.Series(close).pct_change(lookback).to_numpy()
  for mode in ('trend','reversal'):
   direction=np.where(momentum>threshold,1,np.where(momentum < -threshold,-1,0))
   if mode=='reversal': direction=-direction
   ix=np.arange(lookback+1,len(df)-5,5) # nonoverlapping holding periods
   ix=ix[direction[ix-1]!=0]
   if len(ix)<50: continue
   side=direction[ix-1]
   # Exit at open 4 bars later, after entry at current open
   pnl=side*(op[ix+4]-op[ix])-0.30 # illustrative $0.30 roundtrip cost per ounce
   months=times.iloc[ix].dt.to_period('M').astype(str).to_numpy()
   monthly=pd.Series(pnl).groupby(months).sum()
   split=int(len(ix)*0.7)
   train=pnl[:split]; test=pnl[split:]
   if len(test)<15: continue
   equity=np.cumsum(test)
   dd=float(np.max(np.maximum.accumulate(np.r_[0,equity])[1:]-equity))
   results.append(dict(strategy=mode,lookback=lookback,threshold=threshold,trades=len(ix),train_mean_usd_per_oz=round(float(train.mean()),3),test_mean_usd_per_oz=round(float(test.mean()),3),test_total_usd_per_oz=round(float(test.sum()),2),test_winrate=round(float(np.mean(test>0)),3),positive_months=int((monthly>0).sum()),months=len(monthly),test_max_drawdown_usd_per_oz=round(dd,2)))
out=pd.DataFrame(results)
out=out.sort_values(['test_mean_usd_per_oz','positive_months'],ascending=False)
out.to_csv('strategy_results.csv',index=False)
print(out.head(10).to_string(index=False)); print('Saved strategy_results.csv')
print('WARNING: exploratory research only. No intrabar stops, real broker spreads, or execution model. Not a validated profitable strategy.')
