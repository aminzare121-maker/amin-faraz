"""S16 ordered price-path core, not a full OHLC/pivot or order classifier.

Observed reference -> break -> post-break extreme -> return toward reference ->
strict regain of that extreme. No candle-body gate, fixed bar count, ATR or
requirement to hit the exact line. This reconstructs the taught path topology;
selecting a meaningful reference/return region, wick pivots and later S19 large-
confirmation exceptions remain separate. Every result is candidate_only.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

def time(v):
    if type(v) is not int or v<0:raise ValueError('nonnegative exact observation coordinate required')
def price(v):
    if not isinstance(v,Decimal) or not v.is_finite() or v<=0:raise ValueError('positive finite Decimal required')
def text(v):
    if not isinstance(v,str) or not v.strip():raise ValueError('source/identity required')

@dataclass(frozen=True)
class PathPoint:
    at: int
    price: Decimal
    source: str
    def __post_init__(self):time(self.at);price(self.price);text(self.source)

@dataclass(frozen=True)
class PathReference:
    identity: str
    anchor_at: int
    anchor_price: Decimal
    known_at: int
    source: str
    second_at: object=None
    second_price: object=None
    def __post_init__(self):
        text(self.identity);text(self.source);time(self.anchor_at);time(self.known_at);price(self.anchor_price)
        if self.anchor_at>self.known_at:raise ValueError('reference anchor not known yet')
        if (self.second_at is None)!=(self.second_price is None):raise ValueError('both line anchors required')
        if self.second_at is not None:
            time(self.second_at);price(self.second_price)
            if not self.anchor_at<self.second_at<=self.known_at:raise ValueError('line uses future or unordered anchor')
    def level(self,at):
        time(at)
        if at<self.known_at:raise ValueError('reference not available')
        if self.second_at is None:return Fraction(self.anchor_price)
        return Fraction(self.anchor_price)+(Fraction(self.second_price)-Fraction(self.anchor_price))*Fraction(at-self.anchor_at,self.second_at-self.anchor_at)

class PullbackTopology:
    def __init__(self,side,reference,domain,expected_interval=None):
        if side not in ('BUY','SELL') or not isinstance(reference,PathReference):raise ValueError('side/reference required')
        if domain not in ('TEACHER_SCHEMATIC_VERTEX','CLOSED_PRICE_PATH'):raise ValueError('explicit observation domain required')
        if domain=='CLOSED_PRICE_PATH' and (type(expected_interval) is not int or expected_interval<=0):
            raise ValueError('closed-price path needs declared interval')
        if expected_interval is not None and (type(expected_interval) is not int or expected_interval<=0):raise ValueError('invalid interval')
        self.side=side;self.sign=1 if side=='BUY' else -1;self.reference=reference;self._reference=reference
        self.domain=domain;self.interval=expected_interval;self.previous=None;self.stage='AWAIT_REFERENCE_SIDE'
        self.extreme=None;self.extreme_at=None;self.first_known_at=None;self.break_at=None;self.trace=[]
        self.last_seen_at=None

    def fork(self):
        other=PullbackTopology(self.side,self.reference,self.domain,self.interval)
        for key in ('previous','stage','extreme','extreme_at','first_known_at','break_at','last_seen_at'):
            setattr(other,key,getattr(self,key))
        other.trace=list(self.trace)
        return other

    def step(self,p):
        if not isinstance(p,PathPoint):raise ValueError('PathPoint required')
        if self.reference!=self._reference:raise ValueError('fixed reference changed')
        if self.last_seen_at is not None and p.at<=self.last_seen_at:raise ValueError('strict observation order required')
        self.last_seen_at=p.at
        events=[]
        def result(reason):
            r={'stage':self.stage,'reason':reason,'at':p.at,'observed_price':p.price,'side':self.side,
                'reference_id':self.reference.identity,'domain':self.domain,'events':events,
                'post_break_extreme':self.extreme,'extreme_at':self.extreme_at,'first_known_at':self.first_known_at,
                'candidate_only':True,'actionable':False,'scope':'S16_PRICE_PATH_CORE_NOT_COMPLETE_ENTRY_OR_OHLC_PIVOT',
                'later_exception_assessment_required':True,'source':p.source,
                'teacher_refs':((16,615,708.12),(16,780.16,854.76),(16,1065.72,1109.76),(19,1218,1241))}
            self.trace.append(r);return r
        if p.at<self.reference.known_at:return result('REFERENCE_NOT_KNOWN')
        level=self.reference.level(p.at);far=self.sign*(Fraction(p.price)-level)
        if self.previous is not None and self.interval is not None and p.at-self.previous.at!=self.interval:
            self.stage='REVIEW_MISSING_PATH';self.previous=p;return result('UNSEEN_PATH_CANNOT_BE_ASSUMED')
        if self.stage in ('CORE_CONFIRMED','REVIEW_MISSING_PATH','REVIEW_REFERENCE_REASSESSMENT'):
            self.previous=p;return result('NO_REUSE_OR_SILENT_REVALIDATION')
        if self.stage=='AWAIT_REFERENCE_SIDE':
            if far<=0:self.stage='ARMED'
            self.previous=p
            return result('REFERENCE_SIDE_OBSERVED' if far<=0 else 'ARRIVED_AFTER_POSSIBLE_BREAK')
        if self.stage=='ARMED':
            if far>0:
                self.stage='POST_BREAK_EXTENSION';self.break_at=p.at;self.extreme=p.price;self.extreme_at=p.at
                events.append('BREAK_OBSERVED')
            self.previous=p;return result('WAIT_FOR_POST_BREAK_RETURN')
        if far<0:
            self.stage='REVIEW_REFERENCE_REASSESSMENT';self.previous=p
            return result('RETURN_PASSED_REFERENCE_CONTEXT_NOT_ASSUMED_VALID')
        if self.stage=='POST_BREAK_EXTENSION':
            if self.sign*(p.price-self.extreme)>0:self.extreme=p.price;self.extreme_at=p.at
            if self.sign*(p.price-self.previous.price)<0:
                self.stage='RETURN_OBSERVED';self.first_known_at=p.at;events.append('POST_BREAK_EXTREME_OBSERVED_BY_RETURN')
            self.previous=p;return result('TURN_OBSERVED_NOT_FIXED_N_PIVOT' if events else 'EXTREME_STILL_DEVELOPING')
        if self.stage=='RETURN_OBSERVED' and self.sign*(p.price-self.extreme)>0:
            self.stage='CORE_CONFIRMED';events.append('STRICT_POST_RETURN_EXTREME_REGAINED')
        self.previous=p
        return result('S16_CORE_CONFIRMATION' if events else 'NO_CLOSE_BEYOND_POST_BREAK_EXTREME')
