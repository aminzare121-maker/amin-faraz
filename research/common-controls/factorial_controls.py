"""Orthogonal research controls, using the existing PR32 simulator only."""
from decimal import Decimal as D
from historical_management import Management

class FixedVolumeTrailing(Management):
    """Old fixed-volume control has NO entry risk veto; not a production mode.
    Reuses original trailing and capital accounting, without changing entries.
    """
    def prepare(self,setup,entry,bar,history,spread):
        if self.blocked:raise ValueError('UNRESOLVED_CAPITAL_PATH')
        self.peak=entry
        vol=D('.01');stop=D(setup['stop_loss'])
        risk=(abs(entry-stop)+D(self.policy.max_slippage))*vol*D(self.spec.contract_size)+D(self.policy.commission_per_lot)*vol
        return dict(volume=str(vol),stop_loss=str(stop),initial_risk_usd=str(risk),equity_before=str(self.equity))

def control(mode):
    if mode=='FF':return None
    if mode=='VF':return Management(adaptive_exit=False)
    if mode=='FA':return FixedVolumeTrailing()
    if mode=='VA':return Management()
    raise ValueError('FACTOR_MODE')

def matched(left,right):
    """Only identical observed entry opportunity, not ordinal trade number."""
    def index(rows):
        out={}
        for row in rows:
            key=(row['signal_time'],row['entry_time'],row['side'])
            if key in out:raise ValueError('DUPLICATE_ENTRY')
            out[key]=row
        return out
    a,b=index(left['rows']),index(right['rows']);common=a.keys()&b.keys()
    pairs=[]
    for key in sorted(common):
        x,y=a[key],b[key];nx,ny=x['net_scenario_usd'],y['net_scenario_usd']
        pairs.append(dict(entry_key_sha256=__import__('registry').digest(key),
            left_lots=x['lots'],right_lots=y['lots'],left_net=nx,right_net=ny,
            net_difference=None if nx is None or ny is None else str(D(ny)-D(nx)),
            same_exit=x['exit_time']==y['exit_time'] and x['reason']==y['reason'],
            comparability='UNRESOLVED' if nx is None or ny is None else 'MATCHED_ENTRY_NOT_CAUSAL_PROOF'))
    return dict(matched=len(common),only_left=len(a.keys()-b.keys()),only_right=len(b.keys()-a.keys()),pairs=pairs)

def validate_windows(windows):
    previous=None
    for w in sorted(windows,key=lambda x:x['start']):
        if w['start']>=w['end'] or (previous is not None and w['start']<previous):raise ValueError('OVERLAPPING_WINDOWS')
        previous=w['end']
    return True
