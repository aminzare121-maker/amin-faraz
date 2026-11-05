"""Glue for ORIGINAL amin_mt5 candidates; isolated historical *diagnostic* only.

No engine code is replaced, no order API exists, no financial approval.
"""
import json
from decimal import Decimal
from pathlib import Path
from historical_diagnostic import bars_from_rows,segments,num


def bridge_existing(rows, contexts, *, candidates=None, evaluator=None):
    """Injectable evaluator for tests; on Windows use original candidate modules.

    Caller is responsible for historical evidence validation. This never certifies it.
    """
    if not contexts or set(contexts)!={'base','stress'}:raise ValueError('TWO_FIXED_COST_CONTEXTS_REQUIRED')
    for c in contexts.values():
        if c.get('cost_basis')!='ASSUMPTION' or c.get('assumed_spread') is None or c.get('slippage') is None or c.get('commission') is None:
            raise ValueError('COST_CONTEXT_UNKNOWN')
        for k in ('assumed_spread','slippage','commission'):
            if num(c[k])<0:raise ValueError('NEGATIVE_COST')
        if c.get('swap') is None and c.get('assumed_swap') is None and c.get('swap_schedule') is None:
            raise ValueError('SWAP_MUST_BE_EXPLICIT_OR_UNKNOWN_BLOCKED')
    if candidates is None or evaluator is None:
        import sys
        common=Path(__file__).resolve().parents[1]/'common-controls'
        if str(common) not in sys.path:sys.path.insert(0,str(common))
        from engine_bridge import existing_engine
        existing_engine()  # import only, no trade connection
        from amin_mt5.strategy import candidates as original_candidates
        from scenario_segment import evaluate_segment
        candidates = original_candidates() if candidates is None else candidates
        evaluator = evaluate_segment if evaluator is None else evaluator
    parts=segments(bars_from_rows(rows));out=[]
    for candidate in candidates:
        ident=getattr(candidate,'id',type(candidate).__name__)
        lookback=int(getattr(candidate,'lookback',0))
        if lookback<0:raise ValueError('LOOKBACK')
        for label,context in contexts.items():
            for intrabar in ('unknown','stop_first','target_first'):
                values=[];skipped=0;errors=[]
                for idx,part in enumerate(parts):
                    if len(part)<lookback+6:
                        skipped+=1;continue
                    # Keep broker-relative time. Stage dates are CONDITIONAL; never validated as UTC.
                    prepared=[dict(time=b['time'],open=str(b['open']),high=str(b['high']),low=str(b['low']),close=str(b['close']),
                        available=b['time']+900,observed_at=b['time']+900,final=True,time_basis='raw-broker-server-unverified') for b in part]
                    try:
                        values.extend(evaluator(prepared,0,len(prepared),context,candidate,None,intrabar))
                    except Exception as e:
                        errors.append({'segment_index':idx,'error_type':type(e).__name__})
                resolved=[num(x['net']) for x in values if x.get('net') is not None]
                complete=bool(values) and not errors and len(resolved)==len(values)
                equity=peak=dd=Decimal(0)
                for n in resolved:
                    equity+=n;peak=max(peak,equity);dd=max(dd,peak-equity)
                out.append(dict(candidate=ident,cost_context=label,intrabar_policy=intrabar,
                    signal_rows=len(values),segments_skipped_for_warmup=skipped,failed_segments=errors,
                    scenario_net_usd=str(equity) if complete else None,
                    scenario_drawdown_usd=str(dd) if complete else None,
                    status='EXPLORATORY_ONLY',real_market_profitability_verified=False,
                    path_uncertainty='BROKER_TIME_AND_BID_ASK_NOT_VERIFIED'))
    return dict(schema=1,kind='ORIGINAL_FARAZ_CANDIDATE_RESEARCH_BRIDGE',
        source_segments=len(parts),max_segment_bars=max(map(len,parts),default=0),results=out,
        data_time_basis='RAW_BROKER_SERVER_LABEL_NOT_ATTESTED',
        historical_backtest_certified=False,market_profitability_verified=False,trade_allowed=False,
        holdout_freshness='UNVERIFIED',costs_hypothetical=True)
