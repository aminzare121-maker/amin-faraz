#!/usr/bin/env python3
"""Transparent, NON-TEACHER proxy comparison on actual public BID M15 data.

Signals are experimental raw candle geometry, NOT any of the instructor's 13
methods. Execution: signal on closed candle, next candle OPEN; one trade at a
time; SL=5 USD/oz TP=10 USD/oz; max 16 bars; conservative stop-first tie.
BID-only data: modeled constant ask spread on BUY entry and SELL exit.
No MT5 orders. Results in USD per 1 troy oz (NOT per 1 lot).
"""
import csv,json,sys
from pathlib import Path

def load(p):
    a=[]
    for r in csv.DictReader(open(p,encoding="utf-8-sig",newline="")):
        t=int(r.get('timestamp') or r.get('time'))
        if t>10**11:t//=1000
        a.append((t,*(float(r[k]) for k in ('open','high','low','close'))))
    if len(a)<100:raise ValueError('INSUFFICIENT_DATA')
    return a

def signal(a,i,method):
    if i<2 or any(a[j][0]-a[j-1][0]!=900 for j in (i-1,i)):return 0
    x,y,z=a[i-2:i+1]
    if method=='three_candle_raw':
        d=[(b[4]>b[1])-(b[4]<b[1]) for b in (x,y,z)]
        return d[0] if d[0] and d.count(d[0])==3 else 0
    if method=='fvg_raw':
        if z[3]>x[2]:return 1
        if z[2]<x[3]:return -1
    return 0

def simulate(a,method,spread):
    trades=[];i=2;eligible=0
    while i<len(a)-1:
        side=signal(a,i,method)
        if not side:i+=1;continue
        eligible+=1
        # Never fill a signal until next candle. Avoid weekend gaps.
        if a[i+1][0]-a[i][0]!=900:i+=1;continue
        start=i+1
        entry=a[start][1]+(spread if side==1 else 0)
        stop=entry-side*5
        target=entry+side*10
        end=min(len(a),start+16)
        result=None
        for j in range(start,end):
            t,o,h,l,c=a[j]
            if j>start and t-a[j-1][0]!=900:
                # Exit at last known close, not across a market closure.
                j-=1;t,o,h,l,c=a[j];exit_price=c+(spread if side==-1 else 0);reason='GAP_EXIT';break
            # SELL exit prices use ask approximation; BUY exit prices BID.
            hi=h+(spread if side==-1 else 0)
            lo=l+(spread if side==-1 else 0)
            if side==1:
                hit_stop=lo<=stop;hit_tp=hi>=target
            else:
                hit_stop=hi>=stop;hit_tp=lo<=target
            if hit_stop:
                exit_price=stop;reason='STOP' if not hit_tp else 'STOP_FIRST_BOTH_HIT';break
            if hit_tp:exit_price=target;reason='TARGET';break
        else:
            j=end-1;exit_price=a[j][4]+(spread if side==-1 else 0);reason='TIME_EXIT'
        pnl=side*(exit_price-entry)
        trades.append({'signal_time':a[i][0],'entry_time':a[start][0],
          'exit_time':a[j][0],'side':'BUY' if side==1 else 'SELL',
          'entry':round(entry,5),'exit':round(exit_price,5),
          'pnl_usd_per_oz':round(pnl,5),'reason':reason})
        i=max(j+1,i+1)
    pnls=[x['pnl_usd_per_oz'] for x in trades]
    equity=0;peak=0;drawdown=0
    for p in pnls:
        equity+=p;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    return {'method':method,'spread_usd_per_oz':spread,'eligible_candidates_encountered':eligible,
      'trades':len(trades),'wins':sum(p>0 for p in pnls),
      'losses':sum(p<0 for p in pnls),'flat':sum(p==0 for p in pnls),
      'win_rate':round(sum(p>0 for p in pnls)/len(pnls),5) if pnls else None,
      'net_usd_per_oz':round(sum(pnls),5),
      'max_closed_trade_drawdown_usd_per_oz':round(drawdown,5),
      'gross_profit':round(sum(p for p in pnls if p>0),5),
      'gross_loss':round(sum(p for p in pnls if p<0),5),
      'trades_detail':trades}

def main(source,out):
    bars=load(source)
    cases=[simulate(bars,m,s) for m in ('three_candle_raw','fvg_raw') for s in (0.0,0.3,0.6)]
    result={'schema':'artin_non_teacher_proxy_comparison_v1',
      'data':'Dukascopy public XAUUSD M15 BID NOT Eplanet',
      'rows':len(bars),'one_year_sample':True,
      'teacher_13_methods_verified':False,'teacher_13_methods_pnl':None,
      'real_or_demo_broker_orders':0,'research_paper_only':True,
      'units':'USD per 1 troy ounce, not USD per MT5 lot',
      'rules':'NEXT_BAR_OPEN; 5 USD/oz stop; 10 USD/oz target; 16 M15 bars maximum; stop-first if both hit; no overlapping trades; constant spread sensitivity 0/0.3/0.6; no commission, slippage, swaps or volume sizing',
      'cases':cases}
    Path(out).write_text(json.dumps(result,indent=2))
    print(json.dumps({'rows':len(bars),'cases':[{k:v for k,v in c.items() if k!='trades_detail'} for c in cases]},indent=2))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
