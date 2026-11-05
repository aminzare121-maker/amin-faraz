"""Pure, synthetic linear sizing. This is not a broker valuation model.

Every limit and monetary input is required explicitly. Decimal strings, integers
and Decimal values are accepted; binary floats and unknown values fail closed.
The MT5 volume lattice is k * step, constrained by min/max, never min + k*step.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, MAX_EMAX, MIN_EMIN, localcontext
from typing import Tuple

from .numbers import dec


@dataclass(frozen=True)
class VolumeRules:
    minimum: object
    step: object
    maximum: object
    volume_limit: object


@dataclass(frozen=True)
class ExposureAmount:
    """One typed position/order/unknown amount with a source-local identifier.

    UNKNOWN side reserves volume against either direction. UNKNOWN kind means
    an unresolved position/order classification, not an unknown numeric volume.
    Identity is (account_id, symbol, kind, reference_id). Identical same-kind
    records count once; a conflicting same-kind record rejects the snapshot.
    Different kinds always add, even with the same reference_id. No link or
    covered-volume reconciliation is inferred between positions, orders and
    UNKNOWN records; the caller must retain unresolved exposure conservatively.
    """
    account_id: str
    symbol: str
    side: str
    kind: str
    reference_id: str
    volume: object


@dataclass(frozen=True)
class LinearRiskModel:
    contract_size: object
    entry_cost_per_lot: object
    exit_cost_per_lot: object
    slippage_reserve_per_lot: object
    gap_reserve_per_lot: object
    margin_per_lot: object


@dataclass(frozen=True)
class RiskRequest:
    """Synthetic monetary snapshot; no broker free-margin attestation.

    available_margin is capacity after confirmed-open margin, but BEFORE all
    local unfilled reserved/pending/unknown margin. held_unknown_margin contains
    those unfilled commitments, including RESERVED. Open margin is not deducted
    twice. No credit for overlap with broker pending-order margin is supported.
    held_notional and held_unknown_notional are disjoint gross committed-entry
    amounts (entry * contract * retained volume), with no side/symbol netting.
    A real marked valuation or broker margin reconciliation is outside this API.
    """
    account_id: str
    symbol: str
    side: str
    entry: object
    stop: object
    risk_budget: object
    rules: VolumeRules
    model: LinearRiskModel
    exposures: Tuple[ExposureAmount, ...]
    available_margin: object
    notional_cap: object
    portfolio_risk_cap: object
    held_risk: object
    held_unknown_risk: object
    held_notional: object
    held_unknown_notional: object
    held_unknown_margin: object


@dataclass(frozen=True)
class RiskDecision:
    action: str
    reasons: Tuple[str, ...]
    volume: Decimal = Decimal("0")
    risk_per_lot: Decimal = Decimal("0")
    risk: Decimal = Decimal("0")
    margin: Decimal = Decimal("0")
    notional: Decimal = Decimal("0")
    directional_volume_held: Decimal = Decimal("0")

    @property
    def allowed(self) -> bool:
        return self.action == "TRADE"


def _number(value: object, label: str, *, positive: bool = False) -> Decimal:
    try:
        number = dec(value)
    except ValueError:
        raise ValueError("INVALID_OR_UNKNOWN_" + label) from None
    if number < 0 or (positive and number == 0):
        raise ValueError("INVALID_" + label)
    return number


def _precision(values) -> int:
    return max(64, 32 + sum(len(v.as_tuple().digits) + abs(v.as_tuple().exponent)
                            for v in values))


def _floor_ratio(numerator: Decimal, denominator: Decimal) -> int:
    n, d = numerator.as_integer_ratio()
    p, q = denominator.as_integer_ratio()
    return (n * q) // (d * p)


def _rules(rules: VolumeRules):
    if not isinstance(rules, VolumeRules):
        raise ValueError("INVALID_VOLUME_RULES")
    values = tuple(_number(getattr(rules, name), name.upper(), positive=True)
                   for name in ("minimum", "step", "maximum", "volume_limit"))
    if values[0] > values[2]:
        raise ValueError("MINIMUM_EXCEEDS_MAXIMUM")
    return values


def floor_volume(cap: object, rules: VolumeRules) -> Decimal:
    """Largest permitted k*step <= cap; zero means below minimum.

    volume_limit is an aggregate directional cap, applied by size_trade after
    subtracting held amounts. This helper only applies per-order min/max/step.
    """
    minimum, step, maximum, _ = _rules(rules)
    ceiling = min(_number(cap, "VOLUME_CAP"), maximum)
    with localcontext() as ctx:
        ctx.prec = _precision((minimum, step, maximum, ceiling))
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        result = Decimal(_floor_ratio(ceiling, step)) * step
        return result if result >= minimum else Decimal("0")


def _held_volume(request: RiskRequest) -> Decimal:
    if not isinstance(request.exposures, tuple):
        raise ValueError("EXPOSURES_MUST_BE_IMMUTABLE_TUPLE")
    seen = {}
    included = []
    for row in request.exposures:
        if not isinstance(row, ExposureAmount):
            raise ValueError("INVALID_EXPOSURE")
        if not all(isinstance(v, str) and v.strip() for v in
                   (row.account_id, row.symbol, row.reference_id)):
            raise ValueError("INVALID_EXPOSURE_IDENTITY")
        if row.side not in ("BUY", "SELL", "UNKNOWN"):
            raise ValueError("INVALID_EXPOSURE_SIDE")
        if row.kind not in ("POSITION", "PENDING", "UNKNOWN"):
            raise ValueError("INVALID_EXPOSURE_KIND")
        amount = _number(row.volume, "EXPOSURE_VOLUME")
        key = (row.account_id, row.symbol, row.kind, row.reference_id)
        payload = (row.side, amount)
        if key in seen:
            if seen[key] != payload:
                raise ValueError("CONFLICTING_DUPLICATE_EXPOSURE")
            continue
        seen[key] = payload
        if (row.account_id == request.account_id and row.symbol == request.symbol
                and row.side in (request.side, "UNKNOWN")):
            included.append(amount)
    with localcontext() as ctx:
        ctx.prec = _precision(included)
        ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
        return sum(included, Decimal("0"))


def size_trade(request: RiskRequest) -> RiskDecision:
    """Floor a risk-sized candidate, then veto every breached aggregate cap.

    available_margin is net of confirmed-open margin, but before local unfilled
    commitments; only those unresolved reserves are additionally deducted. This
    must not be mapped blindly from generic broker free margin. held_risk and
    held_notional exclude their
    separately supplied held_unknown_* amounts. All monetary values must use
    the same explicit synthetic currency. No currency conversion is attempted.
    """
    try:
        if not isinstance(request, RiskRequest):
            raise ValueError("INVALID_RISK_REQUEST")
        if not all(isinstance(v, str) and v.strip()
                   for v in (request.account_id, request.symbol)):
            raise ValueError("INVALID_ACCOUNT_OR_SYMBOL")
        if request.side not in ("BUY", "SELL"):
            raise ValueError("INVALID_SIDE")
        minimum, step, maximum, volume_limit = _rules(request.rules)
        if not isinstance(request.model, LinearRiskModel):
            raise ValueError("INVALID_LINEAR_MODEL")
        model_fields = ("contract_size", "entry_cost_per_lot", "exit_cost_per_lot",
                        "slippage_reserve_per_lot", "gap_reserve_per_lot", "margin_per_lot")
        contract, entry_cost, exit_cost, slip, gap, margin_per_lot = (
            _number(getattr(request.model, name), name.upper(),
                    positive=name in ("contract_size", "margin_per_lot"))
            for name in model_fields)
        entry = _number(request.entry, "ENTRY", positive=True)
        stop = _number(request.stop, "STOP", positive=True)
        if not ((request.side == "BUY" and stop < entry)
                or (request.side == "SELL" and stop > entry)):
            raise ValueError("STOP_NOT_ADVERSE")
        fields = ("risk_budget", "available_margin", "notional_cap", "portfolio_risk_cap",
                  "held_risk", "held_unknown_risk", "held_notional",
                  "held_unknown_notional", "held_unknown_margin")
        (budget, free_margin, notional_cap, portfolio_cap, held_risk, unknown_risk,
         held_notional, unknown_notional, unknown_margin) = values = tuple(
            _number(getattr(request, name), name.upper()) for name in fields)
        held_volume = _held_volume(request)
        with localcontext() as ctx:
            ctx.prec = _precision(values + (minimum, step, maximum, volume_limit, contract,
                                           entry_cost, exit_cost, slip, gap, margin_per_lot,
                                           entry, stop, held_volume))
            ctx.Emax, ctx.Emin = MAX_EMAX, MIN_EMIN
            loss_per_lot = abs(entry - stop) * contract + entry_cost + exit_cost + slip + gap
            if loss_per_lot <= 0:
                raise ValueError("NONPOSITIVE_RISK_PER_LOT")
            remaining_volume = volume_limit - held_volume
            if remaining_volume <= 0:
                return RiskDecision("NO_TRADE", ("DIRECTIONAL_VOLUME_LIMIT",),
                                    risk_per_lot=loss_per_lot,
                                    directional_volume_held=held_volume)
            risk_units = _floor_ratio(budget, loss_per_lot * step)
            cap_units = _floor_ratio(min(maximum, remaining_volume), step)
            candidate = Decimal(min(risk_units, cap_units)) * step
            if candidate < minimum or candidate == 0:
                return RiskDecision("NO_TRADE", ("BELOW_MINIMUM_VOLUME",),
                                    risk_per_lot=loss_per_lot,
                                    directional_volume_held=held_volume)
            risk = candidate * loss_per_lot
            margin = candidate * margin_per_lot
            notional = candidate * entry * contract
            reasons = []
            if risk > budget:
                reasons.append("RISK_BUDGET")
            if margin + unknown_margin > free_margin:
                reasons.append("MARGIN_CAP")
            if notional + held_notional + unknown_notional > notional_cap:
                reasons.append("NOTIONAL_CAP")
            if risk + held_risk + unknown_risk > portfolio_cap:
                reasons.append("PORTFOLIO_RISK_CAP")
            if candidate + held_volume > volume_limit:
                reasons.append("DIRECTIONAL_VOLUME_LIMIT")
            if reasons:
                return RiskDecision("NO_TRADE", tuple(reasons), risk_per_lot=loss_per_lot,
                                    directional_volume_held=held_volume)
            return RiskDecision("TRADE", (), candidate, loss_per_lot, risk,
                                margin, notional, held_volume)
    except (ValueError, ArithmeticError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else "DECIMAL_ARITHMETIC_FAILURE"
        return RiskDecision("NO_TRADE", (reason,))
