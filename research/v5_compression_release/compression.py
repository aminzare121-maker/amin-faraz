"""Compression release: use with rejection_engine.py (previous research dependency)."""
import numpy as np,pandas as pd
from rejection_engine import load,replay
def build(d):
    h,l,c=d.high,d.low,d.close
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14,adjust=False).mean()
    width=h.shift(1).rolling(8).max()-l.shift(1).rolling(8).min()
    normal=tr.shift(1).rolling(96).mean()
    compressed=width<normal*3.2
    upper=h.shift(1).rolling(8).max()
    lower=l.shift(1).rolling(8).min()
    buy=compressed&(c>upper)&(c.shift(1)<=upper)&((c-d.open)>tr*.35)
    sell=compressed&(c<lower)&(c.shift(1)>=lower)&((d.open-c)>tr*.35)
    return atr,np.select([buy,sell],[1,-1],0)
def run(source):
    d=load(source);atr,sig=build(d)
    for name,start,end in [('development','2026-01-01','2026-04-01'),('later_reused','2026-04-01','2026-11-06')]:
        for slip in (.1,.3,.5):
            metrics,_=replay(d,atr,sig,start,end,slip=slip)
            print(name,slip,metrics)
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source');run(p.parse_args().source)
