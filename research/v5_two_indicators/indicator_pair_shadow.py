#!/usr/bin/env python3
"""Research-only closed-M15 two-indicator SHADOW overlay. Never sends orders."""
import argparse,json
from pathlib import Path
import pandas as pd
import numpy as np

COLUMNS=['bar_open_utc','indicator_1','indicator_2',
         'indicator_1_ready_utc','indicator_2_ready_utc']

def audit(trades_csv,indicator_csv,out):
    t=pd.read_csv(trades_csv)
    x=pd.read_csv(indicator_csv)
    if not {'entry_utc','pnl_usd','side'}.issubset(t):raise ValueError('trade columns missing')
    if not set(COLUMNS).issubset(x):raise ValueError('indicator columns missing')
    t['entry_utc']=pd.to_datetime(t['entry_utc'],utc=True)
    t['bar_open_utc']=t['entry_utc']-pd.Timedelta(minutes=15)
    for col in ('bar_open_utc','indicator_1_ready_utc','indicator_2_ready_utc'):
        x[col]=pd.to_datetime(x[col],utc=True)
    if x.bar_open_utc.duplicated().any():raise ValueError('duplicate bars')
    if (x.bar_open_utc.dt.minute%15!=0).any():raise ValueError('unaligned bars')
    for k in (1,2):
        key=f'indicator_{k}'
        if not x[key].isin([-1,0,1]).all():raise ValueError('signal must be -1/0/+1')
        if (x[f'{key}_ready_utc']<x.bar_open_utc+pd.Timedelta(minutes=15)).any():
            raise ValueError('future-data leak: indicator before bar close')
    merged=t.merge(x,on='bar_open_utc',how='left',validate='many_to_one',indicator=True)
    present=merged['_merge'].eq('both')
    ready=present&(merged.indicator_1_ready_utc<=merged.entry_utc)&(merged.indicator_2_ready_utc<=merged.entry_utc)
    agree=ready&(merged.indicator_1==merged.side)&(merged.indicator_2==merged.side)
    oppose=ready&(merged.indicator_1==-merged.side)&(merged.indicator_2==-merged.side)
    merged['context']=np.select([agree,oppose,ready],['both_agree','both_oppose','mixed_or_neutral'],default='unavailable')
    baseline=float(t.pnl_usd.sum())
    groups=[]
    for k,g in merged.groupby('context'):
        groups.append({'context':k,'count':len(g),'net_pnl':float(g.pnl_usd.sum()),
                       'win_fraction':float((g.pnl_usd>0).mean())})
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    merged.to_csv(out/'shadow_trades.csv',index=False)
    report={'status':'RESEARCH_SHADOW_NOT_REAL_TRADING','n_trades':len(t),
        'n_preserved':len(merged),'n_context_ready':int(ready.sum()),
        'base_net_pnl':baseline,'shadow_net_pnl':float(merged.pnl_usd.sum()),
        'unchanged':bool(np.isclose(baseline,merged.pnl_usd.sum(),atol=1e-9)),
        'groups':groups,'not_original_V5':True}
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--trades',required=True)
    p.add_argument('--indicators',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.trades,a.indicators,a.out),indent=2))
