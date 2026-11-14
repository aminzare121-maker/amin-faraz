#!/usr/bin/env python3
"""Validate M15 external quote directions against Eplanet. Research only.
All time shifts are selected using calibration days BEFORE evaluation dates.
Never authorizes a trade or lot/risk change.
"""
import io, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

def load_eplanet(path):
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if 'M15-' in n and n.lower().endswith('.csv')]
        if not names: raise ValueError('no Eplanet M15 CSV')
        frames=[pd.read_csv(io.BytesIO(z.read(n))) for n in names]
    d=pd.concat(frames,ignore_index=True).drop_duplicates('time').sort_values('time')
    d['time_utc']=pd.to_datetime(d.time,unit='s',utc=True)
    d['direction']=np.where(d.close>d.open,'up',np.where(d.close<d.open,'down','flat'))
    return d.set_index('time_utc')

def load_external_directions(path):
    d=pd.read_csv(path,dtype={'external_dir':str})
    if not {'time','external_dir'}.issubset(d.columns):raise ValueError('missing fields')
    d['time']=pd.to_datetime(d.time,utc=True)
    d.external_dir=d.external_dir.map({'0':'down','1':'up','x':'flat','down':'down','up':'up','flat':'flat'})
    if d.external_dir.isna().any() or d.time.duplicated().any():raise ValueError('bad external rows')
    return d.sort_values('time').reset_index(drop=True)

def direction_score(external,eplanet,offset_minutes):
    t=pd.DatetimeIndex(external.time)+pd.Timedelta(minutes=offset_minutes)
    own=eplanet.direction.reindex(t).to_numpy()
    ext=external.external_dir.to_numpy()
    valid=np.isin(own,['up','down']) & np.isin(ext,['up','down'])
    n=int(valid.sum())
    correct=int(np.sum(own[valid]==ext[valid]))
    return {'n':n,'agree':correct,'rate':correct/n if n else None}

def choose_offset(train,eplanet,offsets=range(-120,121,15),minimum=40):
    options=[(off,direction_score(train,eplanet,off)) for off in offsets]
    options=[(off,score) for off,score in options if score['n']>=minimum]
    if not options:raise ValueError('too few matched calibration candles')
    return max(options,key=lambda item:(item[1]['rate'],item[1]['n'],-abs(item[0])))

def run(ep_zip,external_csv,out,split_utc='2026-03-08T00:00:00Z'):
    ep=load_eplanet(ep_zip)
    ex=load_external_directions(external_csv)
    split=pd.Timestamp(split_utc)
    eras=[('pre_dst',ex[ex.time<split]),('post_dst',ex[ex.time>=split])]
    audit=[];holdout=[]
    for era,frame in eras:
        if frame.empty:continue
        first=frame.time.dt.date.min()
        train=frame.loc[frame.time.dt.date==first]
        test=frame.loc[frame.time.dt.date>first]
        if test.empty:continue
        offset,cal=choose_offset(train,ep)
        score=direction_score(test,ep,offset)
        audit.append({'era':era,'calibration_date':str(first),
                      'offset_minutes':offset,'train':cal,'holdout':score})
        holdout.append(test.assign(corrected_time=test.time+pd.Timedelta(minutes=offset),
                                   offset_minutes=offset))
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(audit).to_json(out/'clock_alignment_audit.json',orient='records',indent=2)
    if holdout:pd.concat(holdout).to_csv(out/'calibrated_holdout.csv',index=False)
    return audit

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--ep',required=True);p.add_argument('--external',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    print(json.dumps(run(a.ep,a.external,a.out),indent=2))
