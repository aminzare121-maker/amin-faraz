"""Offline execution model. Every request is synthetic and every trace is in memory.

This module has no broker adapter and cannot contact a terminal. A local intent ID
is an idempotency key, not a promise of exactly-once execution at any broker.
Replaying the immutable command trace models recovery; it provides no disk or
process durability. Terminal evidence below is supplied synthetic evidence, not a
verification of an external account.
"""
from dataclasses import dataclass, field, replace
from decimal import Decimal, localcontext
from enum import Enum

from .numbers import dec, natural
from .authorization import (EntryAuthorization, PolicyPin, validate_authorization,
                            validate_fresh_authorization)


ZERO = Decimal("0")


def _identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("NONEMPTY_IDENTIFIER_REQUIRED")
    return value


def _boolean(value):
    if type(value) is not bool:
        raise ValueError("BOOLEAN_REQUIRED")
    return value


def _sum(values):
    values = tuple(values)
    if not values:
        return ZERO
    # Enough significant digits for exact addition, including very small inputs.
    with localcontext() as context:
        context.prec = max(1, max(x.adjusted() for x in values)
                           - min(x.as_tuple().exponent for x in values)
                           + len(str(len(values))) + 3)
        return sum(values, ZERO)


def _mul(left, right):
    with localcontext() as context:
        context.prec = len(left.as_tuple().digits) + len(right.as_tuple().digits) + 2
        return left * right


class Phase(str, Enum):
    PROPOSED = "PROPOSED"
    RISK_APPROVED = "RISK_APPROVED"
    RESERVED = "RESERVED"
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"


@dataclass(frozen=True)
class DemoBinding:
    account_id: str
    revision: int
    mode: str = "DEMO"
    synthetic: bool = True
    connected: bool = True
    fresh: bool = True
    position_mode: str = "HEDGING"
    unmanaged_positions: bool = False
    netting_ambiguous: bool = False
    policy: PolicyPin | None = None
    budget_epoch_id: str = "unconfigured"
    epoch_risk_limit: Decimal = ZERO

    def __post_init__(self):
        _identifier(self.account_id)
        natural(self.revision)
        for value in (self.synthetic, self.connected, self.fresh,
                      self.unmanaged_positions, self.netting_ambiguous):
            _boolean(value)
        if self.mode != "DEMO" or not self.synthetic:
            raise ValueError("SYNTHETIC_DEMO_ONLY")
        if self.position_mode not in ("HEDGING", "NETTING"):
            raise ValueError("INVALID_POSITION_MODE")
        _identifier(self.budget_epoch_id)
        limit = dec(self.epoch_risk_limit)
        if limit < ZERO:
            raise ValueError("INVALID_EPOCH_RISK_LIMIT")
        object.__setattr__(self, "epoch_risk_limit", limit)
        if self.policy is not None:
            if not isinstance(self.policy, PolicyPin):
                raise ValueError("PINNED_POLICY_REQUIRED")
            rules = dict(self.policy.context_rules)
            if limit <= ZERO or limit > min(dec(rules["daily_loss_limit"]),
                                           dec(rules["total_loss_limit"]),
                                           self.policy.portfolio_risk_cap):
                raise ValueError("EPOCH_LIMIT_EXCEEDS_PINNED_CAPS")


@dataclass(frozen=True)
class Intent:
    client_intent_id: str
    account_id: str
    account_revision: int
    symbol: str
    side: str
    volume: Decimal
    risk_per_lot: Decimal
    entry_price: Decimal
    initial_sl: Decimal
    payload_hash: str = ""
    authorization: EntryAuthorization | None = None

    def __post_init__(self):
        for value in (self.client_intent_id, self.account_id, self.symbol):
            _identifier(value)
        natural(self.account_revision)
        if not isinstance(self.payload_hash, str):
            raise ValueError("PAYLOAD_HASH_STRING_REQUIRED")
        if self.side not in ("BUY", "SELL"):
            raise ValueError("INVALID_SIDE")
        for field in ("volume", "risk_per_lot", "entry_price", "initial_sl"):
            value = dec(getattr(self, field))
            if value <= ZERO:
                raise ValueError("POSITIVE_EXECUTION_INPUT_REQUIRED")
            object.__setattr__(self, field, value)
        if ((self.side == "BUY" and self.initial_sl >= self.entry_price)
                or (self.side == "SELL" and self.initial_sl <= self.entry_price)):
            raise ValueError("INITIAL_STOP_WRONG_SIDE")

    @property
    def requested_risk(self):
        return _mul(self.volume, self.risk_per_lot)


@dataclass(frozen=True)
class Protection:
    proposed_stop: Decimal | None = None
    acknowledged_stop: Decimal | None = None
    observed_stop: Decimal | None = None
    observed_history: tuple = ()
    observation_current: bool = False
    observation_revision: int | None = None
    observation_generation: int | None = None
    safety_fault: str | None = None
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)
    broker_protection_confirmed: bool = field(default=False, init=False)

    @property
    def server_protected(self):
        """A memory observation can never attest real broker protection."""
        return False

    @property
    def synthetic_protected(self):
        return (self.observation_current and self.observed_stop is not None
                and self.safety_fault is None)


@dataclass(frozen=True)
class LedgerSlice:
    open_risk: Decimal = ZERO
    reserved_risk: Decimal = ZERO
    unknown_risk: Decimal = ZERO

    @property
    def total(self):
        return _sum((self.open_risk, self.reserved_risk, self.unknown_risk))


@dataclass(frozen=True)
class ExecutionIntent:
    intent: Intent
    context_generation: int
    phase: Phase = Phase.PROPOSED
    approved_risk: Decimal | None = None
    reservation_made: bool = False
    filled_volume: Decimal = ZERO
    closed_volume: Decimal = ZERO
    close_deals: tuple = ()
    close_uncertain: bool = False
    unresolved_close_events: tuple = ()
    terminal_status: str | None = None
    order_id: str | None = None
    deal_ids: tuple = ()
    deal_evidence: tuple = ()
    position_ids: tuple = ()
    position_evidence_complete: bool = True
    last_sequence: int = 0
    protection: Protection = Protection()
    budget_epoch_id: str = "unconfigured"

    @property
    def ledger(self):
        if not self.reservation_made:
            return LedgerSlice()
        open_volume = _sum((self.filled_volume, self.closed_volume.copy_negate()))
        open_risk = _mul(open_volume, self.intent.risk_per_lot)
        remaining = _sum((self.intent.volume, self.filled_volume.copy_negate()))
        retained = ZERO if self.terminal_status else _mul(remaining, self.intent.risk_per_lot)
        if self.phase == Phase.RESERVED:
            return LedgerSlice(open_risk, retained, ZERO)
        return LedgerSlice(open_risk, ZERO, retained)


@dataclass(frozen=True)
class SyntheticRequest:
    client_intent_id: str
    account_id: str
    account_revision: int
    symbol: str
    side: str
    volume: Decimal
    stop: Decimal
    synthetic: bool = True
    payload_hash: str = ""


@dataclass(frozen=True)
class BrokerEvent:
    """Synthetic evidence, never external attestation.

    CLOSE.realized_pnl is confirmed NET after allocated entry/exit costs and
    swap. Unknown or gross-only values cannot release a held position slice.
    """
    event_id: str
    client_intent_id: str
    sequence: int
    kind: str
    account_id: str
    account_revision: int
    cumulative_filled: Decimal | None = None
    order_id: str | None = None
    deal_id: str | None = None
    position_id: str | None = None
    terminal_proof: bool = False
    authoritative: bool = False
    terminal_status: str | None = None
    close_volume: Decimal | None = None
    realized_pnl: Decimal | None = None
    budget_epoch_id: str | None = None
    net_costs_confirmed: bool = False
    cost_evidence_id: str | None = None
    evidence_source: str = "OFFLINE_SYNTHETIC"
    close_order_id: str | None = None
    net_pnl_provenance: str | None = None
    reconciles_event_id: str | None = None

    def __post_init__(self):
        for value in (self.event_id, self.client_intent_id, self.account_id):
            _identifier(value)
        natural(self.sequence)
        natural(self.account_revision)
        if self.sequence == 0:
            raise ValueError("POSITIVE_EVENT_SEQUENCE_REQUIRED")
        if self.kind not in ("ACK", "FILL", "CANCELLED", "REJECTED", "RECONCILE", "CLOSE"):
            raise ValueError("INVALID_BROKER_EVENT_KIND")
        if self.terminal_status not in (None, "OPEN", "FILLED", "CANCELLED", "REJECTED", "NOT_SENT"):
            raise ValueError("INVALID_TERMINAL_STATUS")
        _boolean(self.terminal_proof)
        _boolean(self.authoritative)
        _boolean(self.net_costs_confirmed)
        if self.evidence_source != "OFFLINE_SYNTHETIC":
            raise ValueError("SYNTHETIC_EVIDENCE_ONLY")
        for value in (self.order_id, self.deal_id, self.position_id):
            if value is not None:
                _identifier(value)
        if self.cumulative_filled is not None:
            value = dec(self.cumulative_filled)
            if value < ZERO:
                raise ValueError("NEGATIVE_FILL")
            object.__setattr__(self, "cumulative_filled", value)
        for name in ("close_volume", "realized_pnl"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, dec(getattr(self, name)))
        for value in (self.budget_epoch_id, self.cost_evidence_id, self.close_order_id,
                      self.reconciles_event_id):
            if value is not None:
                _identifier(value)


@dataclass(frozen=True)
class QuarantinedEvent:
    event: BrokerEvent
    reason: str


@dataclass(frozen=True)
class TraceEntry:
    operation: str
    arguments: tuple


@dataclass(frozen=True)
class BudgetEpoch:
    epoch_id: str
    risk_limit: Decimal
    realized_loss: Decimal = ZERO
    realized_profit: Decimal = ZERO

    @property
    def remaining_limit(self):
        return max(ZERO, _sum((self.risk_limit, self.realized_loss.copy_negate())))


@dataclass(frozen=True)
class CloseSettlement:
    deal_id: str
    close_order_id: str
    position_id: str
    volume: Decimal
    net_pnl: Decimal
    cost_evidence_id: str
    budget_epoch_id: str


@dataclass(frozen=True)
class ExecutionState:
    binding: DemoBinding
    context_generation: int = 0
    intents: tuple = ()
    seen_events: tuple = ()
    quarantined: tuple = ()
    requests: tuple = ()
    trace: tuple = ()
    budget: BudgetEpoch | None = None

    def get(self, client_intent_id):
        for record in self.intents:
            if record.intent.client_intent_id == client_intent_id:
                return record
        raise ValueError("UNKNOWN_CLIENT_INTENT_ID")

    @property
    def ledger(self):
        slices = tuple(record.ledger for record in self.intents)
        return LedgerSlice(_sum(x.open_risk for x in slices),
                           _sum(x.reserved_risk for x in slices),
                           _sum(x.unknown_risk for x in slices))


def start(binding):
    if not isinstance(binding, DemoBinding):
        raise ValueError("DEMO_BINDING_REQUIRED")
    return ExecutionState(binding, trace=(TraceEntry("start", (binding,)),),
                          budget=BudgetEpoch(binding.budget_epoch_id, binding.epoch_risk_limit))


def _commit(state, operation, arguments, **changes):
    return replace(state, trace=state.trace + (TraceEntry(operation, arguments),), **changes)


def _records(state, record):
    return tuple(record if item.intent.client_intent_id == record.intent.client_intent_id
                 else item for item in state.intents)


def _context(state, record=None):
    binding = state.binding
    if not binding.connected or not binding.fresh:
        raise ValueError("STALE_OR_DISCONNECTED_CONTEXT")
    if binding.unmanaged_positions:
        raise ValueError("UNMANAGED_EXPOSURE")
    if binding.netting_ambiguous or binding.position_mode == "NETTING":
        raise ValueError("AMBIGUOUS_OR_UNSUPPORTED_NETTING")
    if record is not None and (
            record.intent.account_id != binding.account_id
            or record.intent.account_revision != binding.revision
            or record.context_generation != state.context_generation):
        raise ValueError("ACCOUNT_REVISION_CHANGED")


def _entry_gate(state):
    if any(record.close_uncertain for record in state.intents):
        raise ValueError("UNRESOLVED_CLOSE_EVIDENCE")


def intent_from_authorization(authorization, policy):
    """Derive the complete intent from a recomputed, logically valid proposal.

    These same-process inputs provide no broker identity or cryptographic trust.
    """
    decision = validate_authorization(authorization, policy)
    context, request = authorization.context, authorization.request
    return Intent(decision.client_intent_id, context.account_key, context.account_revision,
                  request.symbol, request.side, decision.risk.volume,
                  decision.risk.risk_per_lot, dec(request.entry), dec(request.stop),
                  decision.payload_hash, authorization)


def _validate_intent(state, record):
    if state.binding.policy is None or record.intent.authorization is None:
        raise ValueError("VALIDATED_ENTRY_AUTHORIZATION_REQUIRED")
    expected = intent_from_authorization(record.intent.authorization, state.binding.policy)
    if expected != record.intent:
        raise ValueError("INTENT_AUTHORIZATION_MISMATCH")
    if record.intent.authorization.context.position_mode != state.binding.position_mode:
        raise ValueError("POSITION_MODE_BINDING_MISMATCH")
    return expected


def _fresh_check(state, record, fresh_authorization, now_ms):
    _validate_intent(state, record)
    now_ms = natural(now_ms)
    decision = validate_fresh_authorization(record.intent.authorization, fresh_authorization,
                                             state.binding.policy, now_ms)
    known = []
    unknown = []
    known_notional = []
    unknown_notional = []
    unresolved_margin = []
    directional = []
    other_count = 0
    for item in state.intents:
        if item.intent.client_intent_id == record.intent.client_intent_id:
            continue
        ledger = item.ledger
        known.append(_sum((ledger.open_risk, ledger.reserved_risk)))
        unknown.append(ledger.unknown_risk)
        if item.reservation_made and ledger.total > ZERO:
            # The committed-entry valuation is an independent synthetic floor,
            # not a current market/broker valuation. Missing authorization must
            # never turn an existing commitment into zero notional or margin.
            _validate_intent(state, item)
            model = item.intent.authorization.request.model
            notional_per_lot = _mul(item.intent.entry_price, dec(model.contract_size))
            live = _sum((item.filled_volume, item.closed_volume.copy_negate()))
            unfilled = (ZERO if item.terminal_status else
                        _sum((item.intent.volume, item.filled_volume.copy_negate())))
            reserved = unfilled if item.phase == Phase.RESERVED else ZERO
            uncertain = ZERO if item.phase == Phase.RESERVED else unfilled
            known_notional.append(_mul(_sum((live, reserved)), notional_per_lot))
            unknown_notional.append(_mul(uncertain, notional_per_lot))
            # available_margin is already net of confirmed-open margin, but
            # excludes every local unfilled commitment. No overlap credit with
            # broker pending-order margin exists in this offline contract.
            unresolved_margin.append(_mul(unfilled, dec(model.margin_per_lot)))
            other_count += 1
            if (item.intent.account_id, item.intent.symbol, item.intent.side) == (
                    record.intent.account_id, record.intent.symbol, record.intent.side):
                directional.append(_sum((live, unfilled)))
    request, context = fresh_authorization.request, fresh_authorization.context
    if (dec(request.held_risk) < _sum(known)
            or dec(request.held_unknown_risk) < _sum(unknown)
            or decision.risk.directional_volume_held < _sum(directional)
            or context.positions_and_pending < other_count):
        raise ValueError("FRESH_SNAPSHOT_UNDERREPORTS_HELD_EXPOSURE")
    if (dec(request.held_notional) < _sum(known_notional)
            or dec(request.held_unknown_notional) < _sum(unknown_notional)):
        raise ValueError("FRESH_SNAPSHOT_UNDERREPORTS_HELD_NOTIONAL")
    if dec(request.held_unknown_margin) < _sum(unresolved_margin):
        raise ValueError("FRESH_SNAPSHOT_UNDERREPORTS_UNRESOLVED_MARGIN")
    if (dec(context.daily_loss) < state.budget.realized_loss
            or dec(context.total_loss) < state.budget.realized_loss):
        raise ValueError("FRESH_SNAPSHOT_UNDERREPORTS_REALIZED_LOSS")
    if _sum((state.ledger.total, state.budget.realized_loss)) > state.budget.risk_limit:
        raise ValueError("FIXED_EPOCH_RISK_BUDGET")


def propose(state, intent):
    if not isinstance(intent, Intent):
        raise ValueError("INTENT_REQUIRED")
    for record in state.intents:
        if record.intent.client_intent_id == intent.client_intent_id:
            if record.intent != intent:
                raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return state
    _context(state)
    _entry_gate(state)
    if (intent.account_id, intent.account_revision) != (
            state.binding.account_id, state.binding.revision):
        raise ValueError("ACCOUNT_REVISION_CHANGED")
    record = ExecutionIntent(intent, state.context_generation,
                             protection=Protection(proposed_stop=intent.initial_sl),
                             budget_epoch_id=state.budget.epoch_id)
    return _commit(state, "propose", (intent,), intents=state.intents + (record,))


def approve(state, client_intent_id, approved_risk):
    record = state.get(client_intent_id)
    _context(state, record)
    _entry_gate(state)
    if record.intent.authorization is not None:
        _validate_intent(state, record)
    value = dec(approved_risk)
    if value != record.intent.requested_risk:
        raise ValueError("RISK_APPROVAL_MISMATCH")
    if record.phase == Phase.RISK_APPROVED:
        return state
    if record.phase != Phase.PROPOSED:
        raise ValueError("INVALID_APPROVAL_PHASE")
    record = replace(record, phase=Phase.RISK_APPROVED, approved_risk=value)
    return _commit(state, "approve", (client_intent_id, value), intents=_records(state, record))


def reserve(state, client_intent_id, max_total_risk, max_same_side_risk):
    record = state.get(client_intent_id)
    _context(state, record)
    _entry_gate(state)
    total_limit, side_limit = dec(max_total_risk), dec(max_same_side_risk)
    if total_limit < ZERO or side_limit < ZERO:
        raise ValueError("NONNEGATIVE_RISK_LIMIT_REQUIRED")
    if record.phase == Phase.RESERVED:
        return state
    if record.phase != Phase.RISK_APPROVED:
        raise ValueError("RISK_APPROVAL_REQUIRED")
    risk = record.intent.requested_risk
    if state.binding.policy is not None:
        _validate_intent(state, record)
        if _sum((state.ledger.total, risk, state.budget.realized_loss)) > state.budget.risk_limit:
            raise ValueError("FIXED_EPOCH_RISK_BUDGET")
    side_risk = _sum(item.ledger.total for item in state.intents
                     if (item.intent.account_id, item.intent.symbol, item.intent.side)
                     == (record.intent.account_id, record.intent.symbol, record.intent.side))
    if _sum((state.ledger.total, risk)) > total_limit:
        raise ValueError("TOTAL_RISK_LIMIT")
    if _sum((side_risk, risk)) > side_limit:
        raise ValueError("SAME_SIDE_RISK_LIMIT")
    record = replace(record, phase=Phase.RESERVED, reservation_made=True)
    return _commit(state, "reserve", (client_intent_id, total_limit, side_limit),
                   intents=_records(state, record))


def send_synthetic(state, client_intent_id, fresh_authorization=None, now_ms=None):
    """Record one attempted mock request. No adapter, callback, or I/O is used."""
    record = state.get(client_intent_id)
    _context(state, record)
    _entry_gate(state)
    if record.phase != Phase.RESERVED or any(
            item.client_intent_id == client_intent_id for item in state.requests):
        raise ValueError("NO_RESEND_OR_UNKNOWN_RETRY")
    _validate_intent(state, record)
    if fresh_authorization is None or now_ms is None:
        raise ValueError("EXPLICIT_FRESH_AUTHORIZATION_AND_TIME_REQUIRED")
    _fresh_check(state, record, fresh_authorization, now_ms)
    intent = record.intent
    request = SyntheticRequest(client_intent_id, intent.account_id, intent.account_revision,
                               intent.symbol, intent.side, intent.volume,
                               record.protection.proposed_stop, payload_hash=intent.payload_hash)
    record = replace(record, phase=Phase.SENT)
    return _commit(state, "send_synthetic", (client_intent_id, fresh_authorization, now_ms),
                   intents=_records(state, record), requests=state.requests + (request,))


def timeout(state, client_intent_id):
    record = state.get(client_intent_id)
    if record.phase == Phase.UNKNOWN:
        return state
    if record.phase not in (Phase.SENT, Phase.RESERVED):
        raise ValueError("NO_PENDING_REQUEST")
    # The model cannot prove a reserved request was never handed off before a
    # crash or timeout. Reconciliation, rather than a resend, resolves it.
    record = replace(record, phase=Phase.UNKNOWN)
    return _commit(state, "timeout", (client_intent_id,), intents=_records(state, record))


def recover(state):
    """Logical restart: retain reservations; sent outcomes become uncertain."""
    records = tuple(replace(item, phase=Phase.UNKNOWN,
                            protection=replace(item.protection, observation_current=False))
                    if item.phase in (Phase.SENT, Phase.RESERVED) else
                    replace(item, protection=replace(item.protection, observation_current=False))
                    for item in state.intents)
    return _commit(state, "recover", (), intents=records)


def update_context(state, binding):
    if not isinstance(binding, DemoBinding):
        raise ValueError("DEMO_BINDING_REQUIRED")
    if binding.account_id == state.binding.account_id and binding.revision < state.binding.revision:
        raise ValueError("ACCOUNT_REVISION_REGRESSION")
    if (binding.policy != state.binding.policy
            or binding.budget_epoch_id != state.budget.epoch_id
            or binding.epoch_risk_limit != state.budget.risk_limit):
        raise ValueError("PINNED_POLICY_OR_BUDGET_EPOCH_CHANGED")
    changed = (binding.account_id, binding.revision) != (
        state.binding.account_id, state.binding.revision)
    generation = state.context_generation + int(changed)
    records = tuple(replace(item, protection=replace(item.protection, observation_current=False))
                    for item in state.intents)
    return _commit(state, "update_context", (binding,), binding=binding,
                   context_generation=generation, intents=records)


def _quarantine(state, event, reason, record=None, retain_uncertainty=False):
    records = state.intents
    if record is not None and event.kind == "CLOSE":
        record = replace(record, close_uncertain=True,
                         unresolved_close_events=record.unresolved_close_events + (event,),
                         protection=replace(record.protection, observation_current=False))
        records = _records(state, record)
    elif record is not None and retain_uncertainty and record.reservation_made:
        # Contradictory evidence revokes release; it never invents a confirmed fill.
        record = replace(record, phase=Phase.UNKNOWN, terminal_status=None,
                         protection=replace(record.protection, observation_current=False))
        records = _records(state, record)
    return _commit(state, "apply_event", (event,), intents=records,
                   seen_events=state.seen_events + (event,),
                   quarantined=state.quarantined + (QuarantinedEvent(event, reason),))


def _apply_close(state, event, record):
    if (not event.authoritative or not event.terminal_proof or not event.net_costs_confirmed
            or event.net_pnl_provenance != "SYNTHETIC_CONFIRMED_NET"
            or event.close_volume is None or event.close_volume <= ZERO
            or event.realized_pnl is None or not event.deal_id or not event.position_id
            or not event.close_order_id or not event.cost_evidence_id):
        return _quarantine(state, event, "CONFIRMED_NET_CLOSE_PROOF_REQUIRED", record)
    if (event.budget_epoch_id != record.budget_epoch_id
            or event.budget_epoch_id != state.budget.epoch_id):
        return _quarantine(state, event, "CLOSE_BUDGET_EPOCH_MISMATCH", record)
    evidence = CloseSettlement(event.deal_id, event.close_order_id, event.position_id,
                               event.close_volume, event.realized_pnl, event.cost_evidence_id,
                               event.budget_epoch_id)
    pending = tuple(previous for previous in record.unresolved_close_events
                    if not (previous.deal_id == event.deal_id
                            or (event.reconciles_event_id == previous.event_id
                                and (previous.deal_id is None or previous.deal_id == event.deal_id))))
    resolved = tuple(previous for previous in record.unresolved_close_events if previous not in pending)
    if resolved and event.sequence <= max(record.last_sequence,
                                          max(previous.sequence for previous in resolved)):
        return _quarantine(state, event, "OUT_OF_ORDER_CLOSE_RECONCILIATION", record)
    for item in state.intents:
        if event.deal_id in item.deal_ids:
            return _quarantine(state, event, "ENTRY_DEAL_CANNOT_BE_CLOSE_DEAL", record)
        for previous in item.close_deals:
            if previous.deal_id == event.deal_id:
                if item.intent.client_intent_id != record.intent.client_intent_id or previous != evidence:
                    return _quarantine(state, event, "CLOSE_DEAL_ID_PAYLOAD_CONFLICT", record)
                record = replace(record, unresolved_close_events=pending, close_uncertain=bool(pending))
                return _commit(state, "apply_event", (event,),
                               intents=_records(state, record),
                               seen_events=state.seen_events + (event,))
            if previous.cost_evidence_id == event.cost_evidence_id:
                return _quarantine(state, event, "CLOSE_COST_EVIDENCE_REUSED", record)
    if event.sequence <= record.last_sequence:
        return _quarantine(state, event, "OUT_OF_ORDER_CLOSE", record)
    if (event.position_id not in record.position_ids or not record.position_evidence_complete
            or len(record.position_ids) != 1 or not record.reservation_made):
        return _quarantine(state, event, "CLOSE_POSITION_IDENTITY_AMBIGUOUS", record)
    remaining_open = _sum((record.filled_volume, record.closed_volume.copy_negate()))
    if event.close_volume > remaining_open:
        return _quarantine(state, event, "CLOSE_EXCEEDS_CONFIRMED_OPEN_VOLUME", record)
    closed = _sum((record.closed_volume, event.close_volume))
    record = replace(record, closed_volume=closed, close_deals=record.close_deals + (evidence,),
                     close_uncertain=bool(pending), unresolved_close_events=pending,
                     last_sequence=event.sequence,
                     protection=replace(record.protection, observation_current=False))
    loss = max(ZERO, event.realized_pnl.copy_negate())
    profit = max(ZERO, event.realized_pnl)
    # Realized gap losses are evidence even above budget. Charge them and let
    # the next reservation fail; rejecting them would erase a real liability.
    budget = replace(state.budget,
                     realized_loss=_sum((state.budget.realized_loss, loss)),
                     realized_profit=_sum((state.budget.realized_profit, profit)))
    return _commit(state, "apply_event", (event,), intents=_records(state, record),
                   seen_events=state.seen_events + (event,), budget=budget)


def apply_event(state, event):
    if not isinstance(event, BrokerEvent):
        raise ValueError("BROKER_EVENT_REQUIRED")
    for previous in state.seen_events:
        if previous.event_id == event.event_id:
            if previous != event:
                raise ValueError("EVENT_ID_PAYLOAD_CONFLICT")
            return state
    try:
        record = state.get(event.client_intent_id)
    except ValueError:
        return _quarantine(state, event, "UNKNOWN_CLIENT_INTENT_ID")
    if (event.account_id, event.account_revision) != (
            record.intent.account_id, record.intent.account_revision):
        return _quarantine(state, event, "EVENT_ACCOUNT_MISMATCH", record)
    recorded_attempt = any(item.client_intent_id == event.client_intent_id for item in state.requests)
    recovered_reservation = (record.phase == Phase.UNKNOWN and record.reservation_made
                             and event.kind == "RECONCILE" and event.authoritative)
    if not recorded_attempt and not recovered_reservation:
        return _quarantine(state, event, "UNSENT_INTENT", record)
    if record.order_id and event.order_id and record.order_id != event.order_id:
        return _quarantine(state, event, "ORDER_ID_MISMATCH", record, True)
    if event.kind == "CLOSE":
        return _apply_close(state, event, record)
    fill = event.cumulative_filled
    if event.sequence <= record.last_sequence:
        contradicts = fill is not None and fill > record.filled_volume
        return _quarantine(state, event, "OUT_OF_ORDER", record, contradicts)
    if fill is not None and (fill < record.filled_volume or fill > record.intent.volume):
        return _quarantine(state, event, "INCONSISTENT_CUMULATIVE_FILL", record, True)
    if event.deal_id is not None:
        evidence = (event.deal_id, fill, event.order_id, event.position_id)
        for previous in record.deal_evidence:
            if previous[0] == event.deal_id and previous != evidence:
                return _quarantine(state, event, "DEAL_ID_PAYLOAD_CONFLICT", record, True)
    if record.terminal_status and event.kind != "RECONCILE":
        return _quarantine(state, event, "EVENT_AFTER_TERMINAL", record,
                           fill is not None and fill != record.filled_volume)
    terminal = None
    if event.kind == "ACK":
        if not event.order_id or (fill is not None and fill != record.filled_volume):
            return _quarantine(state, event, "INVALID_ACK", record, True)
    elif event.kind == "FILL":
        if fill is None or not event.deal_id or not event.position_id or not event.order_id:
            return _quarantine(state, event, "INCOMPLETE_FILL_EVIDENCE", record, True)
        if fill == record.intent.volume:
            terminal = "FILLED"
    elif event.kind in ("CANCELLED", "REJECTED"):
        if (not event.terminal_proof or fill is None
                or (event.kind == "CANCELLED" and not event.order_id)
                or (event.kind == "REJECTED" and fill != ZERO)):
            return _quarantine(state, event, "TERMINAL_PROOF_REQUIRED", record, True)
        terminal = event.kind
    elif event.kind == "RECONCILE":
        if not event.authoritative or fill is None:
            return _quarantine(state, event, "AUTHORITATIVE_RECONCILIATION_REQUIRED", record, True)
        terminal = event.terminal_status
        if terminal == "OPEN":
            terminal = None
        if ((terminal and not event.terminal_proof)
                or (terminal == "FILLED" and fill != record.intent.volume)
                or (terminal in ("REJECTED", "NOT_SENT") and fill != ZERO)
                or (terminal == "NOT_SENT" and (recorded_attempt or event.order_id
                                                or event.deal_id or event.position_id))
                or (terminal in (None, "CANCELLED", "FILLED") and not event.order_id)):
            return _quarantine(state, event, "INVALID_RECONCILIATION_PROOF", record, True)
    filled = record.filled_volume if fill is None else fill
    phase = Phase.RECONCILED if terminal else (
        Phase.SENT if event.kind == "ACK" and record.phase == Phase.SENT else Phase.UNKNOWN)
    positions = record.position_ids + ((event.position_id,) if event.position_id and
                                       event.position_id not in record.position_ids else ())
    complete_positions = record.position_evidence_complete
    if filled > record.filled_volume and event.position_id is None:
        complete_positions = False
    if event.kind == "RECONCILE" and event.authoritative and event.position_id:
        complete_positions = True
    complete_positions = complete_positions and len(positions) <= 1
    protection = record.protection
    if not complete_positions or positions != record.position_ids:
        protection = replace(protection, observation_current=False)
    record = replace(record, phase=phase, filled_volume=filled, terminal_status=terminal,
                     order_id=event.order_id or record.order_id,
                     deal_ids=record.deal_ids + ((event.deal_id,) if event.deal_id and
                                                event.deal_id not in record.deal_ids else ()),
                     deal_evidence=record.deal_evidence + (
                         ((event.deal_id, fill, event.order_id, event.position_id),)
                         if event.deal_id and event.deal_id not in record.deal_ids else ()),
                     position_ids=positions, position_evidence_complete=complete_positions,
                     protection=protection,
                     last_sequence=event.sequence)
    return _commit(state, "apply_event", (event,), intents=_records(state, record),
                   seen_events=state.seen_events + (event,))


def _at_least_protective(side, candidate, previous):
    return candidate >= previous if side == "BUY" else candidate <= previous


def _managed_position(record):
    if record.filled_volume <= record.closed_volume:
        raise ValueError("CONFIRMED_POSITION_REQUIRED")
    if len(record.position_ids) != 1 or not record.position_evidence_complete:
        raise ValueError("UNAMBIGUOUS_MANAGED_POSITION_REQUIRED")


def propose_stop(state, client_intent_id, stop, current_price, minimum_distance="0"):
    record = state.get(client_intent_id)
    _context(state, record)
    _managed_position(record)
    candidate, price, distance = dec(stop), dec(current_price), dec(minimum_distance)
    if candidate <= ZERO or price <= ZERO or distance < ZERO:
        raise ValueError("INVALID_STOP_INPUT")
    gap = (_sum((price, candidate.copy_negate())) if record.intent.side == "BUY"
           else _sum((candidate, price.copy_negate())))
    if gap <= ZERO or gap < distance:
        raise ValueError("STOP_WRONG_SIDE_OR_DISTANCE")
    previous = tuple(x for x in (record.protection.proposed_stop,
                                record.protection.acknowledged_stop) if x is not None)
    previous += record.protection.observed_history
    if any(not _at_least_protective(record.intent.side, candidate, x) for x in previous):
        raise ValueError("STOP_WEAKENING_FORBIDDEN")
    record = replace(record, protection=replace(record.protection, proposed_stop=candidate))
    return _commit(state, "propose_stop", (client_intent_id, candidate, price, distance),
                   intents=_records(state, record))


def acknowledge_stop(state, client_intent_id, stop):
    record = state.get(client_intent_id)
    _context(state, record)
    _managed_position(record)
    value = dec(stop)
    if value != record.protection.proposed_stop:
        raise ValueError("UNPROPOSED_STOP_ACK")
    record = replace(record, protection=replace(record.protection, acknowledged_stop=value))
    return _commit(state, "acknowledge_stop", (client_intent_id, value), intents=_records(state, record))


def observe_stop(state, client_intent_id, stop=None, complete=False):
    """An omitted field is a partial update; a complete missing stop is a fault.

    A weaker server observation is retained as evidence and revokes the current
    protection claim. It never authorizes a weaker proposal or erases history.
    """
    _boolean(complete)
    record = state.get(client_intent_id)
    _context(state, record)
    _managed_position(record)
    protection = record.protection
    if stop is None and not complete:
        return state
    value = None if stop is None else dec(stop)
    if value is not None and value <= ZERO:
        raise ValueError("POSITIVE_STOP_REQUIRED")
    fault = None
    if value is None:
        fault = "SERVER_STOP_NOT_PRESENT"
    elif any(not _at_least_protective(record.intent.side, value, previous)
             for previous in protection.observed_history):
        fault = "SERVER_STOP_WEAKENED"
    history = protection.observed_history + ((value,) if value is not None else ())
    protection = replace(protection,
                         observed_stop=protection.observed_stop if value is None else value,
                         observed_history=history, observation_current=fault is None,
                         observation_revision=state.binding.revision,
                         observation_generation=state.context_generation, safety_fault=fault)
    record = replace(record, protection=protection)
    return _commit(state, "observe_stop", (client_intent_id, value, complete), intents=_records(state, record))


def replay(trace):
    """Rebuild only from an immutable in-memory command trace. No I/O occurs."""
    trace = tuple(trace)
    if not trace or trace[0].operation != "start":
        raise ValueError("TRACE_MUST_START_WITH_BINDING")
    state = start(*trace[0].arguments)
    operations = {function.__name__: function for function in
                  (propose, approve, reserve, send_synthetic, timeout, recover,
                   update_context, apply_event, propose_stop, acknowledge_stop, observe_stop)}
    for entry in trace[1:]:
        if entry.operation not in operations:
            raise ValueError("UNKNOWN_TRACE_OPERATION")
        state = operations[entry.operation](state, *entry.arguments)
    if state.trace != trace:
        raise ValueError("NONCANONICAL_TRACE")
    return state


class MockBroker:
    """Scripted synthetic events only; there is deliberately no real send API."""

    def __init__(self, events=(), lose_response=False):
        self.events = tuple(events)
        if any(not isinstance(event, BrokerEvent) for event in self.events):
            raise ValueError("SYNTHETIC_EVENTS_REQUIRED")
        self.lose_response = _boolean(lose_response)
        self._attempted = []

    @property
    def attempted(self):
        return tuple(self._attempted)

    def dispatch(self, executor, client_intent_id, fresh_authorization, now_ms):
        if type(executor) is not MemoryExecutor:
            raise ValueError("MEMORY_EXECUTOR_REQUIRED")
        # Commit the attempted state before processing any response. Even a
        # malformed response cannot roll the wrapper back into resend eligibility.
        executor.state = send_synthetic(executor.state, client_intent_id, fresh_authorization, now_ms)
        self._attempted.append(executor.state.requests[-1])
        if self.lose_response:
            executor.state = timeout(executor.state, client_intent_id)
            return executor.state
        for event in self.events:
            if event.client_intent_id == client_intent_id:
                executor.state = apply_event(executor.state, event)
        return executor.state


class MemoryExecutor:
    """Small mutable convenience shell around the pure transitions above."""

    def __init__(self, binding=None, *, trace=None):
        if (binding is None) == (trace is None):
            raise ValueError("PROVIDE_BINDING_OR_MEMORY_TRACE")
        self.state = replay(trace) if trace is not None else start(binding)

    def transition(self, operation, *arguments):
        allowed = {function.__name__: function for function in
                   (propose, approve, reserve, timeout, recover, update_context,
                    apply_event, propose_stop, acknowledge_stop, observe_stop)}
        if operation not in allowed:
            raise ValueError("OFFLINE_TRANSITION_REQUIRED")
        self.state = allowed[operation](self.state, *arguments)
        return self.state

    def send(self, broker, client_intent_id, fresh_authorization=None, now_ms=None):
        if type(broker) is not MockBroker:
            raise ValueError("MOCK_BROKER_ONLY")
        return broker.dispatch(self, client_intent_id, fresh_authorization, now_ms)
