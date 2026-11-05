"""Explicit dated rollover events; never extrapolate a current broker swap rate."""
from decimal import Decimal
from execution_scenarios import number

def carry(start,end,lots,side,schedule):
    if type(start) is not int or type(end) is not int or end<start or side not in ('buy','sell'):raise ValueError('CARRY_RANGE')
    lot=number(lots)
    if lot<=0 or lot%Decimal('.01'):raise ValueError('VOLUME_GRID')
    unknown=dict(cashflow=None,status='UNKNOWN',events=[],reason='NO_FULL_DATED_COVERAGE')
    if not schedule or schedule.get('coverage_start',end+1)>start or schedule.get('coverage_end',start-1)<end:return unknown
    if schedule.get('basis') not in ('ASSUMPTION','VERIFIED'):raise ValueError('CARRY_BASIS')
    if schedule['basis']=='VERIFIED':
        receipt=schedule.get('evidence',{});sha=receipt.get('sha256','')
        if receipt.get('reviewed') is not True or receipt.get('historical') is not True or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):return unknown
    if schedule.get('complete_event_calendar') is not True:return unknown
    result=Decimal(0);trace=[];previous=None
    for event in schedule.get('events',[]):
        t=event['time']
        if type(t) is not int or previous is not None and t<=previous:raise ValueError('CARRY_EVENT_ORDER')
        previous=t
        if not start<t<=end:continue
        rate=number(event['long_per_lot' if side=='buy' else 'short_per_lot']);multiple=number(event['multiplier'])
        if multiple<=0:raise ValueError('CARRY_MULTIPLIER')
        value=rate*multiple*lot;result+=value
        trace.append(dict(time=t,rate_per_lot=str(rate),multiplier=str(multiple),cashflow=str(value)))
    return dict(cashflow=str(result),status=schedule['basis'],events=trace,reason=None)
