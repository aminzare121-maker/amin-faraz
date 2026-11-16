"""V5 shock reversal research. No trading, no private data committed.
Run: python research/v5_shock_reversion.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
Requires pandas numpy. Assumes 100 oz/lot; verify MT5 contract and tick size.
"""
import sys, json
import pandas as pd
import numpy as np
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["date"]=pd.to_datetime(d.time,unit="s",utc=True).dt.date
p=d.close.shift(1)
tr=pd.concat([d.high-d.low,(d.high-p).abs(),(d.low-p).abs()],axis=1).max(axis=1)
d["atr"]=tr.shift(1).rolling(40).median()
d["medvol"]=d.tick_volume.shift(1).rolling(40).median()
def run(lo,hi):
    trades=[]; occupied=-1
    for i in range(max(lo,42),min(hi,len(d)-5)):
        if i<=occupied: continue
        a=d.at[i,"atr"]; rng=d.at[i,"high"]-d.at[i,"low"]
        if not np.isfinite(a) or a<=0 or rng<2.5*a or d.at[i,"tick_volume"]<1.5*d.at[i,"medvol"]: continue
        pos=(d.at[i,"close"]-d.at[i,"low"])/rng
        side=1 if pos<.15 else (-1 if pos>.85 else 0)
        if not side: continue
        entry=d.at[i+1,"open"]; stop=entry-side*1.5*a; target=entry+side*a
        exitprice=d.at[i+4,"close"]; end=i+4
        for j in range(i+1,i+5):
            hitstop=d.at[j,"low"]<=stop if side==1 else d.at[j,"high"]>=stop
            hittarget=d.at[j,"high"]>=target if side==1 else d.at[j,"low"]<=target
            if hitstop or hittarget:
                exitprice=stop if hitstop else target; end=j; break
        lot=min(.10,max(.01,np.floor((10/(1.5*a+.86)/100)*100)/100))
        gross=(exitprice-entry)*side*100*lot
        cost=.86*100*lot # .26 spread proxy + .30 slippage each side
        trades.append((round(gross-cost,2),round(gross,2),round(cost,2),lot))
        occupied=end
    eq=1000; peak=1000; dd=0
    for pnl,*_ in trades:
        eq+=pnl;peak=max(peak,eq);dd=max(dd,peak-eq)
    days=len(set(d.iloc[lo:hi].date))
    return dict(bars=int(hi-lo),days=int(days),opportunities=len(trades),
                wins=sum(t[0]>0 for t in trades),net=round(eq-1000,2),
                gross=round(sum(t[1] for t in trades),2),
                costs=round(sum(t[2] for t in trades),2),
                max_closed_drawdown=round(dd,2),
                daily_net=round((eq-1000)/days,2),
                lot_min=float(min((t[3] for t in trades),default=0)),
                lot_max=float(max((t[3] for t in trades),default=0)))
cut=int(len(d)*.6)
for name,lo,hi in [("train",0,cut),("test",cut,len(d))]:
    print(json.dumps({"split":name,**run(lo,hi)}))
