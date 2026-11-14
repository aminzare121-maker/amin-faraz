import sys
from pathlib import Path
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parent
DATA=BASE/'data'/'Eplanet_M15_20251105_20261105_merged.csv'
sys.path.insert(0,str(BASE))
import amin_candle_voice_v3 as m

def bars(rows,starts=1700000000):
    x=pd.DataFrame(rows,columns=['open','high','low','close','spread'])
    x['time']=starts+np.arange(len(x))*900
    x['tick_volume']=500
    return x

def test_no_future_features():
    df=m.read_history(DATA)
    f,_=m.features(df)
    cutoff=700
    edit=df.copy()
    for col in ('open','high','low','close'):
        edit.loc[cutoff+1:,col]*=1.5
    f2,_=m.features(edit)
    np.testing.assert_allclose(f.iloc[:cutoff+1].to_numpy(),f2.iloc[:cutoff+1].to_numpy(),equal_nan=True)

def test_contiguity():
    df=bars([[100,101,99,100,30]]*9)
    df.loc[5:,'time']+=900
    v=m.contiguous(df,3)
    assert v[0] and v[1]
    assert not v[2] and not v[3] and not v[4]
    assert v[5] and not v[6]

def test_collision_stop_prioritized():
    df=bars([[100,101,99,100,0],[100,110,90,100,0],[100,101,99,100,0],[100,101,99,100,0]])
    # ATR 2, BUY enters at index 1 open, both 90 and 110 hit. Must stop.
    ar=pd.Series([2.,2.,2.,2.]);spec=m.Barrier(2,1.,2.)
    out=m.label_barriers(df,ar,spec)
    assert out['buy']['event'][0]=='STOP_COLLISION',out
    assert out['buy']['net'][0]<0
    assert out['sell']['event'][0]=='STOP_COLLISION'
    assert out['sell']['net'][0]<0

def test_clean_target_hit_each_side():
    a=pd.Series([1.]*4)
    up=bars([[100,100.2,99.8,100,0],[100,103,99.4,102,0],[102,103,101.5,102,0],[102,103,101.5,102,0]])
    x=m.label_barriers(up,a,m.Barrier(2,1.,1.5))
    assert x['buy']['event'][0]=='TARGET'
    assert x['buy']['net'][0]>0
    dn=bars([[100,100.2,99.8,100,0],[100,100.5,97,98,0],[98,98.5,97,98,0],[98,98.5,97,98,0]])
    y=m.label_barriers(dn,a,m.Barrier(2,1.,1.5))
    assert y['sell']['event'][0]=='TARGET'
    assert y['sell']['net'][0]>0


def test_short_spread_prevents_fake_tp():
    df=bars([[100,101,99,100,50],[100,100,98.2,99,50],[99,99,98.2,99,50],[99,99,98.2,99,50]])
    ar=pd.Series([1.,1.,1.,1.]); spec=m.Barrier(2,1,1.5)
    out=m.label_barriers(df,ar,spec)
    # sell at 100-.05, TP ask <= 98.45; candle low bid98.2 +.5 =>98.7, NOT TP
    assert out['sell']['event'][0]=='TIMEOUT', out['sell']['event'][0]

def test_timeout_is_executable_outcome():
    df=bars([[100,100.5,99.5,100,30],[100,100.5,99.5,100,30],[100,100.5,99.5,100,30],[100,100.5,99.5,100,30]])
    a=pd.Series([4.,4.,4.,4.]);o=m.label_barriers(df,a,m.Barrier(2,1.,2.))
    assert o['buy']['event'][0]=='TIMEOUT'
    assert o['buy']['net'][0]<0  # costs even when prices don't move

def test_gaps_invalidate_future():
    df=bars([[100,100.5,99.5,100,30]]*5)
    df.loc[3:,'time']+=3600
    out=m.label_barriers(df,pd.Series([4.]*5),m.Barrier(2,1.,2.))
    assert not out['valid'][1]
    assert out['buy']['exit'][1]==-1 and np.isnan(out['sell']['net'][1])

def test_split_purge():
    s=m.make_splits(10000,8)
    assert max(s['train'])+8<min(s['calibration'])
    assert max(s['calibration'])+8<min(s['validation'])
    assert max(s['validation'])+8<min(s['holdout'])


def test_nonoverlap():
    df=bars([[100,101,99,100,0]]*15)
    net=np.ones(15)
    o={'buy':{'exit':np.arange(15)+3,'net':net,'event':['TARGET']*15},
       'sell':{'exit':np.arange(15)+3,'net':net,'event':['TARGET']*15}}
    o['buy']['exit'][-3:]=-1;o['sell']['exit'][-3:]=-1
    p={'buy':{i:0.9 for i in range(10)},'sell':{}}
    t=m.select_backtest(df,range(10),o,p,{'buy':.8,'sell':.8},'long')
    assert [x['decision_index'] for x in t]==[0,3,6,9]


def test_vectorized_labels_against_scalar_reference():
    """Cross-check 64 independent decisions against a simple single-trade simulator."""
    df=m.read_history(DATA).iloc[2000:2500].reset_index(drop=True)
    _,atr=m.features(df)
    spec=m.Barrier(4,1.,2.)
    data=m.label_barriers(df,atr,spec)
    rng=np.random.default_rng(777)
    ids=rng.choice(np.where(data['valid']&atr.notna().to_numpy())[0],size=64,replace=False)
    for i in ids:
        for side in ('buy','sell'):
            dist=atr.iat[i]
            if side=='buy':
                ent=df.open.iat[i+1]+df.spread.iat[i+1]*m.POINT_VALUE+m.ENTRY_SLIP
                tp=ent+2*dist;sl=ent-dist
            else:
                ent=df.open.iat[i+1]-m.ENTRY_SLIP
                tp=ent-2*dist;sl=ent+dist
            event='TIMEOUT'; exitidx=i+spec.horizon
            for j in range(i+1,i+1+spec.horizon):
                if side=='buy':
                    hit_sl=df.low.iat[j]<=sl
                    hit_tp=df.high.iat[j]>=tp
                else:
                    asklo=df.low.iat[j]+df.spread.iat[j]*m.POINT_VALUE
                    askhi=df.high.iat[j]+df.spread.iat[j]*m.POINT_VALUE
                    hit_sl=askhi>=sl
                    hit_tp=asklo<=tp
                if hit_sl:
                    event='STOP_COLLISION' if hit_tp else 'STOP'
                    exitidx=j
                    if side=='buy':exitpx=min(sl,df.open.iat[j])-m.EXIT_SLIP
                    else:exitpx=max(sl,df.open.iat[j]+df.spread.iat[j]*m.POINT_VALUE)+m.EXIT_SLIP
                    break
                if hit_tp:
                    event='TARGET';exitidx=j
                    exitpx=tp-m.EXIT_SLIP if side=='buy' else tp+m.EXIT_SLIP
                    break
            else:
                j=exitidx
                exitpx=df.close.iat[j]-m.EXIT_SLIP if side=='buy' else df.close.iat[j]+df.spread.iat[j]*m.POINT_VALUE+m.EXIT_SLIP
            scalar=(exitpx-ent if side=='buy' else ent-exitpx)-m.COMMISSION_PRICE_OZ
            got=data[side]
            assert abs(got['net'][i]-scalar)<1e-8, (i,side,got['net'][i],scalar)
            assert got['event'][i]==event and got['exit'][i]==exitidx

if __name__=='__main__':
    for name,f in sorted(globals().items()):
        if name.startswith('test_') and callable(f):
            f();print('PASS',name)
