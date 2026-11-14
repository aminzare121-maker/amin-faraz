# V5 research: rejection candle, no private data. Research only.
# Run: python research/v5_wick_rejection.py path/to/Eplanet_M15.csv
import sys, json
import numpy as np
import pandas as pd

def test(df, start, end):
    high,low,op,cl=[df[x].to_numpy() for x in ('high','low','open','close')]
    tr=np.maximum.reduce([high-low,abs(high-np.r_[np.nan,cl[:-1]]),abs(low-np.r_[np.nan,cl[:-1]])])
    atr=pd.Series(tr).rolling(20).mean().to_numpy()
    equity=peak=1000.; drawdown=0.; signals=0; trades=[]
    i=max(25,start)
    while i<end-5:
        width=high[i]-low[i]; body=cl[i]-op[i]
        lower=min(op[i],cl[i])-low[i]; upper=high[i]-max(op[i],cl[i])
        side=1 if lower>.65*width and body>0 and width>1.3*atr[i] else (-1 if upper>.65*width and body<0 and width>1.3*atr[i] else 0)
        if not side or not np.isfinite(atr[i]): i+=1;continue
        signals+=1; entry=op[i+1]; stop=max(.9*atr[i],2.)
        spread=float(df.spread.iloc[i+1])*.01
        cost_per_lot=(spread+.6)*100+7
        lots=np.floor(min(equity*.01/(stop*100+cost_per_lot),1)*100)/100
        if lots<.01:i+=1;continue
        exit_price=cl[i+4]
        for j in range(i+1,i+5):
            if side==1:
                if low[j]<=entry-stop:exit_price=entry-stop;break
                if high[j]>=entry+1.5*stop:exit_price=entry+1.5*stop;break
            else:
                if high[j]>=entry+stop:exit_price=entry+stop;break
                if low[j]<=entry-1.5*stop:exit_price=entry-1.5*stop;break
        pnl=side*(exit_price-entry)*100*lots-cost_per_lot*lots
        equity+=pnl;peak=max(peak,equity);drawdown=max(drawdown,(peak-equity)/peak)
        trades.append([int(df.time.iloc[i]),float(pnl),float(lots)]);i+=5
    frame=pd.DataFrame(trades,columns=['time','pnl','lots'])
    good=0
    if len(frame):
        good=int((frame.assign(day=pd.to_datetime(frame.time,unit='s').dt.date).groupby('day').pnl.sum()>=50).sum())
    return dict(signals=signals,trades=len(trades),net=round(equity-1000,2),max_drawdown_pct=round(drawdown*100,2),days_at_least_50=good)

if __name__=='__main__':
    df=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
    split=int(len(df)*.7)
    print(json.dumps({'rows':len(df),'development':test(df,0,split),'later_period':test(df,split,len(df))},indent=2))
