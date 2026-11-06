"""Offline diagnostic entry point for existing private Eplanet M15 data.

This is not the main Faraz selector and never certifies market performance.
Run from research/common-controls on Codex Windows with the existing
offline_evidence.py and private feed manifest available; no network or MT5.
"""
import argparse, json
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from historical_engine import canonical_bars,simulate,sma_cross_signal


def epoch_utc(value):
    if not value.endswith('Z'):
        raise ValueError('USE_EXPLICIT_UTC_Z_TIME')
    return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())


def one_signal(side):
    def signal(history):
        return side if len(history)==21 else None
    return signal


def report_for_bars(records, *, offset_seconds, start_utc, end_utc,
                    spread, slippage, commission, rollover_exposure='UNKNOWN'):
    if not start_utc < end_utc or start_utc%900 or end_utc%900:
        raise ValueError('BAD_WINDOW')
    if not records:
        return {'status':'NO_DATA','market_profitability_verified':False}
    canonical=canonical_bars(records,offset_seconds=offset_seconds,offset_evidence='CONDITIONAL')
    selected=[x for x in canonical if start_utc<=x['time']<end_utc]
    if not selected:
        return {'status':'NO_DATA','market_profitability_verified':False}
    methods={'SMA_5_20_FROZEN':sma_cross_signal,
             'BUY_AFTER_21_CLOSED_BASELINE':one_signal('buy'),
             'SELL_AFTER_21_CLOSED_BASELINE':one_signal('sell')}
    output={}
    for name,signal in methods.items():
        result={}
        for policy in ('stop_first','target_first','unknown'):
            r=simulate(selected,signal,spread=spread,slippage=slippage,
                  commission_roundtrip_per_lot=commission,
                  rollover_exposure=rollover_exposure,
                  cost_basis='ASSUMPTION',time_basis='CONDITIONAL',policy=policy)
            result[policy]={k:r[k] for k in ('positions','resolved','unresolved',
                   'scenario_net_usd','scenario_max_drawdown_usd','known_partial_net_usd')}
        output[name]=result
    from historical_engine import sha_bars,segments
    continuous=list(segments(selected))
    return {'schema':1,'status':'EXPLORATORY_ONLY','window_start_utc':start_utc,
       'window_end_utc':end_utc,'m15_rows':len(selected),
       'segments':len(continuous),'largest_segment':max(map(len,continuous)),
       'raw_sha256':sha_bars(selected),'time_evidence':'CONDITIONAL_OFFSET_NOT_ATTESTED',
       'cost_basis':'ASSUMED_NO_HISTORICAL_RECEIPT',
       'ask_intrabar':'APPROXIMATED_FROM_BID_SPREAD',
       'rollover_exposure':rollover_exposure,'market_profitability_verified':False,
       'holdout_certified':False,'trading_permitted':False,
       'strategies_are_existing_faraz_six':False,
       'scope_note':'Frozen baselines plus illustrative SMA only. Historical price observations, hypothetical cost/execution. Not an edge estimate.',
       'scenarios':output}


def main():
    p=argparse.ArgumentParser(description='Private Eplanet M15 offline diagnostic. No trading, no downloads.')
    p.add_argument('--start',required=True,help='UTC ISO with Z, e.g. 2026-11-04T00:00:00Z')
    p.add_argument('--end',required=True,help='UTC ISO with Z')
    p.add_argument('--offset-seconds',type=int,required=True,help='Explicit conditional broker-server-to-UTC offset')
    p.add_argument('--assumed-spread',required=True,help='Price units per oz, assumption')
    p.add_argument('--assumed-slippage',required=True,help='Price units per oz per side, assumption')
    p.add_argument('--assumed-roundtrip-commission',required=True,help='USD per lot, assumption')
    p.add_argument('--output',type=Path,required=True,help='LOCAL file path, NOT repository')
    args=p.parse_args()
    # The existing verified-hash private loader is reused; no additional feed reader.
    from offline_evidence import load_existing
    bars,_=load_existing(include_repairs=True)
    r=report_for_bars(bars,offset_seconds=args.offset_seconds,start_utc=epoch_utc(args.start),
       end_utc=epoch_utc(args.end),spread=args.assumed_spread,
       slippage=args.assumed_slippage,commission=args.assumed_roundtrip_commission)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':r['status'],'m15':r.get('m15_rows'),
         'result_file_local':str(args.output),'market_profitability_verified':False}))


if __name__=='__main__':main()
