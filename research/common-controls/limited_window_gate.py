"""Local window gates, independent of PnL and annual certification.
Eligibility is not profitability, an order permission, or fresh-holdout evidence.
"""
from registry import digest

REQUIRED=('rights','clock','session','ohlc','price_side','contract','costs','execution')

def evaluate(window,*,mode='DIAGNOSTIC'):
    if mode not in ('DIAGNOSTIC','SEALED_HOLDOUT'):raise ValueError('MODE')
    start,end=window['start'],window['end']
    if type(start) is not int or type(end) is not int or start>=end:raise ValueError('WINDOW')
    blockers=[]
    for name in REQUIRED:
        e=window.get('evidence',{}).get(name,{})
        if e.get('status') not in ('VERIFIED','VERIFIED_BOUNDED'):
            blockers.append(name.upper()+'_NOT_VERIFIED');continue
        # Labels cannot substitute for a versioned, window-covering evidence receipt.
        sha=e.get('receipt_sha256','')
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            blockers.append(name.upper()+'_RECEIPT_MISSING');continue
        if e.get('start',end)>start or e.get('end',start)<end:
            blockers.append(name.upper()+'_OUTSIDE_EVIDENCE_INTERVAL')
    if window.get('missing_slots',0):blockers.append('UNEXPLAINED_MISSING_SLOTS')
    if mode=='SEALED_HOLDOUT' and (window.get('exposure')!='VERIFIED_UNSEEN' or window.get('rollback')!='VERIFIED'):
        blockers.append('FRESH_HOLDOUT_UNVERIFIED')
    eligible=not blockers
    engine_ready=window.get('engine_ready') is True
    return dict(schema=1,window_id=window['id'],window_hash=digest(window),mode=mode,
                status='LOCAL_WINDOW_ELIGIBLE' if eligible else 'EXPLORATORY_ONLY',
                blockers=blockers,engine_ready=engine_ready,
                backtest_allowed=eligible and engine_ready,
                result='READY_FOR_FIXED_DIAGNOSTIC' if eligible and engine_ready else 'NO_RESULT',
                fresh_holdout=eligible and mode=='SEALED_HOLDOUT',
                annual_certified=False,profitability_verified=False,trade_allowed=False)
