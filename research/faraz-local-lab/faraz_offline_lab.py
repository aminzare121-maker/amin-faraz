#!/usr/bin/env python3
"""FARAZ: local, read-only M15 strategy screener; emits aggregate statistics only.

Runs without network, external libraries, broker accounts, MT5, orders, or file changes.
This is exploratory research, NOT a validated trading strategy or complete-year PnL.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

M15_SECONDS = 900
CONTRACT_OZ_PER_LOT = 100.0
LOT = 0.01
RISK_BUDGET_USD = 25.0  # 0.25% of a hypothetical $10,000, research only
SPREAD_PRICE = 0.50
SLIPPAGE_PRICE_EACH_SIDE = 0.20
COMMISSION_USD_PER_LOT_ROUNDTRIP = 10.0
HORIZON_BARS = 8
STOP_ATR_MULTIPLE = 1.5
FAMILIES = ('trend_pullback', 'range_reversion', 'compression_expansion')

@dataclass(frozen=True)
class Candle:
    t: int
    o: float
    h: float
    l: float
    c: float
    volume: float


def to_float(s: str) -> float:
    v = float(str(s).strip())
    if not math.isfinite(v):
        raise ValueError('Non-finite numeric field')
    return v


def load_csv(path: Path):
    candles=[]
    sha=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''):
            sha.update(chunk)
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        header=set(reader.fieldnames or [])
        needed={'time_raw_epoch','open','high','low','close'}
        if not needed<=header:
            raise ValueError('CSV must contain time_raw_epoch,open,high,low,close')
        if {'account','login','password','token'} & {str(h).lower() for h in header}:
            raise ValueError('CSV contains unexpected account/credential column; use prices-only export')
        for line, row in enumerate(reader,2):
            try:
                t=int(row['time_raw_epoch'])
                o,h,l,c=(to_float(row[k]) for k in ('open','high','low','close'))
                v=to_float(row.get('tick_volume') or 0)
                if t % M15_SECONDS or (candles and t<=candles[-1].t):
                    raise ValueError('non-M15, duplicate or out-of-order time')
                if min(o,h,l,c)<=0 or h<max(o,c,l) or l>min(o,c,h) or v<0:
                    raise ValueError('invalid OHLC or volume')
                candles.append(Candle(t,o,h,l,c,v))
            except (ValueError,TypeError,OverflowError) as exc:
                raise ValueError(f'Invalid input at CSV line {line}: {exc}') from exc
    if len(candles)<80:
        raise ValueError('Insufficient candles: at least 80 required for screening')
    return candles,sha.hexdigest()


def split_segments(candles):
    segments=[]; start=0
    for i in range(1,len(candles)):
        if candles[i].t-candles[i-1].t != M15_SECONDS:
            segments.append(candles[start:i]); start=i
    segments.append(candles[start:])
    return segments


def ema(xs, period):
    out=[]; state=None; alpha=2/(period+1)
    for x in xs:
        state=x if state is None else alpha*x+(1-alpha)*state
        out.append(state)
    return out


def signals(seg):
    n=len(seg)
    closes=[x.c for x in seg]
    em20=ema(closes,20); em60=ema(closes,60)
    true_ranges=[max(x.h-x.l,abs(x.h-seg[i-1].c),abs(x.l-seg[i-1].c)) if i else x.h-x.l for i,x in enumerate(seg)]
    out={f:[0]*n for f in FAMILIES}
    atr=[None]*n
    for i in range(60,n):
        prevtr=true_ranges[i-14:i]
        a=statistics.fmean(prevtr)
        atr[i]=a
        if a<=0: continue
        c=seg[i]; p=seg[i-1]
        # Rule A: re-entry in the direction of a moving-average trend after a pullback.
        if em20[i]>em60[i] and em20[i]>em20[i-3] and c.l<=em20[i] and c.c>em20[i] and c.c>c.o:
            out['trend_pullback'][i]=1
        elif em20[i]<em60[i] and em20[i]<em20[i-3] and c.h>=em20[i] and c.c<em20[i] and c.c<c.o:
            out['trend_pullback'][i]=-1
        # Rule B: low-trend, wide deviation from prior 20-candle distribution.
        pri=closes[i-20:i]
        avg=statistics.fmean(pri)
        sd=statistics.pstdev(pri)
        if abs(em20[i]-em60[i])<0.55*a and sd>0:
            if c.c < avg-2.0*sd and c.c<c.o:
                out['range_reversion'][i]=1
            elif c.c > avg+2.0*sd and c.c>c.o:
                out['range_reversion'][i]=-1
        # Rule C: volatility expansion *after* a compressed pre-signal period.
        shorter=statistics.fmean(true_ranges[i-10:i]); longer=statistics.fmean(true_ranges[i-40:i]); curr=c.h-c.l
        if longer>0 and shorter/longer < 0.7 and curr>1.6*longer:
            prior_hi=max(x.h for x in seg[i-10:i]); prior_lo=min(x.l for x in seg[i-10:i])
            if c.c>prior_hi and c.c>c.o: out['compression_expansion'][i]=1
            elif c.c<prior_lo and c.c<c.o: out['compression_expansion'][i]=-1
    return out,atr


def one_trade(seg, at, direction, atr):
    """The entry occurs at NEXT bar's open; one stop, otherwise time exit.

    Any gap before eight completed bars returns UNRESOLVED; segment ends there.
    There is no take profit, so SL/TP same-bar ambiguity is absent. Stops are
    conservatively checked before a bar-close horizon exit.
    """
    entry_idx=at+1
    if entry_idx>=len(seg):
        return None,'MISSED_ENTRY'
    if atr is None or atr<=0:
        return None,'INVALID_ATR'
    en_bid=seg[entry_idx].o
    # Bid OHLC assumption, explicit adverse spread / slip on each side.
    en_price=en_bid + SPREAD_PRICE+SLIPPAGE_PRICE_EACH_SIDE if direction==1 else en_bid-SLIPPAGE_PRICE_EACH_SIDE
    stop_dist=STOP_ATR_MULTIPLE*atr
    risk_nominal=stop_dist*CONTRACT_OZ_PER_LOT*LOT
    if risk_nominal+(SPREAD_PRICE+2*SLIPPAGE_PRICE_EACH_SIDE)*CONTRACT_OZ_PER_LOT*LOT+COMMISSION_USD_PER_LOT_ROUNDTRIP*LOT > RISK_BUDGET_USD:
        return None,'RISK_VETO'
    # Initial stop is based on the entry reference, never lookahead extrema.
    stop=en_bid-direction*stop_dist
    last_idx=entry_idx+HORIZON_BARS-1
    for j in range(entry_idx,min(last_idx,len(seg)-1)+1):
        b=seg[j]
        if direction==1 and b.l<=stop:
            exit_bid=min(b.o,stop)-SLIPPAGE_PRICE_EACH_SIDE  # unfavorable gap-through fill
            pnl=(exit_bid-en_price)*CONTRACT_OZ_PER_LOT*LOT - COMMISSION_USD_PER_LOT_ROUNDTRIP*LOT
            return (pnl,b.t,'STOP'),'RESOLVED'
        if direction==-1 and b.h>=stop:
            exit_ask=max(b.o,stop)+SPREAD_PRICE+SLIPPAGE_PRICE_EACH_SIDE
            pnl=(en_price-exit_ask)*CONTRACT_OZ_PER_LOT*LOT-COMMISSION_USD_PER_LOT_ROUNDTRIP*LOT
            return (pnl,b.t,'STOP'),'RESOLVED'
    if last_idx>=len(seg):
        return None,'UNRESOLVED_NEXT_GAP_OR_END'
    ex=seg[last_idx]
    ex_price=ex.c-SLIPPAGE_PRICE_EACH_SIDE if direction==1 else ex.c+SPREAD_PRICE+SLIPPAGE_PRICE_EACH_SIDE
    pnl=direction*(ex_price-en_price)*CONTRACT_OZ_PER_LOT*LOT-COMMISSION_USD_PER_LOT_ROUNDTRIP*LOT
    return (pnl,ex.t,'TIME'),'RESOLVED'


def screen(candles):
    segments=split_segments(candles)
    results={f:{'entries':0,'closed':0,'unresolved':0,'veto':0,'missed':0,'winning':0,'losing':0,'stop':0,'time_exit':0,'wins_usd':0.,'losses_usd':0.,'max_segment_dd_usd':0.,'quarters':defaultdict(lambda:{'closed':0,'pnl':0.})} for f in FAMILIES}
    for seg in segments:
        sig,atrs=signals(seg)
        for f in FAMILIES:
            r=results[f]
            i=60; seg_equity=0.; seg_peak=0.
            while i<len(seg):
                d=sig[f][i]
                if not d: i+=1;continue
                trade,status=one_trade(seg,i,d,atrs[i])
                if status=='MISSED_ENTRY':r['missed']+=1;i+=1;continue
                if status in ('RISK_VETO','INVALID_ATR'):r['veto']+=1;i+=1;continue
                r['entries']+=1
                if status=='UNRESOLVED_NEXT_GAP_OR_END':
                    r['unresolved']+=1
                    break  # Do not silently reset the unresolved equity within this segment.
                pnl,exit_t,exit_reason=trade
                r['closed']+=1;r['stop' if exit_reason=='STOP' else 'time_exit']+=1
                if pnl>0:r['winning']+=1;r['wins_usd']+=pnl
                elif pnl<0:r['losing']+=1;r['losses_usd']+=pnl
                seg_equity+=pnl; seg_peak=max(seg_peak,seg_equity)
                r['max_segment_dd_usd']=max(r['max_segment_dd_usd'],seg_peak-seg_equity)
                # Raw broker time label; not verified UTC.
                dt=datetime.fromtimestamp(exit_t,tz=timezone.utc)
                q=f'{dt.year}-Q{(dt.month-1)//3+1}'
                r['quarters'][q]['closed']+=1;r['quarters'][q]['pnl']+=pnl
                exit_idx=(exit_t-seg[0].t)//M15_SECONDS
                i=max(i+1,exit_idx+1)
    out=[]
    for family,r in results.items():
        gain=r['wins_usd'];loss=r['losses_usd'];known=gain+loss
        pf=gain/(-loss) if loss<0 else (None if gain==0 else None)
        quarters=[{'period_raw':q,'closed':v['closed'],'known_partial_net_usd':round(v['pnl'],2)} for q,v in sorted(r['quarters'].items())]
        out.append({'family':family,'observed_entries':r['entries'],'closed':r['closed'],'unresolved':r['unresolved'],'risk_veto':r['veto'],'unfilled_entry_due_to_segment_end':r['missed'],'winning_closed':r['winning'],'losing_closed':r['losing'],'stops_closed':r['stop'],'timed_closed':r['time_exit'],'known_partial_net_usd':round(known,2),'known_partial_profit_factor':round(pf,4) if pf is not None else None,'closed_expectancy_usd':round(known/r['closed'],4) if r['closed'] else None,'max_independent_segment_closed_dd_usd':round(r['max_segment_dd_usd'],2),'raw_label_quarters':quarters,'research_decision':'EXPLORATORY_ONLY_NOT_APPROVED'})
    return len(segments),out


def main(argv=None):
    p=argparse.ArgumentParser(description='FARAZ offline-only new hypothesis screener')
    p.add_argument('--csv',required=True,help='Absolute path to existing LOCAL prices-only CSV; never uploaded')
    p.add_argument('--out',required=True,help='Local path to aggregates-only JSON report')
    args=p.parse_args(argv)
    src=Path(args.csv).expanduser().resolve()
    dst=Path(args.out).expanduser().resolve()
    if src==dst: raise ValueError('Input and output must differ')
    candles,checksum=load_csv(src)
    nseg,stats=screen(candles)
    report={
        'tool':'faraz_local_offline_research_v1',
        'data_sha256':checksum,'candles_observed':len(candles),
        'timeframe_seconds':M15_SECONDS,'segments':nseg,
        'data_policy':'Existing prices-only M15 CSV; original timestamps unconverted; no interpolation',
        'limits':['IN_SAMPLE: repeatedly studied period, no untouched holdout','OHLC BID assumption, not verified execution quotes','Fixed scenario cost, not historical broker spread/swap','Unresolved gaps and after-gap resets mean no annual PnL','Fixed 0.01 lot, flat-start each segment, not live sizing','No intrabar mark-to-market DD','Quarter labels derived from raw timestamps; UTC/DST not verified'],
        'cost_model':{'spread_price':SPREAD_PRICE,'slippage_each_side_price':SLIPPAGE_PRICE_EACH_SIDE,'commission_per_lot_roundtrip_usd':COMMISSION_USD_PER_LOT_ROUNDTRIP},
        'research_params':{'lot':LOT,'risk_budget_usd':RISK_BUDGET_USD,'stop_atr_multiple':STOP_ATR_MULTIPLE,'horizon_bars':HORIZON_BARS,'tp':'NONE_TIME_EXIT'},
        'methods':stats,
        'overall_conclusion':'NO_STRATEGY_APPROVED; verification requires a separate prelocked independent-period test'
    }
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(f'PASS: {len(candles)} historical rows checked; {nseg} independent segments; 3 research methods analyzed.')
    print(f'Aggregate-only report: {dst.name} (local; no upload performed)')
    for m in stats:
        print(f"{m['family']}: closed={m['closed']} unknown={m['unresolved']} partial_net={m['known_partial_net_usd']} PF={m['known_partial_profit_factor']}")
    return 0

if __name__=='__main__':
    raise SystemExit(main())
