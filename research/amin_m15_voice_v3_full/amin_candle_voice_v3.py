#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AMIN Candle Voice V3: offline, leakage-aware TP-before-SL research.

IMPORTANT: NO broker login, NO live feed, NO trade placement. This script uses
closed historical M15 bars and tests triple-barrier outcomes, with conservative
same-bar collision treatment and explicit UNVERIFIED broker assumptions.

Requirements: numpy, pandas, scikit-learn.
Usage: python amin_candle_voice_v3.py history.csv --output-dir results
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

STATUS = 'OFFLINE_RESEARCH_NO_BROKER_NO_ORDERS'
SEED = 280614
CONTRACT_OZ = 100.0  # ASSUMPTION; NOT checked with Eplanet
LOT = 0.01
POINT_VALUE = .01     # ASSUMPTION: spread column points -> XAUUSD price
ENTRY_SLIP = .05     # ASSUMED price per oz on entry
EXIT_SLIP = .05      # ASSUMED price per oz on exit
COMMISSION_PER_LOT = 7.0  # ASSUMED USD round-trip/1.0 lot
COMMISSION_PRICE_OZ = COMMISSION_PER_LOT / CONTRACT_OZ
MIN_TRADES = 100
MIN_DAYS = 25
MIN_PF = 1.2
STRESS_EXTRA_COST_PRICE_PER_OZ = .20  # Extra adverse assumed fills
SPLITS = (.55, .70, .85)
QUANTILES = (.50, .65, .80, .90, .95)
SIDES = ('both', 'long', 'short')

@dataclass(frozen=True)
class Barrier:
    horizon: int
    stop_atr: float
    reward_ratio: float

    @property
    def key(self):
        return f'h{self.horizon}_sl{self.stop_atr:g}_r{self.reward_ratio:g}'

SPECS = tuple(Barrier(h, 1., r) for h in (4, 8) for r in (1.5, 2.0))


def sha256(p: Path):
    d=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): d.update(c)
    return d.hexdigest()


def utc(t):
    return datetime.fromtimestamp(int(t), tz=timezone.utc).isoformat(timespec='minutes')


def read_history(path):
    df = pd.read_csv(path)
    columns = ('time','open','high','low','close','tick_volume','spread')
    if not set(columns).issubset(df.columns):
        raise ValueError('Required columns: '+', '.join(columns))
    for col in columns: df[col] = pd.to_numeric(df[col],errors='raise')
    if df[list(columns)].isna().any().any(): raise ValueError('Non-numeric/missing data')
    df = df.sort_values('time').drop_duplicates('time',keep='last').reset_index(drop=True)
    if len(df)<6000: raise ValueError('At least 6000 bars required for reliable chronology')
    if (df.time.diff().iloc[1:]<=0).any(): raise ValueError('Non-increasing time')
    if not (df.high >= df[['open','low','close']].max(axis=1)).all():
        raise ValueError('Invalid highs')
    if not (df.low <= df[['open','high','close']].min(axis=1)).all():
        raise ValueError('Invalid lows')
    if (df.spread<0).any(): raise ValueError('Negative spread')
    return df


def features(df):
    """Every row i uses only OHLCV data from closed candles at or before i."""
    close, high, low, op = (df[x] for x in ('close','high','low','open'))
    prev=close.shift(1)
    true_range = pd.concat([high-low,(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    atr = true_range.rolling(20,min_periods=20).mean().clip(lower=.02)
    ret=close.diff()
    body=close-op
    f=pd.DataFrame(index=df.index)
    for k in (0,1,2,3,4,5,7,11):
        f[f'ret_{k}'] = ret.shift(k)/atr.shift(k)
        f[f'body_{k}'] = body.shift(k)/atr.shift(k)
    f['range_atr'] = (high-low)/atr
    f['upper_wick'] = (high-pd.concat([close,op],axis=1).max(axis=1))/atr
    f['lower_wick'] = (pd.concat([close,op],axis=1).min(axis=1)-low)/atr
    f['close_location'] = (close-low)/(high-low).clip(lower=.01)
    f['atr'] = atr
    f['spread_atr_assumed'] = df.spread * POINT_VALUE / atr
    for n in (3,6,12,24,48,96):
        f[f'trend_{n}']=(close-close.shift(n))/atr
        f[f'vol_{n}']=ret.rolling(n,min_periods=n).std()/atr
    for n in (12,48):
        f[f'zprice_{n}']=(close-close.rolling(n).mean())/(close.rolling(n).std()+.01)
        f[f'breakout_{n}']=(close-high.shift(1).rolling(n).max())/atr
        f[f'breakdown_{n}']=(close-low.shift(1).rolling(n).min())/atr
    delta=close.diff()
    avgup=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    avgdn=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    f['rsi_14']=100-100/(1+avgup/(avgdn+.000001))
    f['volume_ratio']=np.log1p(df.tick_volume)/np.log1p(df.tick_volume.rolling(48,min_periods=48).median())
    t=df.time.to_numpy()
    f['hour_sin']=np.sin(2*np.pi*(t%86400)/86400)
    f['hour_cos']=np.cos(2*np.pi*(t%86400)/86400)
    f['weekday']=pd.to_datetime(df.time,unit='s',utc=True).dt.dayofweek
    # Explicit recent-break feature: no hidden look ahead, only prior time stamps.
    f['gap_in_last_20']=((df.time.diff()!=900).astype(int).rolling(20,min_periods=20).max())
    return f.replace([np.inf,-np.inf],np.nan),atr


def contiguous(df, horizon):
    """True iff bars i..i+h exist at exactly 15 minute intervals."""
    times=df.time.to_numpy(dtype=np.int64)
    valid=np.ones(len(df),dtype=bool)
    for offset in range(1,horizon+1):
        same=np.zeros(len(df),dtype=bool)
        same[:-offset] = (times[offset:] - times[offset-1:-1] == 900)
        valid &= same
    return valid


def label_barriers(df, atr, spec:Barrier):
    """Bid OHLC assumption. Stop prioritized when stop+TP touch same bar.

    Signal at bar i CLOSE. Entry next bar i+1 OPEN. For BUY, entry at ASK
    open+spread+slip and exits at BID. For SELL, entry at BID open-slip and
    exits at ASK (bid+spread). Commission and exit-slip included in outcomes.
    Gaps within horizon are excluded. Worse-than-stop OPEN prices are honored.
    Intrabar tick ordering is UNKNOWN; both-hit assigned adverse stop.
    """
    n=len(df); h=spec.horizon
    valid=contiguous(df,h) & atr.notna().to_numpy()
    a=atr.to_numpy(dtype=float)
    op=df.open.to_numpy(dtype=float); hi=df.high.to_numpy(dtype=float)
    lo=df.low.to_numpy(dtype=float); cl=df.close.to_numpy(dtype=float)
    sp=df.spread.to_numpy(dtype=float)*POINT_VALUE
    next_open=np.r_[op[1:],np.nan]
    next_sp=np.r_[sp[1:],np.nan]
    entry_buy=next_open+next_sp+ENTRY_SLIP
    entry_sell=next_open-ENTRY_SLIP
    dist=spec.stop_atr*a
    buy_sl=entry_buy-dist; buy_tp=entry_buy+dist*spec.reward_ratio
    sell_sl=entry_sell+dist; sell_tp=entry_sell-dist*spec.reward_ratio
    b_out=np.full(n,np.nan); s_out=np.full(n,np.nan)
    b_tp=np.zeros(n,dtype=np.int8); s_tp=np.zeros(n,dtype=np.int8)
    b_exit=np.full(n,-1,dtype=int); s_exit=np.full(n,-1,dtype=int)
    b_event=np.full(n,'INVALID',dtype='U16'); s_event=np.full(n,'INVALID',dtype='U16')
    b_active=valid.copy(); s_active=valid.copy()
    for offset in range(1,h+1):
        until=n-offset
        # If gap occurs anywhere in target span, the entire sample invalidated later.
        buy_stop=b_active[:until] & (lo[offset:]<=buy_sl[:until])
        buy_collision=buy_stop & (hi[offset:]>=buy_tp[:until])
        buy_take=b_active[:until] & (hi[offset:]>=buy_tp[:until]) & ~buy_stop
        sell_ask_hi=hi[offset:]+sp[offset:]
        sell_ask_lo=lo[offset:]+sp[offset:]
        sell_stop=s_active[:until] & (sell_ask_hi>=sell_sl[:until])
        sell_collision=sell_stop & (sell_ask_lo<=sell_tp[:until])
        sell_take=s_active[:until] & (sell_ask_lo<=sell_tp[:until]) & ~sell_stop
        ix=np.where(buy_stop)[0]
        if len(ix):
            # Slippage at stop plus gap-through on stop, never optimistic better open.
            fill=np.minimum(buy_sl[ix],op[ix+offset])-EXIT_SLIP
            b_out[ix]=fill-entry_buy[ix]-COMMISSION_PRICE_OZ
            b_exit[ix]=ix+offset; b_event[ix]=np.where(buy_collision[ix],'STOP_COLLISION','STOP')
        ix=np.where(buy_take)[0]
        if len(ix):
            b_out[ix]=buy_tp[ix]-EXIT_SLIP-entry_buy[ix]-COMMISSION_PRICE_OZ
            b_tp[ix]=1; b_exit[ix]=ix+offset; b_event[ix]='TARGET'
        ix=np.where(sell_stop)[0]
        if len(ix):
            fill=np.maximum(sell_sl[ix],op[ix+offset]+sp[ix+offset])+EXIT_SLIP
            s_out[ix]=entry_sell[ix]-fill-COMMISSION_PRICE_OZ
            s_exit[ix]=ix+offset; s_event[ix]=np.where(sell_collision[ix],'STOP_COLLISION','STOP')
        ix=np.where(sell_take)[0]
        if len(ix):
            s_out[ix]=entry_sell[ix]-sell_tp[ix]-EXIT_SLIP-COMMISSION_PRICE_OZ
            s_tp[ix]=1; s_exit[ix]=ix+offset; s_event[ix]='TARGET'
        b_active[:until] &= ~(buy_stop|buy_take)
        s_active[:until] &= ~(sell_stop|sell_take)
    idx=np.where(b_active & valid)[0]
    if len(idx):
        b_out[idx]=cl[idx+h]-EXIT_SLIP-entry_buy[idx]-COMMISSION_PRICE_OZ
        b_exit[idx]=idx+h; b_event[idx]='TIMEOUT'
    idx=np.where(s_active & valid)[0]
    if len(idx):
        s_out[idx]=entry_sell[idx]-(cl[idx+h]+sp[idx+h]+EXIT_SLIP)-COMMISSION_PRICE_OZ
        s_exit[idx]=idx+h; s_event[idx]='TIMEOUT'
    # Ineligible entries must not retain partial labels.
    for net,p,tp,ev in ((b_out,b_exit,b_tp,b_event),(s_out,s_exit,s_tp,s_event)):
        net[~valid]=np.nan; p[~valid]=-1; tp[~valid]=0; ev[~valid]='INVALID'
    return {'valid':valid,
            'buy':{'net':b_out,'tp':b_tp,'exit':b_exit,'event':b_event},
            'sell':{'net':s_out,'tp':s_tp,'exit':s_exit,'event':s_event}}


def make_splits(n,h):
    bounds=[0,int(SPLITS[0]*n),int(SPLITS[1]*n),int(SPLITS[2]*n),n]
    # Drop final h signal slots in EACH block. Features may use earlier history.
    return {k:np.arange(bounds[i],max(bounds[i],bounds[i+1]-h),dtype=int)
            for i,k in enumerate(('train','calibration','validation','holdout'))}


def calibrate_p(p_cal,y_cal,p_val,p_test):
    """Platt calibration ONLY on calibration block; independent of validation/test."""
    if len(np.unique(y_cal))<2: raise ValueError('Calibration targets have one class')
    def logit(x):
        z=np.clip(x,1e-6,1-1e-6)
        return np.log(z/(1-z)).reshape(-1,1)
    model=LogisticRegression(max_iter=300,C=1.0,solver='lbfgs')
    model.fit(logit(p_cal),y_cal)
    return (model.predict_proba(logit(p_cal))[:,1],
            model.predict_proba(logit(p_val))[:,1],
            model.predict_proba(logit(p_test))[:,1])


def odds_metrics(y,p):
    if len(y)==0: return None
    return {'n':len(y),'tp_base_rate':round(float(y.mean()),5),
            'brier':round(float(brier_score_loss(y,p)),5),
            'auc':round(float(roc_auc_score(y,p)),5) if len(np.unique(y))==2 else None}


def select_backtest(df,ids,outcomes,prob,thresholds,allowed):
    """One trade at most; transaction exists only after a closed-bar decision."""
    trade=[]; last_exit=-1
    for i in ids:
        i=int(i)
        if i<last_exit:continue
        options=[]
        for side in ('buy','sell'):
            if allowed=='long' and side=='sell':continue
            if allowed=='short' and side=='buy':continue
            pp=prob[side].get(i)
            if pp is not None and pp>=thresholds[side]: options.append((pp-thresholds[side],side,pp))
        if not options: continue
        # If both predict hitting their TP, choose greater margin above threshold.
        _,side,pp=max(options,key=lambda x:(x[0],x[2]))
        row=outcomes[side]
        if row['exit'][i]<0 or not np.isfinite(row['net'][i]):
            raise AssertionError('Invalid virtual trade')
        last_exit=int(row['exit'][i])
        trade.append({'decision_index':i,'signal_time_utc':utc(df.time.iat[i]),
                      'entry_time_utc':utc(df.time.iat[i+1]),
                      'exit_time_utc':utc(df.time.iat[last_exit]),
                      'exit_day_utc':utc(df.time.iat[last_exit])[:10],
                      'side':side.upper(),'event':str(row['event'][i]),
                      'p_tp_calibrated':round(float(pp),6),
                      'net_usd_per_oz_assumed':round(float(row['net'][i]),5),
                      'pnl_usd_assumed_fixed_001_lot':round(float(row['net'][i])*CONTRACT_OZ*LOT,5),
                      'hold_bars':last_exit-i})
    return trade


def metrics(trades,full_day_count):
    val=np.array([x['pnl_usd_assumed_fixed_001_lot'] for x in trades])
    days={t['exit_day_utc'] for t in trades}
    basic={'signals':len(trades),'active_days':len(days),'test_trading_days':int(full_day_count),
           'sum_usd_fixed_001_lot':round(float(val.sum()),3),
           'avg_usd_per_calendar_trading_day':round(float(val.sum()/max(full_day_count,1)),3),
           'days_ge_50_usd':0,'net_expectancy_usd_per_trade':round(float(val.mean()),3) if len(val) else None,
           'win_pct':round(float(100*np.mean(val>0)),3) if len(val) else None,
           'profit_factor':None,'max_closed_trade_drawdown_usd':0.,
           'ambiguous_touch_count':sum(x['event']=='STOP_COLLISION' for x in trades)}
    if len(val):
        gain=float(np.clip(val,0,None).sum());loss=float(-np.clip(val,None,0).sum())
        basic['profit_factor']=round(gain/loss,4) if loss else None
        balance=np.r_[0,np.cumsum(val)]
        basic['max_closed_trade_drawdown_usd']=round(float(np.max(np.maximum.accumulate(balance)-balance)),3)
        dtotal={}
        for t in trades:dtotal[t['exit_day_utc']]=dtotal.get(t['exit_day_utc'],0)+t['pnl_usd_assumed_fixed_001_lot']
        basic['days_ge_50_usd']=sum(v>=50 for v in dtotal.values())
    return basic


def daily_bootstrap_lower(trades,n=1000,seed=SEED):
    """Bootstrap daily P&L clusters, 5th percentile of profit/trade ratio;
    more conservative than naive independent-trade bootstrap (still approximate).
    """
    if not trades:return None
    groups={}
    for t in trades:groups.setdefault(t['exit_day_utc'],[]).append(t['pnl_usd_assumed_fixed_001_lot'])
    if len(groups)<10:return None
    g=list(groups.values());gain=np.array([sum(v) for v in g]); cnt=np.array([len(v) for v in g])
    rng=np.random.default_rng(seed)
    draws=rng.integers(0,len(g),(n,len(g)))
    mu=np.sum(gain[draws],axis=1)/np.sum(cnt[draws],axis=1)
    return round(float(np.quantile(mu,.05)),4)


def time_robustness(trades,median_validation_index):
    halves=[[],[]]
    for t in trades:
        halves[int(t['decision_index']>=median_validation_index)].append(t)
    result=[]
    for part in halves:
        z=metrics(part,max(1,len({t['exit_day_utc'] for t in part})))
        result.append({'signals':z['signals'],'active_days':z['active_days'],
                       'net_usd':z['sum_usd_fixed_001_lot'],'profit_factor':z['profit_factor']})
    return result


def gate(m,ci,halves,stress_sum):
    # Require positive edge in BOTH chronological validation halves as well.
    parts_good=all(z['signals']>=30 and z['active_days']>=10 and
                   z['net_usd']>0 and z['profit_factor'] is not None and
                   z['profit_factor']>=1.0 for z in halves)
    return (parts_good and stress_sum>0 and m['signals']>=MIN_TRADES and m['active_days']>=MIN_DAYS and
            m['profit_factor'] is not None and m['profit_factor']>=MIN_PF and
            m['sum_usd_fixed_001_lot']>0 and ci is not None and ci>0)


def scene_message(report):
    if report['selected_strategy'] is None:
        return ('گزارش تاریخی آفلاین. در آزمون اعتبارسنجی، هیچ روش خرید یا فروش '
                'شرایط سودآوری و اطمینان تعیین‌شده را نگذراند. وضعیت: صبر. '
                'این سیستم مجوز سیگنال معاملاتی ندارد و به متاتریدر متصل نیست.')
    return ('گزارش تاریخی آفلاین. یک روش بر اساس داده‌های اعتبارسنجی انتخاب شد، '
            'ولی آزمون نهایی مستقل و دمو شرط صدور سیگنال زنده است. '
            'از این گزارش دستور خرید یا فروش صادر نمی‌شود.')


def run(path:Path,outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True)
    df=read_history(path); f,atr=features(df)
    cols=list(f.columns); x=f.to_numpy(dtype=float)
    n=len(df);report={'name':'AMIN Candle Voice V3 — TP-before-SL research',
        'status':STATUS,'input':{'file':path.name,'sha256':sha256(path),'bars':n,
             'start_utc':utc(df.time.iloc[0]),'end_utc':utc(df.time.iloc[-1]),
             'discontinuous_15m_intervals':int((df.time.diff().iloc[1:]!=900).sum())},
        'model':{'algorithm':'Two fixed models: TP probability classifier and direct net-PnL regressor',
            'feature_count':len(cols),'features':cols,'train_cal_val_holdout_split':list(SPLITS)+[1.0],
            'bootstrap':'1000 daily-block bootstrap resamples; 5th percentile of net expectancy',
            'no_future_leakage':'Features use closed bars through t; labels use t+1..t+h; purge h at each boundary',
            'entry':'next M15 candle OPEN; hypothetical market execution',
            'barrier':'bid/ask assumed; stop first if both extremes touched in same bar; stop worse on gap',
            'exit':'first TP or SL, else timeout at h-th bar CLOSE',
            'duration_minutes':[60,120]},
        'cost_assumptions_unverified':{'quotes_assumed':'OHLC=bid','spread_point_price':POINT_VALUE,
             'spread':'historical broker column applied on entry BUY / exit SELL; also short stop checks',
             'entry_slippage_price_per_oz':ENTRY_SLIP,'exit_slippage_price_per_oz':EXIT_SLIP,
             'commission_round_trip_usd_per_1_lot':COMMISSION_PER_LOT,
             'contract_size_oz_per_1_lot':CONTRACT_OZ,'fixed_lot_scenario':LOT},
        'selection_policy':{'model_parameters':'fixed ex ante','quantiles':QUANTILES,
          'side_filters':SIDES,'minimum_validation_trades':MIN_TRADES,
          'minimum_validation_active_days':MIN_DAYS,'minimum_validation_profit_factor':MIN_PF,
          'require_positive_daily_bootstrap_5th_percentile':True,
          'require_positive_each_validation_chronological_half':True,
          'stress_extra_cost_price_per_oz':STRESS_EXTRA_COST_PRICE_PER_OZ,
          'holdout_untouched_if_no_validated_model':True},
        'spec_results':{},'selected_strategy':None,'holdout':{'status':'NOT_RUN'},
        'live_signal_approved':False,'mt5_tested':False,'orders_sent':0,
        'risks':['Spread-point unit, commission, slip, quote side and contract size UNVERIFIED with live account',
             '15-minute OHLC lacks the exact intrabar high/low sequence; both-hit treated as a loss',
             'No tick-confirmed fill, overnight swap, margin rules, news slippage or live latency',
             'Signal at bar close may not fill next bar open; results are research approximations',
             'The $50/day on $1000 target is a 5% daily return; NOT established']}
    best=None
    audit=[]
    for spec in SPECS:
        outcomes=label_barriers(df,atr,spec)
        valid=outcomes['valid'] & np.isfinite(x).all(axis=1)
        split=make_splits(n,spec.horizon)
        idx={name:arr[valid[arr]] for name,arr in split.items()}
        sreport={'config':asdict(spec),
                 'historical_ambiguous_touch_counts':{side:int((outcomes[side]['event']=='STOP_COLLISION').sum()) for side in ('buy','sell')},
                 'valid_samples_by_block':{k:len(v) for k,v in idx.items()},
                 'side_models':{},'candidate_count':0,'passed_candidate_count':0,
                 'validation_best_even_if_failed':None,'validation_best_passed':None}
        all_scores={'tp_probability':{},'expected_net_pnl':{}}
        # Calibrate and predict exactly once per side + spec, using separate time blocks.
        for side in ('buy','sell'):
            lab=outcomes[side]['tp']
            tr,ca,va,te=[idx[k] for k in ('train','calibration','validation','holdout')]
            if len(tr)<1000 or len(ca)<500 or len(va)<500 or len(np.unique(lab[tr]))<2:
                sreport['side_models'][side]={'error':'Insufficient varying label observations'}
                break
            clf=HistGradientBoostingClassifier(max_iter=65,max_leaf_nodes=9,max_depth=4,
                   learning_rate=.05,min_samples_leaf=100,l2_regularization=12,
                   random_state=SEED,early_stopping=False)
            clf.fit(x[tr],lab[tr])
            pcal=clf.predict_proba(x[ca])[:,1]
            pval=clf.predict_proba(x[va])[:,1]
            ptest=clf.predict_proba(x[te])[:,1]
            calibrated_cal,calibrated_val,calibrated_test=calibrate_p(pcal,lab[ca],pval,ptest)
            all_scores['tp_probability'][side]={'calibration':dict(zip(ca,calibrated_cal)),
                             'validation':dict(zip(va,calibrated_val)),
                             'holdout':dict(zip(te,calibrated_test))}
            all_scores['tp_probability'][side]['qthresholds']={str(q):float(np.quantile(calibrated_cal,q)) for q in QUANTILES}
            # Second method: predict normalized NET P&L, not direction or TP event.
            # P&L is normalized by the ATR KNOWN at the decision timestamp.
            y_tr=np.clip(outcomes[side]['net'][tr]/atr.iloc[tr].to_numpy(),-8,8)
            reg=HistGradientBoostingRegressor(max_iter=65,max_leaf_nodes=9,max_depth=4,
                     learning_rate=.05,min_samples_leaf=100,l2_regularization=12,
                     random_state=SEED,early_stopping=False,loss='squared_error')
            reg.fit(x[tr],y_tr)
            rcal=reg.predict(x[ca]);rval=reg.predict(x[va]);rtest=reg.predict(x[te])
            all_scores['expected_net_pnl'][side]={'calibration':dict(zip(ca,rcal)),
                             'validation':dict(zip(va,rval)),
                             'holdout':dict(zip(te,rtest))}
            # Positive predicted unit-ATR net P&L and selection ranks from CALIBRATION only.
            all_scores['expected_net_pnl'][side]['qthresholds']={str(q):float(max(.05,np.quantile(rcal,q))) for q in QUANTILES}
            sreport['side_models'][side]={'tp_probability':{
                    'calibration_metrics':odds_metrics(lab[ca],calibrated_cal),
                    'validation_metrics':odds_metrics(lab[va],calibrated_val),
                    'calibration_quantile_thresholds':{str(k):round(v,6) for k,v in all_scores['tp_probability'][side]['qthresholds'].items()}},
                    'net_pnl_regression':{
                    'mean_predicted_unit_atr_validation':round(float(rval.mean()),5),
                    'actual_mean_unit_atr_validation':round(float(np.mean(outcomes[side]['net'][va]/atr.iloc[va].to_numpy())),5),
                    'validation_correlation':round(float(np.corrcoef(rval,outcomes[side]['net'][va]/atr.iloc[va].to_numpy())[0,1]),5),
                    'calibration_quantile_thresholds':{str(k):round(v,6) for k,v in all_scores['expected_net_pnl'][side]['qthresholds'].items()}}}

        if set(all_scores['tp_probability'])!=set(('buy','sell')) or set(all_scores['expected_net_pnl'])!=set(('buy','sell')):
            sreport['error']='Training failed';report['spec_results'][spec.key]=sreport
            continue
        va=idx['validation'];valid_days=len(np.unique(df.time.iloc[split['validation']]//86400))
        midpoint=int(va[len(va)//2])
        for method in ('tp_probability','expected_net_pnl'):
            scores=all_scores[method]
            pb={s:scores[s]['validation'] for s in ('buy','sell')}
            for q in QUANTILES:
                threshold={s:scores[s]['qthresholds'][str(q)] for s in ('buy','sell')}
                for allowed in SIDES:
                    trds=select_backtest(df,va,outcomes,pb,threshold,allowed)
                    m=metrics(trds,valid_days)
                    ci=daily_bootstrap_lower(trds) if m['signals']>=MIN_TRADES and m['active_days']>=MIN_DAYS else None
                    halves=time_robustness(trds,midpoint)
                    # Additional stressed execution scenario beyond baseline slippage/spread.
                    stress_sum=round(m['sum_usd_fixed_001_lot']-len(trds)*STRESS_EXTRA_COST_PRICE_PER_OZ*CONTRACT_OZ*LOT,3)
                    passed=gate(m,ci,halves,stress_sum)
                    cand={'spec':spec.key,'method':method,'side_filter':allowed,'quantile':q,
                          'score_cutoffs':{k:round(v,6) for k,v in threshold.items()},
                          'validation':m,'validation_bootstrap_lower_usd_per_trade':ci,
                          'chronological_validation_halves':halves,
                          'stressed_net_usd_fixed_001_lot':stress_sum,
                          'passed_validation_gate':passed}
                    sreport['candidate_count']+=1
                    audit.append({'spec':spec.key,'method':method,'side':allowed,'quantile':q,
                       'signals':m['signals'],'active_days':m['active_days'],
                       'net_usd':m['sum_usd_fixed_001_lot'],'pf':m['profit_factor'],
                       'net_robustness_daily_bootstrap_lower':ci,
                       'first_half_net_usd':halves[0]['net_usd'],
                       'second_half_net_usd':halves[1]['net_usd'],
                       'stressed_net_usd':stress_sum,'ambiguous_stop_count':m['ambiguous_touch_count'],
                       'pass_gate':passed})
                    if passed: sreport['passed_candidate_count']+=1
                    if sreport['validation_best_even_if_failed'] is None or m['sum_usd_fixed_001_lot']>sreport['validation_best_even_if_failed']['validation']['sum_usd_fixed_001_lot']:
                        sreport['validation_best_even_if_failed']=cand
                    if passed:
                        if sreport['validation_best_passed'] is None or m['sum_usd_fixed_001_lot']>sreport['validation_best_passed']['validation']['sum_usd_fixed_001_lot']:
                            sreport['validation_best_passed']=cand
                        if best is None or (m['sum_usd_fixed_001_lot'], m['profit_factor'])>(best['candidate']['validation']['sum_usd_fixed_001_lot'],best['candidate']['validation']['profit_factor']):
                            best={'candidate':cand,'outcomes':outcomes,'scores':scores,'spec':spec,'test_ids':idx['holdout']}
        report['spec_results'][spec.key]=sreport
    if best:
        c=best['candidate'];report['selected_strategy']=c
        t=best['scores'];cut={s:t[s]['qthresholds'][str(c['quantile'])] for s in ('buy','sell')}
        tprob={s:t[s]['holdout'] for s in ('buy','sell')}
        trades=select_backtest(df,best['test_ids'],best['outcomes'],tprob,cut,c['side_filter'])
        holdout_days=len(np.unique(df.time.iloc[make_splits(len(df),best['spec'].horizon)['holdout']]//86400))
        m=metrics(trades,holdout_days);ci=daily_bootstrap_lower(trades)
        halves=time_robustness(trades,int(best['test_ids'][len(best['test_ids'])//2]))
        stress_sum=round(m['sum_usd_fixed_001_lot']-len(trades)*STRESS_EXTRA_COST_PRICE_PER_OZ*CONTRACT_OZ*LOT,3)
        report['holdout']={'status':'TESTED_LOCKED_VALIDATED_STRATEGY','metrics':m,'bootstrap_lower_usd_per_trade':ci,
          'passes_gate':gate(m,ci,halves,stress_sum),'chronological_halves':halves,'stressed_net_usd':stress_sum,'warning':'Heldout is one short historical block; not a live expectation'}
        pd.DataFrame(trades).to_csv(outdir/'locked_holdout_trades.csv',index=False,encoding='utf-8-sig')
    else:
        report['holdout']={'status':'NOT_TESTED_AS_NO_STRATEGY_PASSED_VALIDATION',
          'reason':'No validation-positive, PF>=1.2, significant expectancy and minimum sample count strategy. Holdout not used for research tuning.'}
    pd.DataFrame(audit).to_csv(outdir/'all_validation_candidates.csv',index=False,encoding='utf-8-sig')
    report['research_audit']={'validation_candidates_count':len(audit),
        'passing_validation_candidates_count':sum(t['pass_gate'] for t in audit),
        'audit_file':'all_validation_candidates.csv'}
    report['historical_voice_message']=scene_message(report)
    (outdir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (outdir/'voice_message_fa.txt').write_text(report['historical_voice_message']+'\n',encoding='utf-8')
    render_html(report,outdir/'dashboard_fa.html')
    print(json.dumps({'status':report['status'],'bars':n,'configs':list(report['spec_results']),
                      'selected_strategy':report['selected_strategy']['spec'] if report['selected_strategy'] else None,
                      'holdout':report['holdout']['status'],'outdir':str(outdir)},ensure_ascii=False))
    return report


def render_html(r,out):
    x=[]
    for key,z in r['spec_results'].items():
        c=z['validation_best_even_if_failed']
        if c:
            m=c['validation'];v=lambda a:html.escape(str(a))
            x.append(f'<tr><td>{v(key)}</td><td>{m["signals"]}</td><td>{m["sum_usd_fixed_001_lot"]}</td><td>{m["profit_factor"]}</td><td>{z["passed_candidate_count"]}</td></tr>')
    selection='هیچ مدلی در اعتبارسنجی قبول نشد؛ سیگنال معاملاتی صادر نمی‌شود.' if r['selected_strategy'] is None else 'مدل در اعتبارسنجی انتخاب شد؛ نتیجه آزمون نهایی را در JSON ببینید. مجوز زنده وجود ندارد.'
    voice=html.escape(r['historical_voice_message'])
    page=f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>کندل سخنگوی امین V3</title><style>
    body{{font-family:Tahoma,Arial,sans-serif;background:#101722;color:#e6edf4;padding:18px;line-height:1.9}}
    main{{max-width:900px;margin:auto}}.panel{{background:#202c3b;border:1px solid #3a4759;padding:18px;border-radius:14px;margin:16px 0}}
    h1{{font-size:1.45rem}}.warn{{color:#ffcd7a}}table{{width:100%;border-collapse:collapse;font-size:.85rem;min-width:550px}}td,th{{border-bottom:1px solid #536170;padding:10px;text-align:right}}.overflow{{overflow-x:auto}}
    button{{font:inherit;border:0;padding:10px 18px;border-radius:8px;background:#a1b7d2;color:#0e1824;cursor:pointer}}
    small{{opacity:.82}} </style></head><body><main><h1>کندل‌های سخنگوی امین — نسخه پژوهشی ۳</h1>
    <div class="panel"><strong class="warn">توجه: آفلاین؛ بدون اتصال زنده و بدون ارسال سفارش</strong><p>{html.escape(selection)}</p>
    <small>آرشیو: {html.escape(r['input']['start_utc'])} تا {html.escape(r['input']['end_utc'])} • {r['input']['bars']:,} کندل ۱۵ دقیقه</small></div>
    <div class="panel"><h2>گزارش گفتاری تاریخی</h2><p id="message">{voice}</p><button onclick="play()">🔊 پخش گفتار فارسی دستگاه</button><button onclick="speechSynthesis.cancel()">توقف</button><p id="audioStatus"><small>تولید صدا فقط با پشتیبانی گفتار مرورگر و صدای فارسی نصب‌شده امکان‌پذیر است؛ روی دستگاه شما آزمون نشده.</small></p></div>
    <div class="panel"><h2>بهترین نتیجه اعتبارسنجی هر تنظیم — حتی اگر مردود</h2><div class="overflow"><table><thead><tr><th>پارامتر</th><th>معامله</th><th>سود خالص فرضی دلار (۰٫۰۱ لات)</th><th>Profit factor</th><th>روش‌های قبول‌شده</th></tr></thead><tbody>{''.join(x)}</tbody></table></div></div>
    <div class="panel"><h2>تفاوت هشدار با سیگنال</h2><p>ورود فقط بعد از قبولی در اعتبارسنجی، آزمون مستقل، و آزمایش جداگانه MT5 دمو مطرح می‌شود. هیچ نتیجه‌ای در این صفحه زنده نیست.</p><small>فرض‌های کارگزاری: هر پوینت اسپرد ۰٫۰۱ قیمت، ۱ لات = ۱۰۰ اونس، ۷ دلار کمیسیون در لات کامل، ۰٫۰۵ قیمت لغزش در هر سمت. همه نیازمند تأیید از خود حساب هستند.</small></div>
    </main><script>function play(){{if(!('speechSynthesis' in window)){{document.getElementById('audioStatus').textContent='مرورگر صدای گفتاری ندارد';return}}speechSynthesis.cancel();let u=new SpeechSynthesisUtterance(document.getElementById('message').textContent);u.lang='fa-IR';u.rate=.9;speechSynthesis.speak(u);document.getElementById('audioStatus').textContent='درخواست پخش به مرورگر ارسال شد؛ کیفیت صدای فارسی به دستگاه بستگی دارد';}}</script></body></html>'''
    out.write_text(page,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('amin_v3_results'))
    a=p.parse_args()
    run(a.csv,a.output_dir)

if __name__=='__main__':main()
