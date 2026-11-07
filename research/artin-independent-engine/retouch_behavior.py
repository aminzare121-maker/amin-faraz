"""Source-specific 50% reference and observed-price wait, never assumed fills.

S21 explicitly uses half BODY. S19's selected drawing range is a measurement
hypothesis: the image does not exclude a body midpoint and does not prove a
unique teacher formula. Selecting that hypothesis is never teacher validation.
Abnormal-candle assessment remains a separate source-context input. No new
candle close is demanded for an observed retouch event.
"""
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class HalfReference:
    identity: str
    side: str
    kind: str
    low: Decimal
    high: Decimal
    known_at: int
    source: str
    def __post_init__(self):
        if self.side not in ('BUY','SELL'):raise ValueError('explicit side required')
        if self.kind not in ('BODY_S21','SELECTED_RANGE_S19'):raise ValueError('source-specific reference kind required')
        if type(self.known_at) is not int or self.known_at<0:raise ValueError('reference availability required')
        if any(not isinstance(x,Decimal) or not x.is_finite() or x<=0 for x in (self.low,self.high)) or self.low>=self.high:
            raise ValueError('nonempty positive exact reference bounds required')
        if any(not isinstance(x,str) or not x.strip() for x in (self.identity,self.source)):raise ValueError('source identity required')
    @property
    def midpoint(self):
        a,b=self.low.as_tuple(),self.high.as_tuple();exponent=min(a.exponent,b.exponent)
        numerator=int(''.join(map(str,a.digits)))*10**(a.exponent-exponent)+int(''.join(map(str,b.digits)))*10**(b.exponent-exponent)
        if numerator%2:numerator*=5;exponent-=1
        else:numerator//=2
        return Decimal((0,tuple(map(int,str(numerator))),exponent))

class RetouchWait:
    def __init__(self,reference,price_basis):
        if not isinstance(reference,HalfReference):raise ValueError('HalfReference required')
        if price_basis not in ('OBSERVED_BID','OBSERVED_ASK','TEACHER_SELECTED_RANGE_COORDINATE'):
            raise ValueError('explicit observed price basis required')
        self.reference=reference;self._reference=reference;self.price_basis=price_basis
        self.last_at=None;self.last_available_at=None;self.state='WAITING';self.events=[]
    def observe(self,price,at,known_at,source,available_at):
        if self.reference!=self._reference:raise ValueError('waiting reference cannot change')
        if any(type(t) is not int or t<0 for t in (at,known_at,available_at)) or not at<=known_at<=available_at:raise ValueError('invalid observation timing')
        if self.last_at is not None and at<=self.last_at:raise ValueError('strict observed-event order required')
        if self.last_available_at is not None and available_at<self.last_available_at:raise ValueError('availability clock moved backwards')
        if not isinstance(price,Decimal) or not price.is_finite() or price<=0:raise ValueError('positive exact observed price required')
        if not isinstance(source,str) or not source.strip():raise ValueError('observed source required')
        if at<=self.reference.known_at:raise ValueError('retouch observation must follow reference completion')
        # An after-the-fact delayed observation is evidence, not permission to
        # submit an order at its past occurrence. This recognizer creates none.
        self.last_at=at;self.last_available_at=available_at
        reached=price<=self.reference.midpoint if self.reference.side=='BUY' else price>=self.reference.midpoint
        new=self.state=='WAITING' and reached
        if new:self.state='REFERENCE_THRESHOLD_REACHED'
        r={'state':self.state,'new_trigger':new,'at':at,'known_at':known_at,'observed_price':price,
            'recognized_at':available_at,'reference_midpoint':self.reference.midpoint,'reference_kind':self.reference.kind,
            'exact_touch_observed':price==self.reference.midpoint,'price_basis':self.price_basis,
            'source':source,'reference_source':self.reference.source,'fill_assumed':False,
            'candidate_only':True,'actionable':False,'new_candle_close_required':False}
        if self.reference.kind=='SELECTED_RANGE_S19':
            r.update(reference_interpretation='SELECTED_DRAWING_RANGE_NOT_PROVEN_UNIQUE_TEACHER_FORMULA',
                     alternative_body_not_excluded=True,source_formula_verified=False)
        else:
            r.update(reference_interpretation='EXPLICIT_BODY_REFERENCE_S21',
                     alternative_body_not_excluded=False,source_formula_verified=True)
        self.events.append(r);return r
