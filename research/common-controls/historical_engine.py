"""Faraz offline historical M15 research engine (no trade / broker interfaces).

Safely evaluates predeclared signals on contiguous M15 *segments*, with causal
signals, uncertainty for ambiguous bars, decimal money, and explicit cost scope.
No historical input is relabelled as synthetic. Never certifies profitability.
"""
from __future__ import annotations
from decimal import Decimal as D
from hashlib import sha256
import json

SECONDS = 900

def num(v):
    if isinstance(v, bool) or v is None:
        raise ValueError('FINITE_NUMBER_REQUIRED')
    z = D(str(v))
    if not z.is_finite():
        raise ValueError('FINITE_NUMBER_REQUIRED')
    return z


def canonical_bars(records, *, offset_seconds=None, offset_evidence='UNKNOWN'):
    """Converts broker-server epoch labels to tentative UTC, preserving both.

    No clock assumption is made implicitly. A hypothetical offset cannot prove
    clock validity. The caller must supply independent evidence before marking
    a window verified, outside this engine.
    """
    if type(offset_seconds) is not int or offset_seconds % 900:
        raise ValueError('EXPLICIT_QUARTER_HOUR_OFFSET_REQUIRED')
    if offset_evidence not in ('VERIFIED', 'CONDITIONAL'):
        raise ValueError('EXPLICIT_CLOCK_EVIDENCE_REQUIRED')
    bars = []
    previous = None
    for rec in sorted(records, key=lambda x: int(x['time'])):
        raw_number=num(rec['time'])
        if raw_number!=raw_number.to_integral_value():raise ValueError('INTEGER_TIMESTAMP_REQUIRED')
        t = int(raw_number); u = t + offset_seconds
        if t % SECONDS or u % SECONDS or (previous is not None and t <= previous):
            raise ValueError('DUPLICATE_OR_TIME_ALIGNMENT')
        o, h, l, c = (num(rec[k]) for k in ('open','high','low','close'))
        if not (0 < l <= min(o,c) <= max(o,c) <= h):
            raise ValueError('BAD_OHLC')
        bars.append(dict(time=u, raw_time=t, open=o, high=h, low=l, close=c,
                         time_evidence=offset_evidence))
        if 'tick_volume' in rec:bars[-1]['tick_volume']=num(rec['tick_volume'])
        previous=t
    return bars


def segments(bars):
    """Never bridge an unverified gap, even across a presumed market closure."""
    current = []
    for b in bars:
        if current and b['time'] - current[-1]['time'] != SECONDS:
            yield current
            current=[]
        current.append(b)
    if current:
        yield current


def sha_bars(bars):
    body=[{k: str(v) for k,v in b.items() if k in ('time','raw_time','open','high','low','close','tick_volume','time_evidence')}
          for b in bars]
    return sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def sma_cross_signal(closed, *, fast=5, slow=20):
    """Frozen demonstration signal. Uses CLOSED candles only, no optimization."""
    if type(fast) is not int or type(slow) is not int or not 1 < fast < slow:
        raise ValueError('STRATEGY_CONFIGURATION')
    if len(closed) < slow+1:
        return None
    values=[b['close'] for b in closed]
    a=sum(values[-fast:])/D(fast); b=sum(values[-slow:])/D(slow)
    a0=sum(values[-fast-1:-1])/D(fast); b0=sum(values[-slow-1:-1])/D(slow)
    if a0 <= b0 and a > b:
        return 'buy'
    if a0 >= b0 and a < b:
        return 'sell'
    return None


def simulate(bars, signal, *, spread, slippage, commission_roundtrip_per_lot,
             lots='0.01', contract='100', stop_distance='5', target_distance='10',
             max_holding_bars=12, policy='unknown', cost_basis='ASSUMPTION',
             rollover_exposure='UNKNOWN', time_basis='CONDITIONAL',
             max_history=120, management=None):
    """One position at a time; all decisions use only previously CLOSED candles.

    PnL is scenario-specific and cannot be used as a verified trading result.
    An unknown intra-bar path, unresolved rollover or segment boundary will
    produce unresolved trades, *not* fabricate an exit or a net result.
    Cost model: bid OHLC; buy entry is Ask=Bid+spread, sell entry is Bid;
    sell exits are assumed Ask=Bid+spread (fixed within bar, not verified).
    Slippage is an adverse price adjustment on both entry and exit.
    Commission is roundtrip USD per 1 lot. All money uses Decimal.
    """
    if policy not in ('stop_first','target_first','unknown'):
        raise ValueError('POLICY')
    if cost_basis not in ('ASSUMPTION','VERIFIED_BOUNDED') or time_basis not in ('CONDITIONAL','VERIFIED'):
        raise ValueError('PROVENANCE')
    if rollover_exposure not in ('PROVEN_NONE','UNKNOWN'):
        raise ValueError('ROLLOVER_UNSUPPORTED')
    sp, sl, fee, vol, mult, stop_d, target_d=map(num,(spread,slippage,commission_roundtrip_per_lot,lots,contract,stop_distance,target_distance))
    if min(sp,sl,fee)<0 or min(vol,mult,stop_d,target_d)<=0 or vol % D('0.01'):
        raise ValueError('INVALID_COST_RISK_OR_LOT')
    if type(max_holding_bars) is not int or max_holding_bars<1 or type(max_history) is not int or max_history<2:
        raise ValueError('HORIZON')
    rows=[];segment_count=0;gap_count=0;unresolved_position=False
    prev_end=None
    for part in segments(bars):
        segment_count+=1
        if prev_end is not None:
            gap_count+=1
        prev_end=part[-1]['time']
        if unresolved_position:continue
        # Warm-up is local to each segment. No training across unknown gaps.
        i=1
        while i < len(part):
            # The callback sees only bars closed prior to the next bar's OPEN.
            history=part[max(0,i-max_history):i]
            setup=signal(tuple(history))
            side=setup.get('side') if isinstance(setup,dict) else setup
            if side not in (None,'buy','sell'):
                raise ValueError('SIGNAL')
            if side is None:
                i+=1;continue
            direction=D(1) if side=='buy' else D(-1)
            entry_open=part[i]['open']
            entry=entry_open+(sp if side=='buy' else D(0))+direction*sl
            stop=entry-direction*stop_d
            if isinstance(setup,dict):
                if setup['signal_time']+SECONDS>part[i]['time']:raise ValueError('LOOKAHEAD_SIGNAL')
                stop=num(setup['stop_loss'])
                if direction*(entry-stop)<=0:
                    i+=1;continue  # Already crossed stop at entry; no invented risk level.
            target=entry+direction*target_d
            initial_stop=stop; sizing=None; adjustments=[]
            if management is not None:
                # Only the current OPEN is available to entry sizing, not its HLC.
                available_open={key:part[i][key] for key in ('time','raw_time','open','time_evidence')}
                sizing=management.prepare(setup,entry,available_open,history,sp)
                if sizing is None:
                    i+=1;continue
                vol=num(sizing['volume']);stop=num(sizing['stop_loss'])
                if vol<=0 or stop<=0 or direction*(entry-stop)<=0:raise ValueError('MANAGEMENT_EXECUTION_CONTRACT')
                initial_stop=stop
                if management.adaptive_exit:target=None
            adaptive=management is not None and management.adaptive_exit
            horizon=len(part)-i if adaptive else max_holding_bars
            exit_price=None; exit_reason='UNRESOLVED_BOUNDARY'; last_idx=None
            for k in range(i,min(len(part),i+horizon)):
                b=part[k]
                # Long exits use Bid; short exits use ASSUMED Ask from Bid.
                o,h,l,c=(b[x]+(sp if side=='sell' else D(0)) for x in ('open','high','low','close'))
                stop_at_open=o<=stop if side=='buy' else o>=stop
                target_at_open=target is not None and (o>=target if side=='buy' else o<=target)
                # A gap at open chooses the observed opening quote, no optimistic fill.
                if stop_at_open:
                    exit_price=o-direction*sl;exit_reason='STOP_OPEN_GAP'
                elif target_at_open:
                    exit_price=target-direction*sl;exit_reason='TARGET_AT_OPEN_CAPPED'
                else:
                    hit_stop=l<=stop if side=='buy' else h>=stop
                    hit_target=target is not None and (h>=target if side=='buy' else l<=target)
                    if hit_stop and hit_target and policy=='unknown':
                        exit_reason='AMBIGUOUS_SL_TP'
                    elif hit_stop and (not hit_target or policy=='stop_first'):
                        exit_price=stop-direction*sl;exit_reason='STOP'
                    elif hit_target:
                        exit_price=target-direction*sl;exit_reason='TARGET'
                if exit_reason!='UNRESOLVED_BOUNDARY':
                    last_idx=k;break
                if management is not None:
                    # Close-only observation. The newly calculated stop is effective
                    # at the NEXT bar; never replay this bar using its future high.
                    update=management.on_close(entry,initial_stop,side,c,stop,
                        part[max(0,k-13):k+1],vol,fee,sl)
                    if update['should_modify']:
                        stop=num(update['stop_loss'])
                        adjustments.append(dict(effective_time=b['time']+SECONDS,stop=str(stop)))
            if not adaptive and last_idx is None and i+max_holding_bars<=len(part):
                last_idx=i+max_holding_bars-1
                last_bar=part[last_idx]
                exit_price=last_bar['close']+(sp if side=='sell' else D(0))-direction*sl
                exit_reason='MAX_HOLD_CLOSE_ASSUMED'
            if last_idx is None:
                last_idx=len(part)-1
            # If position touches an unknown overnight rollover, never assume 0 swap.
            exposed=(rollover_exposure=='UNKNOWN' and
                     part[i]['raw_time']//86400 != (part[last_idx]['raw_time']+SECONDS)//86400)
            resolved=(exit_price is not None and not exposed)
            gross=direction*(exit_price-entry)*mult*vol if resolved else None
            net=gross-fee*vol if resolved else None
            rows.append(dict(side=side,signal_time=part[i-1]['time']+SECONDS,
                entry_time=part[i]['time'],exit_time=part[last_idx]['time']+SECONDS,
                entry=str(entry),exit=str(exit_price) if resolved else None,
                reason='ROLLOVER_COST_UNKNOWN' if exposed else exit_reason,
                price_exit_reason=exit_reason,
                net_scenario_usd=str(net) if resolved else None,
                gross_scenario_usd=str(gross) if resolved else None,
                stop=str(stop),target=str(target) if target is not None else None,lots=str(vol),
                initial_stop=str(initial_stop),initial_risk_usd=sizing['initial_risk_usd'] if sizing else None,
                equity_before=sizing['equity_before'] if sizing else None,stop_adjustments=adjustments,
                signal_candidate=setup.get('candidate') if isinstance(setup,dict) else None))
            if management is not None:
                management.settle(net,part[last_idx]['time']+SECONDS)
            # Block new positions across uncertain unresolved exposure.
            if not resolved:
                unresolved_position=True
                break
            i=last_idx+1
    values=[num(r['net_scenario_usd']) for r in rows if r['net_scenario_usd'] is not None]
    uncertain=len(values)!=len(rows)
    pnl=sum(values,D(0)); equity=peak=drawdown=D(0)
    for v in values:
        equity+=v;peak=max(peak,equity);drawdown=max(drawdown,peak-equity)
    return dict(schema=1,mode='HISTORICAL_DIAGNOSTIC_NO_ORDERS',
        bar_count=len(bars),segments=segment_count,gaps=gap_count,
        data_sha256=sha_bars(bars),strategy='FROZEN_SIGNAL_CALLBACK',
        time_basis=time_basis,cost_basis=cost_basis,
        intrabar_policy=policy,spread_model='FIXED_ASSUMED_BID_ASK_SHIFT',
        positions=len(rows),resolved=len(values),unresolved=len(rows)-len(values),
        scenario_net_usd=None if uncertain else str(pnl),
        scenario_max_drawdown_usd=None if uncertain else str(drawdown),
        known_partial_net_usd=str(pnl),
        no_trade_baseline_usd='0',
        market_profitability_verified=False,holdout_certified=False,
        live_trade_allowed=False,rows=rows)

