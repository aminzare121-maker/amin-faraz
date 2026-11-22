# Reproducible research: directional efficiency vs holding horizon
# Requires pandas, numpy and private Eplanet CSV locally; never commit CSV.
import pandas as pd, numpy as np
from pathlib import Path
p=Path("Eplanet_M15_20251105_20261105_merged.csv")
d=pd.read_csv(p).sort_values("time").drop_duplicates("time").reset_index(drop=True)
d["dt"]=pd.to_datetime(d.time,unit="s",utc=True)
tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
d["atr"]=tr.rolling(20).mean().shift(1)
d["eff"]=(d.close-d.close.shift(8)).abs()/d.close.diff().abs().rolling(8).sum()
d["direction"]=np.sign(d.close-d.close.shift(8))
d["range_ratio"]=(d.high-d.low)/d.atr
eligible=(d.eff>=.7)&(d.eff<=1)&(d.range_ratio<=1.8)&(d.atr>0)&(d.direction!=0)
split=pd.Timestamp("2026-06-15",tz="UTC")
for h in [2,4,8,12]:
    valid=(d.time.shift(-h)-d.time==900*h)&(d.time.shift(-1)-d.time==900)
    edge=d.direction*(d.close.shift(-h)-d.open.shift(-1))-.56
    x=edge[eligible&valid&(d.dt<split)].dropna()
    print(h,len(x),round(x.mean(),6),round((x>0).mean(),4))
# Gate: >=150 train observations AND > $0.30/oz train edge; otherwise no live/demo trades.
# For complete OOS diagnostic with stop-first OHLC, variable lots and guard, use
# v5_efficiency_horizon_20261122.py downloadable from the corresponding run.
