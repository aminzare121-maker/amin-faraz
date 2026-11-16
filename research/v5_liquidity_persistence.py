# V5 research: directional persistence, UTC liquid hours
# Reproduce locally: python research/v5_liquidity_persistence.py /path/to/private/Eplanet_M15_20251105_20261105_merged.csv
# Research only. Never activate live/demo trades from this script.
import sys, json
import numpy as np
import pandas as pd
d=pd.read_csv(sys.argv[1]).sort_values('time').drop_duplicates('time').reset_index(drop=True)
d['utc']=pd.to_datetime(d.time,unit='s',utc=True)
d['atr']=(d.high-d.low).rolling(24).mean().shift(1)
d['med']=d.atr.rolling(192).median().shift(1)
m=d.close-d.open
d['side']=np.sign(m.shift(1)+m.shift(2)+m.shift(3))
d['agree']=(np.sign(m.shift(1))==d.side)&(np.sign(m.shift(2))==d.side)&(np.sign(m.shift(3))==d.side)
split=int(len(d)*.65)
def test(direction, filt, start, end):
    equity=1000.; trades=[]; i=max(start,200)
    while i<min(end,len(d)-3):
        x=d.iloc[i]; side=int(x.side*direction) if np.isfinite(x.side) else 0
        if not (side and x.agree and 12<=x.utc.hour<=18 and np.isfinite(x.atr) and x.atr>0 and
                (not filt or (x.atr<=1.2*x.med and x.spread<=26))):
            i+=1;continue
        distance=max(2.,float(x.atr)*.9)
        # No forced minimum lot if its stop exposure exceeds 0.5% equity.
        lot=np.floor(min(.1, equity*.005/(distance*100))*100)/100
        if lot<.01: i+=1;continue
        entry=float(x.open);stop=entry-side*distance;take=entry+side*1.5*distance
        price=float(d.iloc[i+2].close)
        for j in range(i,i+3):
            b=d.iloc[j]
            if (b.low<=stop if side>0 else b.high>=stop):price=stop;break
            if (b.high>=take if side>0 else b.low<=take):price=take;break
        gross=(price-entry)*side*lot*100
        cost=(float(x.spread)/100+.20)*lot*100+.07*lot/.01
        net=gross-cost;equity+=net
        trades.append((str(x.utc.date()),gross,cost,net))
        i+=3
    v=np.array([t[3] for t in trades]);eq=np.r_[1000,1000+np.cumsum(v)]
    days={}
    for day,_,_,net in trades:days[day]=days.get(day,0)+net
    return dict(trades=len(trades),gross_wins=round(sum(max(0,t[1]) for t in trades),2),
        gross_losses=round(sum(min(0,t[1]) for t in trades),2),
        costs=round(sum(t[2] for t in trades),2),net=round(sum(v),2),
        closed_drawdown=round(float(max(np.maximum.accumulate(eq)-eq)),2),
        days_ge_50=sum(z>=50 for z in days.values()),active_days=len(days))
results={}
for direction in [1,-1]:
    for filt in [False,True]:
        name=('continuation' if direction==1 else 'reversal')+('_riskfilter' if filt else '')
        results[name]={'train':test(direction,filt,0,split),'test':test(direction,filt,split,len(d))}
print(json.dumps(results,indent=2))
# Limitations: OHLC stop-first approximation, assumed contract $100/$1/lot,
# no intrabar tick replay, margin/stopout, swap, or broker fill verification.
