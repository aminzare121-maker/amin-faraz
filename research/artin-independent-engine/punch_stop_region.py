"""S22 first-third region hypothesis for a SOURCE-SELECTED punch movement.

The teacher's illustrated stop is inside a region, not exactly one third from
entry. This module never chooses the movement's start, body/wick basis, a stop
point within the region or a structural priority. Endpoints and interpretation
are explicit source inputs; no reverse fitting from the illustrated stop.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

@dataclass(frozen=True)
class SelectedPunch:
    side:str
    start:Decimal
    completion:Decimal
    known_at:int
    endpoint_basis:str
    source:str
    def __post_init__(self):
        if self.side not in ('BUY','SELL'):raise ValueError('side required')
        if any(not isinstance(v,Decimal) or not v.is_finite() or v<=0 for v in (self.start,self.completion)):
            raise ValueError('positive exact endpoints required')
        if not (self.start<self.completion if self.side=='BUY' else self.start>self.completion):
            raise ValueError('selected movement must follow trade direction')
        if type(self.known_at) is not int or self.known_at<0:raise ValueError('availability required')
        if not isinstance(self.endpoint_basis,str) or not self.endpoint_basis.strip():raise ValueError('explicit source endpoint basis required')
        if not isinstance(self.source,str) or not self.source.strip():raise ValueError('source required')
    def region(self,at):
        if type(at) is not int or at<self.known_at:raise ValueError('selected movement not yet available')
        start,end=Fraction(self.start),Fraction(self.completion)
        boundary=start+(end-start)/3
        return min(start,boundary),max(start,boundary)
    def assess(self,stop,at):
        if not isinstance(stop,Decimal) or not stop.is_finite() or stop<=0:raise ValueError('positive exact stop required')
        low,high=self.region(at)
        return {'inside_first_third_from_selected_start':low<=Fraction(stop)<=high,
            'first_third_low_exact':str(low),'first_third_high_exact':str(high),
            'endpoint_basis':self.endpoint_basis,'source':self.source,'known_at':self.known_at,
            'source_selected_endpoints':True,'unique_teacher_endpoint_formula_verified':False,
            'exact_stop_generated':False,'candidate_only':True,'actionable':False}
