# Research-only reproducibility wrapper; no order execution.
# Requires private Eplanet CSV supplied locally, never committed.
# Full executed script is provided separately as v5_session_range_20261123.py.
import pandas as pd
import numpy as np
import sys
d=pd.read_csv(sys.argv[1]).sort_values("time").drop_duplicates("time")
d["dt"]=pd.to_datetime(d.time,unit="s",utc=True)
d["date"]=d.dt.dt.date
d["hour"]=d.dt.dt.hour
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d["atr"]=tr.rolling(20).mean().shift(1)
for date,g in d.groupby("date"):
    r=g[(g.hour>=7)&(g.hour<9)]
    if len(r)<6: continue
    hi,lo=r.high.max(),r.low.min()
    for i in g[(g.hour>=9)&(g.hour<12)].index:
        side=1 if d.loc[i,"close"]>hi else -1 if d.loc[i,"close"]<lo else 0
        if side:
            print(date, d.loc[i,"dt"],side,"range",hi-lo,"ATR",d.loc[i,"atr"])
            break
