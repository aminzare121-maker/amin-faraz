"""Research only. Eplanet M15 wick rejection; no orders. Requires local private CSV."""
import numpy as np
import pandas as pd
import sys
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
tr=np.maximum.reduce([(d.high-d.low).to_numpy(),abs(d.high-d.close.shift()).to_numpy(),abs(d.low-d.close.shift()).to_numpy()])
atr=pd.Series(tr).rolling(20).mean().to_numpy()
rng=(d.high-d.low).to_numpy(); body=(d.close-d.open).to_numpy()
lower=(np.minimum(d.open,d.close)-d.low).to_numpy()
upper=(d.high-np.maximum(d.open,d.close)).to_numpy()
def run(start,end):
    equity=peak=1000.; dd=0.; trades=[]; signals=0; i=max(start,25)
    while i<end-5:
        direction=1 if lower[i]>.65*rng[i] and body[i]>0 and rng[i]>1.3*atr[i] else (-1 if upper[i]>.65*rng[i] and body[i]<0 and rng[i]>1.3*atr[i] else 0)
        if not direction or not np.isfinite(atr[i]): i+=1; continue
        signals+=1; entry=d.open[i+1]; dist=max(atr[i]*.9,2.)
        spread=d.spread[i+1]*.01 # assumes MT5 spread points of $0.01; verify symbol digits
        lots=np.floor(min(equity*.01/(dist*100+(spread+.6)*100+7),1)*100)/100
        if lots<.01: i+=1; continue
        exitp=d.close[i+4]
        for j in range(i+1,i+5):
            if direction==1:
                if d.low[j]<=entry-dist: exitp=entry-dist; break
                if d.high[j]>=entry+dist*1.5: exitp=entry+dist*1.5; break
            else:
                if d.high[j]>=entry+dist: exitp=entry+dist; break
                if d.low[j]<=entry-dist*1.5: exitp=entry-dist*1.5; break
        pnl=direction*(exitp-entry)*100*lots-(spread+.6)*100*lots-7*lots
        equity+=pnl; peak=max(peak,equity); dd=max(dd,(peak-equity)/peak)
        trades.append((int(d.time[i]),round(pnl,2),lots))
        i+=5
    t=pd.DataFrame(trades,columns=['time','pnl','lots'])
    days=t.assign(day=pd.to_datetime(t.time,unit='s').dt.date).groupby('day').pnl.sum() if len(t) else pd.Series(dtype=float)
    return dict(signals=signals,trades=len(t),net=round(equity-1000,2),max_dd_pct=round(dd*100,2),wins=int((t.pnl>0).sum()),positive_50_days=int((days>=50).sum()))
cut=int(len(d)*.7)
print("development",run(0,cut))
print("out_of_sample",run(cut,len(d)))
