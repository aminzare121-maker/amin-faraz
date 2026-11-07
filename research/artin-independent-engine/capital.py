"""Independent offline capital arithmetic; no orders, feeds, existing engine or defaults.

All amounts/prices must be finite Decimal. Costs are declared account-currency fee
per lot for the FULL round trip, plus adverse price allowance for sizing only.
Actual accounting uses actual fills and actual full-round-trip fee once. Stop moves
retain volume and realize nothing. Nominal riskfree cannot guarantee fills in gaps.
BoxPlan freezes chosen rules, not an absolute target price for all trades. Its target
definition is an inert description/policy ID, never evaluated. Each trade must supply
its own numeric target elsewhere. The incomplete win/loss tree is not inferred.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json

SIZING_SOURCE = ('risk_distance_contract_position_size', 'risk_budget_minimum_lot_feasibility')
MANAGEMENT_SOURCE = ('management_labels_are_sl_movements', 'protected_float_not_realized_pnl')

def _d(value, name, positive=False):
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(name + ' must be finite Decimal')
    if value < 0 or (positive and value == 0):
        raise ValueError(name + ' out of range')
    return value

def _side(side):
    if side not in ('BUY', 'SELL'):
        raise ValueError('side must be BUY or SELL')
    return Decimal(1) if side == 'BUY' else Decimal(-1)

@dataclass(frozen=True)
class Instrument:
    money_per_price_unit_per_lot: Decimal
    min_lot: Decimal
    lot_step: Decimal

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            _d(getattr(self, name), name, True)
        if self.min_lot % self.lot_step:
            raise ValueError('min_lot must align to lot_step; contract grid must be explicit')

@dataclass(frozen=True)
class Costs:
    round_trip_fee_per_lot: Decimal
    adverse_price_allowance: Decimal

    def __post_init__(self):
        _d(self.round_trip_fee_per_lot, 'round_trip_fee_per_lot')
        _d(self.adverse_price_allowance, 'adverse_price_allowance')

def size_position(side, entry, stop, risk_budget, instrument, costs):
    sign = _side(side)
    for name, value in [('entry',entry),('stop',stop),('risk_budget',risk_budget)]:
        _d(value, name, True)
    distance = sign * (entry-stop)
    if distance <= 0:
        return dict(status='REJECT', reason='INVALID_INITIAL_STOP_SIDE', provenance=SIZING_SOURCE)
    per_lot = ((distance + costs.adverse_price_allowance)
               * instrument.money_per_price_unit_per_lot + costs.round_trip_fee_per_lot)
    lots = ((risk_budget/per_lot)/instrument.lot_step).to_integral_value(rounding=ROUND_FLOOR)*instrument.lot_step
    if lots < instrument.min_lot:
        return dict(status='REJECT', reason='MIN_LOT_EXCEEDS_RISK_BUDGET', provenance=SIZING_SOURCE)
    return dict(status='ACCEPT', lots=lots, modeled_loss=lots*per_lot,
                risk_budget=risk_budget, unchanged_stop=stop,
                guarantee=False, provenance=SIZING_SOURCE)

def account_fill(side, entry_fill, exit_fill, lots, instrument, actual_round_trip_fee):
    sign = _side(side)
    _d(lots, 'lots', True)
    for name, value in [('entry_fill',entry_fill),('exit_fill',exit_fill),('actual_round_trip_fee',actual_round_trip_fee)]:
        if value is not None:
            _d(value, name, name != 'actual_round_trip_fee')
    if entry_fill is None or exit_fill is None or actual_round_trip_fee is None:
        return dict(status='UNKNOWN', net_pnl=None, reason='ACTUAL_FILL_OR_FEE_MISSING',
                    provenance=('protected_float_not_realized_pnl',))
    gross = sign*(exit_fill-entry_fill)*lots*instrument.money_per_price_unit_per_lot
    return dict(status='CLOSED', gross_pnl=gross, fee=actual_round_trip_fee,
                net_pnl=gross-actual_round_trip_fee, provenance=('protected_float_not_realized_pnl',))

def move_stop(label, side, entry, initial_stop, current_stop, new_stop, lots, instrument, costs):
    sign = _side(side)
    for name,value in [('entry',entry),('initial_stop',initial_stop),('current_stop',current_stop),('new_stop',new_stop),('lots',lots)]:
        _d(value,name,True)
    if label not in ('reduce', 'riskfree', 'saveprofit'):
        raise ValueError('unknown management choice')
    if sign*(entry-initial_stop) <= 0 or sign*(current_stop-initial_stop) < 0:
        return dict(status='REJECT', reason='INVALID_STOP_HISTORY', provenance=MANAGEMENT_SOURCE)
    if sign*(new_stop-current_stop) <= 0:
        return dict(status='REJECT', reason='STOP_NOT_STRICTLY_RISK_REDUCING', provenance=MANAGEMENT_SOURCE)
    # Model reserves declared adverse allowance and fee once; no actual fill assumed.
    modeled_net = (sign*(new_stop-entry)-costs.adverse_price_allowance)*lots*instrument.money_per_price_unit_per_lot - lots*costs.round_trip_fee_per_lot
    valid = (label=='reduce' and modeled_net<0
             or label=='riskfree' and modeled_net==0
             or label=='saveprofit' and modeled_net>0)
    if not valid:
        return dict(status='REJECT', reason='LABEL_DOES_NOT_MATCH_STOP', provenance=MANAGEMENT_SOURCE)
    return dict(status='ACCEPT', stop=new_stop, lots=lots, modeled_exit_net=modeled_net,
                realized_pnl=None, execution_guaranteed=False,
                note='Nominal model only; gap/slippage/unknown costs may defeat protection.',
                provenance=MANAGEMENT_SOURCE)

@dataclass(frozen=True)
class BoxPlan:
    box_id: str
    risk_budget: Decimal
    target_definition: str
    management_choices: tuple
    declared_before_box: bool

    def __post_init__(self):
        if not isinstance(self.box_id,str) or not self.box_id.strip():
            raise ValueError('box_id required')
        _d(self.risk_budget,'risk_budget',True)
        if not isinstance(self.target_definition,str) or not self.target_definition.strip():
            raise ValueError('explicit nonempty target rule description/policy ID required')
        if type(self.declared_before_box) is not bool or not self.declared_before_box:
            raise ValueError('rules must be selected before box')
        if not isinstance(self.management_choices,tuple) or any(x not in ('reduce','riskfree','saveprofit','fulltarget') for x in self.management_choices):
            raise ValueError('explicit immutable management choices required')

    @property
    def fingerprint(self):
        def canonical(v):
            # as_tuple is exact and independent of Decimal context precision.
            sign,digits,exponent=v.as_tuple()
            digits=list(digits)
            if not any(digits):return '0'
            while digits[-1]==0:
                digits.pop();exponent+=1
            return ('-' if sign else '')+''.join(str(x) for x in digits)+'e'+str(exponent)
        payload=dict(box_id=self.box_id,risk_budget=canonical(self.risk_budget),
                     target_definition=self.target_definition,management_choices=self.management_choices,
                     declared_before_box=self.declared_before_box)
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def validate_unchanged(self, proposed):
        return dict(status='ACCEPT' if isinstance(proposed,BoxPlan) and proposed.fingerprint==self.fingerprint else 'REJECT',
                    reason='BOX_RULES_FIXED',fingerprint=self.fingerprint,
                    provenance=('box_fixed_rules_journal_review','predeclared_limits_and_incomplete_tree'))
