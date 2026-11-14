#!/usr/bin/env python3
"""Audit whether a second XAUUSD M15 feed adds future-direction information.
An externally matched, CLOSED bar may only be compared to later target bars.
This does NOT trade and does not reproduce original V5 trading rules.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from v5_crossfeed_gate import load_eplanet

def wilson(k,n,z=1.96):
    if not n:return None
    p=k/n;v=1+z*z/n
    center=(p+z*z/(2*n))/v
    delta=z*((p*(1-p)/n+z*z/(4*n*n))**0.5)/v
    return [round(center-delta,6),round(center+delta,6)]

def prepare(ep,holdout):
    required={'time','corrected_time','external_dir','offset_minutes'}
    if not required.issubset(holdout):raise ValueError('missing calibrated holdout fields')
    a=holdout.copy()
    a['time']=pd.to_datetime(a.time,utc=True)
    a['corrected_time']=pd.to_datetime(a.corrected_time,utc=True)
    if a.corrected_time.duplicated().any():raise ValueError('duplicate corrected time')
    if not np.all((a.corrected_time-a.time).dt.total_seconds()/60==a.offset_minutes):
        raise ValueError('inconsistent offset')
    a.external_dir=a.external_dir.astype(str).map({
        '0':'down','1':'up','x':'flat','up':'up','down':'down','flat':'flat'})
    if a.external_dir.isna().any():raise ValueError('invalid external direction')
    a=a.sort_values('corrected_time').set_index('corrected_time')
    ep=ep.sort_index()
    j=a.join(ep[['open','close','direction']],how='left')
    if j.open.isna().any():raise ValueError('missing aligned Eplanet candles')
    idx=ep.index.to_series()
    is_next=(idx.shift(-1)-idx).dt.total_seconds().eq(900)
    is_four=pd.Series(True,index=ep.index)
    for h in range(1,5):
        is_four &= (idx.shift(-h)-idx.shift(-(h-1))).dt.total_seconds().eq(900)
    move1=ep.close.shift(-1)-ep.open.shift(-1)
    move4=ep.close.shift(-4)-ep.open.shift(-1)
    target=pd.DataFrame(index=ep.index)
    target['next1_dir']=np.where(is_next & move1.abs().gt(1e-8),
                                  np.where(move1>0,'up','down'),None)
    target['next4_dir']=np.where(is_four & move4.abs().gt(1e-8),
                                  np.where(move4>0,'up','down'),None)
    j=j.join(target,how='left')
    j['comparable']=j.external_dir.isin(['up','down']) & j.direction.isin(['up','down'])
    return j

def predictive_check(j,h):
    y='next'+str(h)+'_dir'
    d=j.loc[j.comparable & j[y].isin(['up','down'])]
    if d.empty:return {'n':0}
    ext=(d.external_dir==d[y]).to_numpy()
    local=(d.direction==d[y]).to_numpy()
    return {'n':len(d),'external_momentum_accuracy':round(float(ext.mean()),6),
            'eplanet_momentum_accuracy':round(float(local.mean()),6),
            'external_new_correct':int(np.sum(ext & ~local)),
            'external_new_wrong':int(np.sum(~ext & local)),
            'incremental_correct_minus_wrong':int(ext.sum()-local.sum()),
            'mismatched_current_bars':int(np.sum(d.external_dir!=d.direction)),
            'days':int(pd.Index(d.index.date).nunique())}

def run(ep_zip,holdout_csv,out):
    ep=load_eplanet(ep_zip)
    j=prepare(ep,pd.read_csv(holdout_csv))
    aligned=j[j.comparable]
    if len(aligned)<500:raise ValueError('insufficient matched holdout bars')
    matches=int((aligned.external_dir==aligned.direction).sum())
    n=len(aligned)
    report={
        'n':n,'current_bar_agree':matches,'current_bar_match_fraction':round(matches/n,6),
        'current_bar_wilson95_iid_only':wilson(matches,n),
        'future_15m':predictive_check(j,1),
        'future_60m':predictive_check(j,4),
        'approved_uses':['M15 clock calibration','external candle data-quality checks'],
        'not_approved_uses':['new predictive signal','broker-equivalent execution','risk/lot changes','automatic trades'],
        'source_broker_unknown':True,
        'warning':'Historical March 2026 sample and only 13 holdout dates; overlapping future labels. Prior project exploration used the same dates; not pristine out-of-sample profitability evidence.'
    }
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    j[['external_dir','direction','next1_dir','next4_dir']].to_csv(out/'paired_candles_and_future_labels.csv')
    (out/'incremental_information.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ep',required=True);p.add_argument('--holdout',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    print(json.dumps(run(a.ep,a.holdout,a.out),indent=2))
