"""Independent raw-label sessions; original risk math on a declared scenario day.
This is NOT a historical broker/Tehran/UTC mapping or continuous account replay.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from historical_management import Management
from historical_candidates import plan, candidates

ANCHOR=int(datetime(2000,1,1,tzinfo=ZoneInfo('Asia/Tehran')).timestamp())

class SessionManagement(Management):
    def __init__(self,raw_start):
        super().__init__();self.raw_start=raw_start
    def scenario_time(self,t):
        delta=t-self.raw_start
        if not 0<=delta<86400:raise ValueError('SCENARIO_DAY_OVERFLOW')
        return ANCHOR+delta
    def mapped(self,b):return dict(b,time=self.scenario_time(b['time']))
    def prepare(self,setup,entry,bar,history,spread):
        return super().prepare(setup,entry,self.mapped(bar),[self.mapped(b) for b in history],spread)
    def on_close(self,entry,initial,side,quote,old,closed,vol,fee,slip):
        return super().on_close(entry,initial,side,quote,old,[self.mapped(b) for b in closed],vol,fee,slip)
    def settle(self,net,time):return super().settle(net,self.scenario_time(time))

def raw_signal(candidate):
    def signal(history):
        asof=history[-1]['time']+900
        closed=[dict(b,final=True,observed_at=b['time']+900,time_basis='RAW_LABEL_UNVERIFIED') for b in history]
        return plan(closed,asof,candidate)
    return signal

def assess_gap(g):
    # Compatibility is separate from trading/execution evidence.
    single=g['absent_m15_slots']==1
    pattern=g['pattern']
    return dict(g,cause_assessment='UNKNOWN' if single else 'COMPATIBLE_UNVERIFIED',
        compatibility_scope='CURRENT_WEEKLY_PATTERN' if pattern!='OTHER' else 'HOLIDAY_DATE_NEIGHBORHOOD_ONLY',
        classification='UNKNOWN',historical_closed_verified=False,
        executable_across_gap=False,financial_approval=False)
