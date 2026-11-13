#!/usr/bin/env python3
"""Research-only robust filter selection on 70% train and untouched 30% test.

No instructor rules are altered or claimed. No broker orders.
Select solely on train with minimum trades and positive net after assumed
spread, then independently evaluate the chosen configuration on test.
"""
import csv,json,sys
from pathlib import Path
from artin_non_teacher_proxy_backtest import load,simulate,signal

def filtered_signal(bars,i,method,minimum_body,trend_window):
    side=signal(bars,i,method)
    if not side:return 0
    o,h,l,c=bars[i][1:]
    if abs(c-o)<minimum_body:return 0
    if trend_window:
        if i<trend_window:return 0
        if bars[i][0]-bars[i-trend_window][0]!=900*trend_window:return 0
        past=bars[i-trend_window][4]
        if side*(c-past)<=0:return 0
    return side

def replay(bars,method,spread,minimum_body,trend_window):
    # Reuse the same execution simulator by swapping only the candidate filter
    # at module scope; all fills and risk parameters remain unchanged.
    import artin_non_teacher_proxy_backtest as base
    original=base.signal
    try:
        base.signal=lambda a,i,m:filtered_signal(a,i,m,minimum_body,trend_window)
        return simulate(bars,method,spread)
    finally:base.signal=original

def summary(x):
    return {k:v for k,v in x.items() if k!='trades_detail'}

def main(src,out):
    bars=load(src)
    split=int(len(bars)*.7)
    train,test=bars[:split],bars[split:]
    spread=.3
    candidates=[]
    for method in ('three_candle_raw','fvg_raw'):
        for body in (0,1,2,3,5):
            for trend in (0,4,8,16):
                result=replay(train,method,spread,body,trend)
                candidates.append((method,body,trend,result))
    # Select only from training; do not peek at test for parameter choice.
    valid=[c for c in candidates if c[3]['trades']>=100 and
           c[3]['net_usd_per_oz']>0 and
           c[3]['max_closed_trade_drawdown_usd_per_oz']>0]
    valid.sort(key=lambda c:(c[3]['net_usd_per_oz']/c[3]['max_closed_trade_drawdown_usd_per_oz'],
                             c[3]['net_usd_per_oz']),reverse=True)
    chosen=valid[0] if valid else None
    result={'schema':'artin_research_walkforward_v1',
      'data':'Dukascopy public BID M15; NOT Eplanet',
      'teacher_methods_validated':False,'broker_orders':0,
      'split':'first 70% train; final 30% untouched holdout',
      'assumed_spread_usd_per_oz':spread,
      'candidate_count':len(candidates),
      'selection':'train positive net; >=100 trades; maximize train net/max drawdown',
      'candidate_training_summary':[{'method':m,'minimum_body':b,'trend_window':t,
             **summary(r)} for m,b,t,r in candidates],
      'selected':None,'holdout':None,'pass':False}
    if chosen:
        m,b,t,tr=chosen
        hold=replay(test,m,spread,b,t)
        result['selected']={'method':m,'minimum_body':b,'trend_window':t,'train':summary(tr)}
        result['holdout']=summary(hold)
        result['pass']=bool(hold['trades']>=30 and hold['net_usd_per_oz']>0 and
                            hold['gross_profit']>abs(hold['gross_loss']) and
                            hold['max_closed_trade_drawdown_usd_per_oz']>0)
    result['decision']='RESEARCH_CANDIDATE_ONLY' if result['pass'] else 'NO_REPEATABLE_PROFIT_SHOWN'
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='candidate_training_summary'},ensure_ascii=False,indent=2))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
