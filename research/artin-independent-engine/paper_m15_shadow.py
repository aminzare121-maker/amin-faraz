"""Offline M15 paper replay from Artin's existing *eligible* trace.

NOT a source of teacher rules, not an MT5 bridge, and not an order executor.
Model assumption: next consecutive bar open is the paper entry fill. When both
stop and target occur within the same OHLC candle, stop wins (conservative,
not a claim of actual intrabar ordering). Exact fills and spreads remain unknown.
"""
import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

INTERVAL = 900


def dec(v, positive=False):
    if isinstance(v, bool) or not isinstance(v, (str, int, Decimal)):
        raise ValueError('decimal string/int required')
    d = Decimal(v)
    if not d.is_finite() or d < 0 or (positive and d == 0):
        raise ValueError('nonnegative finite decimal required')
    return d


def read_bars(path):
    data = Path(path).read_bytes()
    rows = list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
    bars = []
    for r in rows:
        t = int(r['time_raw_epoch'])
        o, h, l, c = (dec(r[k]) for k in ('open','high','low','close'))
        if not l <= min(o,c) <= max(o,c) <= h:
            raise ValueError('invalid OHLC')
        if bars and t <= bars[-1]['t']:
            raise ValueError('timestamps must be strictly increasing')
        bars.append(dict(t=t, o=o, h=h, l=l, c=c))
    if not bars:
        raise ValueError('empty CSV')
    return bars, hashlib.sha256(data).hexdigest()


def read_eligible(path, bars):
    out, counters = [], Counter()
    n = -1
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for n, line in enumerate(f):
            event = json.loads(line)
            if n >= len(bars) or event.get('bar_opened_at') != bars[n]['t'] or event.get('at') != bars[n]['t'] + INTERVAL:
                raise ValueError('raw decision trace and CSV bar times disagree')
            at = event['at']
            for d in event['decisions']:
                counters[d['status']] += 1
                if d['status'] == 'ELIGIBLE':
                    out.append((at, d['side'], d['rule_id']))
    if n + 1 != len(bars):
        raise ValueError('raw decision trace does not cover all CSV bars')
    if len(out) != len(set(out)):
        raise ValueError('duplicate eligible decision keys')
    return out, dict(counters)


def load_specs(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    specs = {}
    for s in raw['specs']:
        key = (int(s['signal_at']), s['side'], s['rule_id'])
        if key in specs:
            raise ValueError('duplicate trade specification')
        if s['side'] not in ('BUY','SELL') or not s['rule_id']:
            raise ValueError('invalid decision key')
        if not s.get('source') or not s.get('stop_source') or not s.get('target_source'):
            raise ValueError('teacher/source trace required for every specification')
        if type(s.get('known_at')) is not int or s['known_at'] > key[0] or s['known_at'] < 0:
            raise ValueError('stop/target must be sourced and known at decision time')
        specs[key] = s
    return specs


def evaluate_trade(bars, idx, key, spec, multiplier, lot, fee):
    at, side, rule = key
    if idx == len(bars) or bars[idx]['t'] != at:
        return dict(signal_at=at, side=side, rule_id=rule,
                    state='BLOCKED', reason='MISSING_IMMEDIATE_NEXT_M15_BAR')
    entry = bars[idx]['o']
    stop, target = dec(spec['stop'], True), dec(spec['target'], True)
    if not ((stop < entry < target) if side == 'BUY' else (target < entry < stop)):
        return dict(signal_at=at, side=side, rule_id=rule,
                    state='BLOCKED', reason='STOP_TARGET_NOT_BRACKETING_NEXT_OPEN',
                    paper_entry=str(entry))
    base = dict(signal_at=at, side=side, rule_id=rule,
                teacher_sources=dict(entry=spec['source'],stop=spec['stop_source'],target=spec['target_source']),
                paper_entry_at=at, paper_entry=str(entry), stop=str(stop), target=str(target))
    last_t = bars[idx]['t']
    for b in bars[idx:]:
        if b['t'] != last_t:
            return dict(**base, state='UNRESOLVED', reason='GAP_DURING_OPEN_TRADE')
        last_t = b['t'] + INTERVAL
        # Open gaps: stop fills at worse actual open; target capped at selected target.
        if side == 'BUY':
            if b['o'] <= stop: price,reason,ambiguity=b['o'],'OPEN_GAP_STOP',False
            elif b['o'] >= target: price,reason,ambiguity=target,'OPEN_GAP_TARGET_CAPPED',False
            else:
                touched_stop, touched_target=b['l'] <= stop,b['h'] >= target
                if touched_stop: price,reason,ambiguity=stop,'STOP',touched_target
                elif touched_target: price,reason,ambiguity=target,'TARGET',False
                else: continue
            gross=(price-entry)*multiplier*lot
        else:
            if b['o'] >= stop: price,reason,ambiguity=b['o'],'OPEN_GAP_STOP',False
            elif b['o'] <= target: price,reason,ambiguity=target,'OPEN_GAP_TARGET_CAPPED',False
            else:
                touched_stop, touched_target=b['h'] >= stop,b['l'] <= target
                if touched_stop: price,reason,ambiguity=stop,'STOP',touched_target
                elif touched_target: price,reason,ambiguity=target,'TARGET',False
                else: continue
            gross=(entry-price)*multiplier*lot
        return dict(**base, state='CLOSED_PAPER', exit_at=b['t'], exit_price=str(price),
                    exit_reason=reason, ambiguous_same_bar=ambiguity,
                    gross_usd=str(gross), net_usd=str(gross-fee*lot))
    return dict(**base, state='OPEN_AT_MONTH_END',
                reason='NO_MARK_TO_MARKET_PNL_CLAIMED')


def replay(csv_path,trace_path,summary_path,spec_path,contract_value,lot_size,roundtrip_fee):
    multiplier,lot,fee=(dec(contract_value,True),dec(lot_size,True),dec(roundtrip_fee))
    bars,csv_digest=read_bars(csv_path)
    summary=json.loads(Path(summary_path).read_text(encoding='utf-8-sig'))
    if summary.get('csv_sha256')!=csv_digest or summary.get('interval_seconds')!=INTERVAL or summary.get('observed_bars')!=len(bars):
        raise ValueError('raw diagnostic summary does not match this M15 CSV')
    eligible,decision_counts=read_eligible(trace_path,bars)
    specs=load_specs(spec_path)
    by_start={b['t']:i for i,b in enumerate(bars)}
    outcomes=[]
    for at,side,rule in eligible:
        key=at,side,rule
        s=specs.get(key)
        if not s:
            outcomes.append(dict(signal_at=at,side=side,rule_id=rule,state='BLOCKED',
                                 reason='MISSING_TEACHER_SOURCED_STOP_TARGET'))
            continue
        outcomes.append(evaluate_trade(bars,by_start.get(at,len(bars)),key,s,multiplier,lot,fee))
    eligible_set=set(eligible)
    orphan_specs=[list(k) for k in specs if k not in eligible_set]
    closed=[o for o in outcomes if o['state']=='CLOSED_PAPER']
    net=sum((Decimal(o['net_usd']) for o in closed),Decimal(0))
    by_state=Counter(o['state'] for o in outcomes)
    blockers=Counter(o.get('reason') for o in outcomes if o['state'] in ('BLOCKED','UNRESOLVED'))
    return dict(mode='OFFLINE_ASSUMPTION_NOT_TEACHER_COMPLETE_BACKTEST',
                csv_sha256=csv_digest, M15_bars=len(bars),
                coverage_at_least_28_calendar_days=(bars[-1]['t']-bars[0]['t']+INTERVAL>=28*86400),
                first_bar_at=bars[0]['t'],last_bar_at=bars[-1]['t'],
                eligible_decisions=len(eligible), all_decision_statuses=decision_counts,
                outcomes_by_state=dict(by_state), blockers=dict(blockers),
                orphan_specs=orphan_specs,
                completed_paper_trades=len(closed),
                paper_net_usd_closed_only=str(net),
                ambiguous_stop_priority_count=sum(bool(o.get('ambiguous_same_bar')) for o in closed),
                assumptions=['next_consecutive_M15_open_paper_fill',
                             'OHLC_same_bar_stop_before_target_if_order_unknown',
                             'entry_spread_slippage_swap_not_modeled',
                             'teacher_sourced_stop_target_required',
                             'unrealized_positions_excluded_from_closed_PnL',
                             'overlapping_signals_are_independent_not_portfolio_risk',
                             'not_teacher_approved_execution_model'],
                strategy_pnl_verified=False, orders_sent=0, trades=outcomes)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv',required=True)
    p.add_argument('--trace',required=True)
    p.add_argument('--summary',required=True)
    p.add_argument('--specs',required=True)
    p.add_argument('--contract-value-per-lot',required=True)
    p.add_argument('--lot',required=True)
    p.add_argument('--roundtrip-fee-per-lot',required=True)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args()
    data=replay(a.csv,a.trace,a.summary,a.specs,a.contract_value_per_lot,a.lot,a.roundtrip_fee_per_lot)
    if a.out.resolve() in [Path(x).resolve() for x in (a.csv,a.trace,a.summary,a.specs)]:
        raise ValueError('output may not overwrite inputs')
    a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:data[k] for k in ('M15_bars','eligible_decisions','completed_paper_trades','paper_net_usd_closed_only','blockers')},ensure_ascii=False))


if __name__=='__main__':main()
