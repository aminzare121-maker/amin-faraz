#!/usr/bin/env python3
"""Create an EMPTY M15 indicator template for actual historical trades. No inferred signals."""
import argparse, io, json, zipfile
from pathlib import Path
import pandas as pd

def build(ep_zip,trades_csv,out):
    t=pd.read_csv(trades_csv)
    if not {'entry_utc','side','pnl_usd'}.issubset(t):raise ValueError('missing trade columns')
    t['entry_utc']=pd.to_datetime(t.entry_utc,utc=True)
    if t.entry_utc.dt.minute.mod(15).ne(0).any() or t.entry_utc.dt.second.ne(0).any():
        raise ValueError('trade entry not M15-aligned')
    t['bar_open_utc']=t.entry_utc-pd.Timedelta(minutes=15)
    with zipfile.ZipFile(ep_zip) as z:
        files=[n for n in z.namelist() if n.lower().endswith('.csv') and 'M15-' in n]
        if not files:raise ValueError('M15 missing')
        chunks=[pd.read_csv(io.BytesIO(z.read(n))) for n in files]
    ep=pd.concat(chunks,ignore_index=True).drop_duplicates('time').sort_values('time')
    ep['bar_open_utc']=pd.to_datetime(ep.time,unit='s',utc=True)
    x=t.merge(ep[['bar_open_utc','open','high','low','close','tick_volume','spread']],
              on='bar_open_utc',how='left',validate='many_to_one')
    missing=int(x.open.isna().sum())
    if missing:raise ValueError(f'Missing {missing} matching Eplanet bars')
    x=(x[['bar_open_utc','open','high','low','close','tick_volume','spread']]
       .drop_duplicates('bar_open_utc').sort_values('bar_open_utc').reset_index(drop=True))
    x.insert(1,'bar_close_utc',x.bar_open_utc+pd.Timedelta(minutes=15))
    for key in ['indicator_1','indicator_2','indicator_1_ready_utc','indicator_2_ready_utc']:
        x[key]=''
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    x.to_csv(out/'TEMPLATE_INDICATOR_VALUES_EMPTY.csv',index=False)
    result={'trades':len(t),'matching_bars':len(x),'signal_values_loaded':0,
            'baseline_pnl_usd_sum_independent_folds':round(float(t.pnl_usd.sum()),6),
            'winners':int((t.pnl_usd>0).sum()),'losers':int((t.pnl_usd<0).sum()),
            'status':'WAITING_FOR_EXACT_INDICATOR_SOURCES; no indicator PnL test'}
    (out/'baseline_reference.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ep',required=True);p.add_argument('--trades',required=True);p.add_argument('--out',required=True)
    a=p.parse_args()
    print(json.dumps(build(a.ep,a.trades,a.out),indent=2))
