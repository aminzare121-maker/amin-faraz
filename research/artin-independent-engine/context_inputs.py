"""Causal, time-bounded evidence inputs, independent of any previous engine.

Historical economics and teacher context are separate from candle geometry.
No numerical news score or candle colour is promoted to sentiment permission.
"""
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from entry_engine import Fact

def integer_time(t):
    if type(t) is not int or t<0:raise ValueError('nonnegative integer time required')

@dataclass(frozen=True)
class Context:
    valid_from: int
    valid_until: int
    known_at: int
    facts: object
    source: str
    def __post_init__(self):
        for t in (self.valid_from,self.valid_until,self.known_at):integer_time(t)
        if self.valid_until<=self.valid_from:raise ValueError('nonempty half-open validity required')
        if not isinstance(self.source,str) or not self.source.strip():raise ValueError('context source required')
        if not isinstance(self.facts,dict) or not self.facts:raise ValueError('nonempty context facts required')
        for k,v in self.facts.items():
            if not isinstance(k,str) or not k:raise ValueError('fact name required')
            Fact(v,self.known_at,self.source)
        object.__setattr__(self,'facts',MappingProxyType(dict(self.facts)))

def facts_as_of(contexts,at):
    integer_time(at);result={}
    for c in contexts:
        if not isinstance(c,Context):raise ValueError('Context required')
        if c.known_at>at or not c.valid_from<=at<c.valid_until:continue
        for k,v in c.facts.items():
            f=Fact(v,c.known_at,c.source)
            # No implicit last-event-wins handling of contradictory context.
            if k in result and result[k].value!=v:raise ValueError('conflicting active context: '+k)
            if k not in result or result[k].known_at<f.known_at:result[k]=f
    return result

@dataclass(frozen=True)
class EconomicValue:
    value: Decimal
    known_at: int
    source: str
    vintage_verified: bool
    def __post_init__(self):
        if not isinstance(self.value,Decimal) or not self.value.is_finite():raise ValueError('finite Decimal required')
        integer_time(self.known_at)
        if not isinstance(self.source,str) or not self.source.strip():raise ValueError('source required')
        if type(self.vintage_verified) is not bool:raise ValueError('explicit vintage verification required')

@dataclass(frozen=True)
class EconomicRelease:
    event_id: str
    released_at: int
    previous: object=None
    forecast: object=None
    actual: object=None
    def __post_init__(self):
        if not isinstance(self.event_id,str) or not self.event_id.strip():raise ValueError('event id required')
        integer_time(self.released_at)
        for v in (self.previous,self.forecast,self.actual):
            if v is not None and not isinstance(v,EconomicValue):raise ValueError('EconomicValue required')
        if self.actual is not None and self.actual.known_at<self.released_at:
            raise ValueError('actual cannot be available before release')

    def comparison(self,at):
        integer_time(at)
        # Session6/7/8: forecast-previous before release; actual-forecast after.
        before=at<self.released_at
        a,b=(self.forecast,self.previous) if before else (self.actual,self.forecast)
        mode='FORECAST_MINUS_PREVIOUS' if before else 'ACTUAL_MINUS_FORECAST'
        values=(a,b)
        if any(v is None for v in values):return {'status':'MISSING_VALUE','mode':mode,'delta':None}
        if any(v.known_at>at for v in values):return {'status':'NOT_YET_AVAILABLE','mode':mode,'delta':None}
        if any(not v.vintage_verified for v in values):return {'status':'UNVERIFIED_VINTAGE','mode':mode,'delta':None}
        return {'status':'COMPARABLE','mode':mode,'delta':a.value-b.value,
                'known_at':max(v.known_at for v in values),'sources':tuple(v.source for v in values),
                'sentiment_permission':None,'automatic_asset_direction_assumed':False}
