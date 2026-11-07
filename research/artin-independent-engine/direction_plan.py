"""Explicit S09 fixed-instrument permission assumption, not historical bias data.

S09:265..278,370..388,591..640. Choosing a research plan before replay is
different from pretending economic analysis was completed or the market ranged.
Absent data NEVER selects this mode automatically. No live/order capability.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from entry_engine import Fact

@dataclass(frozen=True)
class DirectionPlan:
    plan_id: str
    symbol: str
    mode: str
    declared_before_replay: bool
    def __post_init__(self):
        if any(not isinstance(x,str) or not x.strip() for x in (self.plan_id,self.symbol)):
            raise ValueError('explicit plan and exact fixed symbol required')
        if self.mode!='S09_FIXED_SYMBOL_TWO_SIDED_ASSUMPTION':raise ValueError('unsupported direction assumption mode')
        if self.declared_before_replay is not True:raise ValueError('select plan before replay')
    def serialize(self):
        return {'plan_id':self.plan_id,'symbol':self.symbol,'mode':self.mode,
            'declared_before_replay':True,'basis':'RESEARCH_PERMISSION_ASSUMPTION_NOT_OBSERVED_SENTIMENT',
            'counterfactual_research_permission':True,'symbol_binding':'DECLARED_INPUT_SYMBOL_NOT_NEW_BROKER_VERIFICATION',
            'source_refs':((9,265.24,278.12),(9,370.04,387.96),(9,591.16,640)),
            'historical_neutrality_claimed':False,'economic_review_completed_claimed':False}
    @property
    def fingerprint(self):return sha256(json.dumps(self.serialize(),sort_keys=True).encode()).hexdigest()
    def derive(self,existing,at):
        original=existing.get('sentiment_permission')
        # Preserve sourced directional decisions AND malformed inputs for review.
        if original is not None and original.value!='UNKNOWN':return {}
        source='S09_FIXED_SYMBOL_PERMISSION_PLAN:'+self.fingerprint
        values={'sentiment_permission':'TWO_SIDED',
            'direction_permission_basis':'DECLARED_ASSUMPTION_NOT_HISTORICAL_SENTIMENT',
            'historical_direction_evidence_state':'MISSING' if original is None else 'UNRESOLVED',
            'permission_assumption_reason':'DIRECTION_NOT_ESTABLISHED_FIXED_SYMBOL_NO_SWITCH',
            'fixed_symbol':self.symbol}
        return {k:Fact(v,at,source) for k,v in values.items()}
