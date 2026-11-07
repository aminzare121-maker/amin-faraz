"""Injected broker-contract fixtures. No adapter, clock, network or attestation.

Every identity and observation below is OFFLINE_SYNTHETIC. Entry-based notional
is a conservative accounting contract, not a current broker valuation. Even an
allowed decision is only a fixture result and cannot execute an order.
Prices, margins and cash must already use the declared account currency; there
is no implicit currency conversion. Bounded Decimal inputs and at most 4096 rows
permit exact arithmetic with a private 1024-digit context, independent of callers.
"""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from faraz_core.numbers import dec, natural


ZERO = Decimal("0")


def _id(value):
    if type(value) is not str or not value.strip():
        raise ValueError("NONEMPTY_CONTRACT_ID_REQUIRED")
    return value


def _amount(value, positive=False):
    result = dec(value)
    if result < ZERO or (positive and result == ZERO):
        raise ValueError("INVALID_CONTRACT_AMOUNT")
    return result


def _tuple(value):
    if type(value) is not tuple or len(value) > 4096:
        raise ValueError("IMMUTABLE_CONTRACT_TUPLE_REQUIRED")
    return value


def _binding(expected, actual):
    if type(expected) is not SyntheticAccount or actual != expected:
        raise ValueError("SYNTHETIC_ACCOUNT_OWNERSHIP_BINDING_MISMATCH")


@dataclass(frozen=True)
class SyntheticAccount:
    account_id: str
    revision: int
    owner_scope: str
    currency: str = "USD"
    mode: str = "DEMO"
    synthetic: bool = True
    ownership_complete: bool = True
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)

    def __post_init__(self):
        for value in (self.account_id, self.owner_scope, self.currency):
            _id(value)
        natural(self.revision)
        if self.mode != "DEMO" or self.synthetic is not True:
            raise ValueError("SYNTHETIC_DEMO_CONTRACT_ONLY")
        if self.ownership_complete is not True:
            raise ValueError("COMPLETE_OWNERSHIP_REQUIRED")


@dataclass(frozen=True)
class TypedRef:
    kind: str
    reference_id: str

    def __post_init__(self):
        _id(self.reference_id)
        if self.kind not in ("POSITION", "PENDING", "UNKNOWN", "INTENT", "DEAL"):
            raise ValueError("INVALID_TYPED_REFERENCE")


@dataclass(frozen=True)
class ExposureSlice:
    account: SyntheticAccount
    reference: TypedRef
    symbol: str
    side: str
    volume: object
    entry: object
    contract: object
    margin_per_lot: object
    position_revision: int = 0

    def __post_init__(self):
        if type(self.account) is not SyntheticAccount or type(self.reference) is not TypedRef:
            raise ValueError("TYPED_EXPOSURE_REQUIRED")
        if self.reference.kind == "DEAL" or self.side not in ("BUY", "SELL", "UNKNOWN"):
            raise ValueError("INVALID_EXPOSURE_CONTRACT")
        _id(self.symbol)
        natural(self.position_revision)
        for name in ("volume", "entry", "contract", "margin_per_lot"):
            object.__setattr__(self, name, _amount(getattr(self, name), True))


@dataclass(frozen=True)
class SliceOverlap:
    account: SyntheticAccount
    position: TypedRef
    pending: TypedRef
    position_start: object
    pending_start: object
    volume: object
    evidence_id: str
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)

    def __post_init__(self):
        if (type(self.position) is not TypedRef or self.position.kind != "POSITION"
                or type(self.pending) is not TypedRef or self.pending.kind != "PENDING"):
            raise ValueError("POSITION_PENDING_OVERLAP_REQUIRED")
        _id(self.evidence_id)
        for name in ("position_start", "pending_start", "volume"):
            object.__setattr__(self, name, _amount(getattr(self, name), name == "volume"))


@dataclass(frozen=True)
class ContractLedger:
    account: SyntheticAccount
    rows: tuple
    overlaps: tuple
    covered_intervals: tuple
    known_notional: Decimal
    unknown_notional: Decimal
    unfilled_margin: Decimal
    valuation_basis: str = field(default="SYNTHETIC_COMMITTED_ENTRY_GROSS", init=False)

    def __post_init__(self):
        for name in ("known_notional", "unknown_notional", "unfilled_margin"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value < ZERO:
                raise ValueError("EXACT_DERIVED_DECIMAL_REQUIRED")

    @property
    def total_notional(self):
        with localcontext() as context:
            context.prec = 1024
            return self.known_notional + self.unknown_notional


def reconcile_exposures(account, rows, overlaps=()):
    """Deduplicate typed identities; credit only explicit nonoverlapping slices.

    POSITION is known; local INTENT/RESERVED is known but retains extra margin.
    PENDING/UNKNOWN are unknown. Equal text IDs across kinds never imply overlap.
    A linked filled slice is subtracted from PENDING only, never from POSITION.
    Different entry/valuation bases cannot obtain overlap credit in this lab.
    """
    _binding(account, account)
    unique = {}
    for row in _tuple(rows):
        if type(row) is not ExposureSlice:
            raise ValueError("EXPOSURE_SLICE_REQUIRED")
        _binding(account, row.account)
        previous = unique.get(row.reference)
        if previous is not None and previous != row:
            raise ValueError("CONFLICTING_TYPED_EXPOSURE")
        unique[row.reference] = row
    evidence, intervals = {}, {}
    with localcontext() as context:
        context.prec = 1024
        for proof in _tuple(overlaps):
            if type(proof) is not SliceOverlap:
                raise ValueError("EXPLICIT_SLICE_PROOF_REQUIRED")
            _binding(account, proof.account)
            if proof.evidence_id in evidence:
                if evidence[proof.evidence_id] != proof:
                    raise ValueError("CONFLICTING_OVERLAP_EVIDENCE")
                continue
            position, pending = unique.get(proof.position), unique.get(proof.pending)
            if position is None or pending is None:
                raise ValueError("OVERLAP_REFERENCE_NOT_PRESENT")
            if (position.side == "UNKNOWN" or (position.symbol, position.side, position.entry,
                    position.contract, position.margin_per_lot) != (pending.symbol, pending.side,
                    pending.entry, pending.contract, pending.margin_per_lot)):
                raise ValueError("OVERLAP_BASIS_OR_DIRECTION_MISMATCH")
            for reference, start, limit in ((proof.position, proof.position_start, position.volume),
                                           (proof.pending, proof.pending_start, pending.volume)):
                end = start + proof.volume
                if end > limit:
                    raise ValueError("OVERLAP_EXCEEDS_VOLUME_SLICE")
                prior = intervals.setdefault(reference, [])
                if any(start < old_end and old_start < end for old_start, old_end in prior):
                    raise ValueError("OVERLAP_SLICE_CREDIT_REUSED")
                prior.append((start, end))
            evidence[proof.evidence_id] = proof
        known, unknown, margin = ZERO, ZERO, ZERO
        for row in unique.values():
            remaining = row.volume
            if row.reference.kind == "PENDING":
                remaining -= sum((end - start for start, end in intervals.get(row.reference, ())), ZERO)
            notional = remaining * row.entry * row.contract
            if row.reference.kind in ("POSITION", "INTENT"):
                known += notional
            else:
                unknown += notional
            if row.reference.kind != "POSITION":
                margin += remaining * row.margin_per_lot
        ordered_rows = tuple(sorted(unique.values(), key=lambda row: (row.reference.kind, row.reference.reference_id)))
        covered = tuple((ref, start, end) for ref in sorted(intervals,
                        key=lambda ref: (ref.kind, ref.reference_id))
                        for start, end in sorted(intervals[ref]))
        proofs = tuple(evidence[key] for key in sorted(evidence))
        return ContractLedger(account, ordered_rows, proofs, covered, known, unknown, margin)


def _validate_ledger(ledger):
    if (type(ledger) is not ContractLedger or
            reconcile_exposures(ledger.account, ledger.rows, ledger.overlaps) != ledger):
        raise ValueError("DERIVED_CONTRACT_LEDGER_MISMATCH")


@dataclass(frozen=True)
class PendingMarginCoverage:
    reference: TypedRef
    start: object
    volume: object
    margin: object
    evidence_id: str

    def __post_init__(self):
        if type(self.reference) is not TypedRef or self.reference.kind != "PENDING":
            raise ValueError("PENDING_MARGIN_REFERENCE_REQUIRED")
        _id(self.evidence_id)
        for name in ("start", "volume", "margin"):
            object.__setattr__(self, name, _amount(getattr(self, name)))


@dataclass(frozen=True)
class MarginSnapshot:
    account: SyntheticAccount
    available: object
    basis: str
    pending_coverage: tuple = ()
    coverage_complete: bool = False
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)

    def __post_init__(self):
        object.__setattr__(self, "available", _amount(self.available))
        _tuple(self.pending_coverage)
        if type(self.coverage_complete) is not bool:
            raise ValueError("EXPLICIT_MARGIN_COVERAGE_STATE_REQUIRED")


@dataclass(frozen=True)
class MappedMargin:
    ledger: ContractLedger
    snapshot: MarginSnapshot
    available_margin: Decimal
    held_unknown_margin: Decimal
    reflected_pending_margin: Decimal

    def __post_init__(self):
        for name in ("available_margin", "held_unknown_margin", "reflected_pending_margin"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value < ZERO:
                raise ValueError("EXACT_DERIVED_DECIMAL_REQUIRED")


def map_margin(account, ledger, snapshot):
    """Normalize only declared synthetic bases; raw broker free margin vetoes.

    Canonical available_margin is after confirmed-open margin and before ALL
    local unfilled commitments. If free margin already deducts proven pending
    slices, add back exactly those debits, then deduct all unfilled margin once.
    Incomplete coverage cannot obtain overlap credit or enter this mapping.
    """
    if type(ledger) is not ContractLedger or type(snapshot) is not MarginSnapshot:
        raise ValueError("MARGIN_CONTRACT_REQUIRED")
    _binding(account, ledger.account)
    _binding(account, snapshot.account)
    _validate_ledger(ledger)
    reflected = ZERO
    if snapshot.basis == "POST_OPEN_PRE_UNFILLED":
        if snapshot.pending_coverage:
            raise ValueError("CANONICAL_MARGIN_CANNOT_ADD_PENDING_CREDIT")
    elif snapshot.basis == "FREE_AFTER_EXPLICIT_PENDING_DEBITS":
        if not snapshot.coverage_complete:
            raise ValueError("COMPLETE_PENDING_COVERAGE_REQUIRED")
        pending = {row.reference: row for row in ledger.rows if row.reference.kind == "PENDING"}
        seen_refs, seen_ids = set(), set()
        with localcontext() as context:
            context.prec = 1024
            for proof in snapshot.pending_coverage:
                if type(proof) is not PendingMarginCoverage or proof.reference not in pending:
                    raise ValueError("UNKNOWN_PENDING_MARGIN_COVERAGE")
                if proof.reference in seen_refs or proof.evidence_id in seen_ids:
                    raise ValueError("PENDING_MARGIN_COVERAGE_REUSED")
                row = pending[proof.reference]
                end = proof.start + proof.volume
                if end > row.volume or any(ref == proof.reference and proof.start < covered_end
                        and covered_start < end for ref, covered_start, covered_end in ledger.covered_intervals):
                    raise ValueError("PENDING_MARGIN_COVERS_FILLED_OR_INVALID_SLICE")
                if proof.margin != proof.volume * row.margin_per_lot:
                    raise ValueError("PENDING_MARGIN_AMOUNT_MISMATCH")
                reflected += proof.margin
                seen_refs.add(proof.reference)
                seen_ids.add(proof.evidence_id)
            if seen_refs != set(pending):
                raise ValueError("MISSING_PENDING_MARGIN_COVERAGE")
    else:
        raise ValueError("UNVERIFIED_FREE_MARGIN_BASIS")
    with localcontext() as context:
        context.prec = 1024
        return MappedMargin(ledger, snapshot, snapshot.available + reflected, ledger.unfilled_margin, reflected)


@dataclass(frozen=True)
class CapacityDecision:
    allowed: bool
    reasons: tuple
    total_notional: Decimal
    required_margin: Decimal
    available_margin: Decimal
    can_execute: bool = field(default=False, init=False)


def check_capacity(ledger, mapping, new_notional, new_margin, notional_cap):
    if type(ledger) is not ContractLedger or type(mapping) is not MappedMargin or mapping.ledger != ledger:
        raise ValueError("CAPACITY_LEDGER_BINDING_MISMATCH")
    if map_margin(ledger.account, ledger, mapping.snapshot) != mapping:
        raise ValueError("DERIVED_MARGIN_MAPPING_MISMATCH")
    new_notional, new_margin, cap = (_amount(new_notional, True), _amount(new_margin, True),
                                     _amount(notional_cap))
    with localcontext() as context:
        context.prec = 1024
        total = ledger.total_notional + new_notional
        required = mapping.held_unknown_margin + new_margin
        reasons = tuple(reason for condition, reason in ((total > cap, "NOTIONAL_CAP"),
                        (required > mapping.available_margin, "MARGIN_CAP")) if condition)
        return CapacityDecision(not reasons, reasons, total, required, mapping.available_margin)


@dataclass(frozen=True)
class QuoteObservation:
    symbol: str
    bid: object
    ask: object
    observed_ms: int
    available_ms: int
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)

    def __post_init__(self):
        _id(self.symbol)
        for name in ("bid", "ask"):
            object.__setattr__(self, name, _amount(getattr(self, name), True))
        natural(self.observed_ms)
        natural(self.available_ms)
        if self.ask < self.bid or self.available_ms < self.observed_ms:
            raise ValueError("INVALID_QUOTE_OBSERVATION")


def executable_price(quote, symbol, side, action, now_ms, max_age_ms):
    now_ms, max_age_ms = natural(now_ms), natural(max_age_ms)
    if type(quote) is not QuoteObservation or quote.symbol != symbol:
        raise ValueError("QUOTE_SYMBOL_MISMATCH")
    if side not in ("BUY", "SELL") or action not in ("ENTRY", "CLOSE"):
        raise ValueError("EXECUTABLE_PRICE_SIDE_REQUIRED")
    if quote.available_ms > now_ms or now_ms - quote.observed_ms > max_age_ms:
        raise ValueError("STALE_OR_FUTURE_QUOTE")
    return quote.ask if (side == "BUY") == (action == "ENTRY") else quote.bid


@dataclass(frozen=True)
class OffsetPeriod:
    utc_start_ms: int
    utc_end_ms: int
    offset_minutes: int

    def __post_init__(self):
        natural(self.utc_start_ms)
        natural(self.utc_end_ms)
        if (self.utc_end_ms <= self.utc_start_ms or type(self.offset_minutes) is not int
                or abs(self.offset_minutes) > 1440):
            raise ValueError("INVALID_INJECTED_OFFSET_PERIOD")


@dataclass(frozen=True)
class SessionWindow:
    local_start_ms: int
    local_end_ms: int

    def __post_init__(self):
        natural(self.local_start_ms)
        natural(self.local_end_ms)
        if self.local_end_ms <= self.local_start_ms:
            raise ValueError("INVALID_INJECTED_SESSION_WINDOW")


@dataclass(frozen=True)
class SessionCalendar:
    calendar_id: str
    revision: int
    offsets: tuple
    windows: tuple
    complete: bool = True

    def __post_init__(self):
        _id(self.calendar_id)
        natural(self.revision)
        _tuple(self.offsets)
        _tuple(self.windows)
        if type(self.complete) is not bool or any(type(row) is not OffsetPeriod for row in self.offsets):
            raise ValueError("EXPLICIT_INJECTED_CALENDAR_REQUIRED")
        if any(type(row) is not SessionWindow for row in self.windows):
            raise ValueError("EXPLICIT_INJECTED_CALENDAR_REQUIRED")
        ordered = sorted(self.offsets, key=lambda row: row.utc_start_ms)
        if any(left.utc_end_ms > right.utc_start_ms for left, right in zip(ordered, ordered[1:])):
            raise ValueError("OVERLAPPING_UTC_OFFSET_PERIODS")


def local_to_utc(calendar, local_ms, fold=None):
    natural(local_ms)
    if type(calendar) is not SessionCalendar or not calendar.complete:
        raise ValueError("UNKNOWN_SESSION_CALENDAR")
    candidates = sorted({local_ms - period.offset_minutes * 60000 for period in calendar.offsets
                         if period.utc_start_ms <= local_ms - period.offset_minutes * 60000 < period.utc_end_ms})
    if not candidates:
        raise ValueError("NONEXISTENT_OR_UNKNOWN_LOCAL_TIME")
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise ValueError("INVALID_EXPLICIT_FOLD")
    if len(candidates) > 2 or (len(candidates) == 2 and fold is None):
        raise ValueError("AMBIGUOUS_LOCAL_TIME_REQUIRES_FOLD")
    index = 0 if fold is None else fold
    if index >= len(candidates):
        raise ValueError("INVALID_EXPLICIT_FOLD")
    return candidates[index]


def session_allows_entry(calendar, utc_ms):
    natural(utc_ms)
    if type(calendar) is not SessionCalendar or not calendar.complete:
        return False, "UNKNOWN_SESSION_CALENDAR"
    period = next((row for row in calendar.offsets if row.utc_start_ms <= utc_ms < row.utc_end_ms), None)
    if period is None:
        return False, "UNKNOWN_UTC_OFFSET"
    local = utc_ms + period.offset_minutes * 60000
    allowed = any(row.local_start_ms <= local < row.local_end_ms for row in calendar.windows)
    return allowed, "INJECTED_SESSION_OPEN" if allowed else "INJECTED_SESSION_CLOSED"


@dataclass(frozen=True)
class StopObservation:
    account: SyntheticAccount
    position: TypedRef
    symbol: str
    position_revision: int
    observed_ms: int
    stop: object
    complete: bool
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)
    broker_protection_confirmed: bool = field(default=False, init=False)

    def __post_init__(self):
        if type(self.position) is not TypedRef or self.position.kind != "POSITION":
            raise ValueError("STOP_POSITION_REFERENCE_REQUIRED")
        _id(self.symbol)
        natural(self.position_revision)
        natural(self.observed_ms)
        if type(self.complete) is not bool:
            raise ValueError("EXPLICIT_STOP_COMPLETENESS_REQUIRED")
        if self.stop is not None:
            object.__setattr__(self, "stop", _amount(self.stop, True))


def synthetic_stop_observed(account, position, observation, now_ms, max_age_ms):
    if type(position) is not ExposureSlice or type(observation) is not StopObservation:
        raise ValueError("STOP_OBSERVATION_CONTRACT_REQUIRED")
    _binding(account, position.account)
    _binding(account, observation.account)
    natural(now_ms)
    natural(max_age_ms)
    if (position.reference != observation.position or position.symbol != observation.symbol
            or position.position_revision != observation.position_revision):
        raise ValueError("STOP_POSITION_REVISION_MISMATCH")
    return (observation.complete and observation.stop is not None
            and observation.observed_ms <= now_ms
            and now_ms - observation.observed_ms <= max_age_ms)


@dataclass(frozen=True)
class NetCostEvidence:
    account: SyntheticAccount
    deal: TypedRef
    cost_id: str
    gross: object
    entry_fee: object
    exit_fee: object
    swap: object
    net: object
    confirmed: bool
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)

    def __post_init__(self):
        if type(self.deal) is not TypedRef or self.deal.kind != "DEAL":
            raise ValueError("COST_DEAL_REFERENCE_REQUIRED")
        _id(self.cost_id)
        if self.confirmed is not True:
            raise ValueError("CONFIRMED_NET_COSTS_REQUIRED")
        for name in ("gross", "entry_fee", "exit_fee", "swap", "net"):
            object.__setattr__(self, name, dec(getattr(self, name)))
        with localcontext() as context:
            context.prec = 1024
            if self.gross + self.entry_fee + self.exit_fee + self.swap != self.net:
                raise ValueError("NET_COST_CONSERVATION_FAILURE")


def confirmed_net_total(account, evidence):
    deals, costs = {}, {}
    with localcontext() as context:
        context.prec = 1024
        for row in _tuple(evidence):
            if type(row) is not NetCostEvidence:
                raise ValueError("NET_COST_EVIDENCE_REQUIRED")
            _binding(account, row.account)
            if row.deal in deals:
                if deals[row.deal] != row:
                    raise ValueError("CONFLICTING_DEAL_COST_EVIDENCE")
                continue
            if row.cost_id in costs:
                raise ValueError("COST_EVIDENCE_REUSED_ACROSS_DEALS")
            deals[row.deal], costs[row.cost_id] = row, row.deal
        return sum((row.net for row in deals.values()), ZERO)
