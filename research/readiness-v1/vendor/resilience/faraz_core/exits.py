"""Three synthetic exit rules, pure state transitions, and quote-trace replay.

This is an offline linear valuation model, not a broker or profit guarantee.
Proposed, acknowledged, and observed stops are separate facts.  Only executable
Bid (buy exit) / Ask (sell exit) observations can update a position's peak.
"""
from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Iterable

from .numbers import dec, natural
from .temporal import Candle, Quote, atr_wilder, fixed_decimal, validate_quote


CANDIDATES = ("A", "B", "C")


@dataclass(frozen=True)
class Position:
    side: str
    entry_price: Decimal
    units: Decimal
    initial_stop: Decimal
    initial_risk_cash: Decimal
    remaining_cost: Decimal | None
    unit_value: Decimal = Decimal(1)
    revision: int = 0

    def __post_init__(self):
        if self.side not in ("buy", "sell"):
            raise ValueError("SIDE_MUST_BE_BUY_OR_SELL")
        for name in ("entry_price", "units", "initial_stop", "initial_risk_cash", "unit_value"):
            object.__setattr__(self, name, dec(getattr(self, name)))
        if self.remaining_cost is not None:
            object.__setattr__(self, "remaining_cost", dec(self.remaining_cost))
            if self.remaining_cost < 0:
                raise ValueError("NEGATIVE_REMAINING_COST")
        if min(self.entry_price, self.units, self.initial_stop,
               self.initial_risk_cash, self.unit_value) <= 0:
            raise ValueError("POSITIVE_POSITION_VALUES_REQUIRED")
        if ((self.side == "buy" and self.initial_stop >= self.entry_price)
                or (self.side == "sell" and self.initial_stop <= self.entry_price)):
            raise ValueError("INITIAL_STOP_MUST_DEFINE_LOSS_SIDE")
        natural(self.revision)

    @property
    @fixed_decimal
    def cash_per_price(self) -> Decimal:
        return self.units * self.unit_value

    @property
    @fixed_decimal
    def price_risk(self) -> Decimal:
        return abs(self.entry_price - self.initial_stop)

    @fixed_decimal
    def estimated_net(self, exit_price: Decimal) -> Decimal | None:
        if self.remaining_cost is None:
            return None
        direction = Decimal(1) if self.side == "buy" else Decimal(-1)
        return direction * (dec(exit_price) - self.entry_price) * self.cash_per_price - self.remaining_cost


@dataclass(frozen=True)
class MarketRules:
    tick_size: Decimal = Decimal("0.01")
    min_stop_distance: Decimal = Decimal(0)
    freeze_distance: Decimal = Decimal(0)
    max_quote_age_ms: int = 1000

    def __post_init__(self):
        for name in ("tick_size", "min_stop_distance", "freeze_distance"):
            object.__setattr__(self, name, dec(getattr(self, name)))
        if self.tick_size <= 0 or min(self.min_stop_distance, self.freeze_distance) < 0:
            raise ValueError("INVALID_MARKET_RULES")
        natural(self.max_quote_age_ms)


@dataclass(frozen=True)
class ExitState:
    peak_price: Decimal | None = None
    peak_net_cash: Decimal | None = None
    basis_revision: int | None = None
    proposed_stop: Decimal | None = None
    acknowledged_stop: Decimal | None = None
    observed_stop: Decimal | None = None
    desired_floor_cash: Decimal | None = None
    floor_revision: int | None = None
    last_quote_event_ms: int | None = None
    last_decision_ms: int | None = None
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)
    broker_protection_confirmed: bool = field(default=False, init=False)

    def __post_init__(self):
        for name in ("peak_price", "peak_net_cash", "proposed_stop", "acknowledged_stop",
                     "observed_stop", "desired_floor_cash"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, dec(getattr(self, name)))
        for name in ("basis_revision", "floor_revision", "last_quote_event_ms", "last_decision_ms"):
            if getattr(self, name) is not None:
                natural(getattr(self, name))
        for name in ("peak_price", "proposed_stop", "acknowledged_stop", "observed_stop"):
            if getattr(self, name) is not None and getattr(self, name) <= 0:
                raise ValueError("POSITIVE_STOP_OR_PEAK_REQUIRED")


@dataclass(frozen=True)
class ExitDecision:
    candidate: str
    action: str
    reason: str
    state: ExitState
    target_stop: Decimal | None = None
    fixed_take_profit: Decimal | None = None
    estimated_current_net: Decimal | None = None
    estimated_stop_net: Decimal | None = None
    desired_floor_cash: Decimal | None = None
    floor_status: str = "NO_GUARANTEE"
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)
    broker_protection_confirmed: bool = field(default=False, init=False)


def _stronger(side: str, left: Decimal, right: Decimal) -> bool:
    return left > right if side == "buy" else left < right


def _proposal_constraint_stop(position: Position, state: ExitState) -> Decimal | None:
    """Strongest supplied ack/observation constrains proposals; no server attestation."""
    stops = [value for value in (state.acknowledged_stop, state.observed_stop) if value is not None]
    if not stops:
        return None
    return max(stops) if position.side == "buy" else min(stops)


def _tick_stop(position: Position, price: Decimal, rules: MarketRules) -> Decimal:
    # Round toward greater protection so the computed net floor is not rounded away.
    rounding = ROUND_CEILING if position.side == "buy" else ROUND_FLOOR
    return (price / rules.tick_size).to_integral_value(rounding=rounding) * rules.tick_size


@fixed_decimal
def stop_veto(position: Position, state: ExitState, stop: Decimal,
              quote: Quote, rules: MarketRules) -> str | None:
    stop = dec(stop)
    if stop <= 0 or stop % rules.tick_size != 0:
        return "INVALID_STOP_TICK"
    price = quote.exit_price(position.side)
    distance = price - stop if position.side == "buy" else stop - price
    if distance <= 0:
        return "STOP_NOT_BEHIND_EXECUTABLE_PRICE"
    if distance < rules.min_stop_distance:
        return "MIN_STOP_DISTANCE"
    if distance < rules.freeze_distance:
        return "FREEZE_DISTANCE"
    accepted = _proposal_constraint_stop(position, state)
    if accepted is not None:
        existing_distance = price - accepted if position.side == "buy" else accepted - price
        if rules.freeze_distance > 0 and 0 <= existing_distance < rules.freeze_distance:
            return "EXISTING_STOP_FROZEN"
        if not _stronger(position.side, stop, accepted):
            return "NO_STRONGER_STOP"
    return None


def _rebase(state: ExitState, revision: int) -> ExitState:
    if state.basis_revision == revision:
        return state
    return replace(state, peak_price=None, peak_net_cash=None, basis_revision=revision,
                   proposed_stop=None, desired_floor_cash=None, floor_revision=None)


def _state_clock_veto(state: ExitState, quote: Quote, decision_ms: int) -> str | None:
    if state.last_decision_ms is not None and decision_ms < state.last_decision_ms:
        return "DECISION_CLOCK_REGRESSION"
    if state.last_quote_event_ms is not None and quote.event_ms < state.last_quote_event_ms:
        return "OUT_OF_ORDER_QUOTE"
    return None


def _update_peak(position: Position, state: ExitState, quote: Quote,
                 decision_ms: int | None = None) -> ExitState:
    state = _rebase(state, position.revision)
    price = quote.exit_price(position.side)
    peak = state.peak_price
    if peak is None or _stronger(position.side, price, peak):
        peak = price
    return replace(state, peak_price=peak, peak_net_cash=position.estimated_net(peak),
                   last_quote_event_ms=quote.event_ms,
                   last_decision_ms=quote.available_ms if decision_ms is None else decision_ms)


def revise_position(position: Position, state: ExitState, **changes) -> tuple[Position, ExitState]:
    """Cost/entry/volume revisions start a fresh peak/floor basis, retaining stops.

    Call this for every valuation change. A forgotten revision increment is also
    made impossible here. Directly constructed Position revisions are supported
    by evaluate_exit's revision check.
    """
    if "revision" in changes:
        raise ValueError("REVISION_IS_MANAGED")
    revised = replace(position, **changes, revision=position.revision + 1)
    return revised, _rebase(state, revised.revision)


def acknowledge_stop(position: Position, state: ExitState, stop: Decimal) -> ExitState:
    """Record a supplied synthetic acknowledgment, never verified broker protection."""
    stop = dec(stop)
    if state.proposed_stop is None or stop != state.proposed_stop:
        raise ValueError("ACK_MUST_MATCH_PROPOSAL")
    accepted = _proposal_constraint_stop(position, state)
    if accepted is not None and stop != accepted and not _stronger(position.side, stop, accepted):
        raise ValueError("ACK_WOULD_WEAKEN_STOP")
    return replace(state, acknowledged_stop=stop)


def observe_stop(position: Position, state: ExitState, stop: Decimal) -> ExitState:
    """Record a supplied offline observation, without asserting real server state."""
    stop = dec(stop)
    accepted = _proposal_constraint_stop(position, state)
    if accepted is not None and stop != accepted and not _stronger(position.side, stop, accepted):
        raise ValueError("OBSERVATION_WOULD_WEAKEN_STOP")
    return replace(state, observed_stop=stop)


@fixed_decimal
def evaluate_exit(candidate: str, position: Position, state: ExitState,
                  quote: Quote | None, decision_ms: int,
                  rules: MarketRules = MarketRules(),
                  candles: Iterable[Candle] = ()) -> ExitDecision:
    """A: fixed initial SL + 2 price-R TP; B: 1R then 1.5 ATR14 trail;
    C: peak estimated net >= .5 cash-R, then request .5 peak net floor.

    B and C have no fixed TP. A floor is a target under synthetic valuation,
    never a guarantee: rejection, later cost changes, latency, and gaps matter.
    """
    if candidate not in CANDIDATES:
        raise ValueError("UNKNOWN_EXIT_CANDIDATE")
    natural(decision_ms)
    state = _rebase(state, position.revision)
    direction = Decimal(1) if position.side == "buy" else Decimal(-1)
    take_profit = (position.entry_price + direction * 2 * position.price_risk
                   if candidate == "A" else None)
    veto = validate_quote(quote, decision_ms, rules.max_quote_age_ms)
    if veto is not None:
        return ExitDecision(candidate, "HOLD", veto, state, fixed_take_profit=take_profit)
    veto = _state_clock_veto(state, quote, decision_ms)
    if veto is not None:
        return ExitDecision(candidate, "HOLD", veto, state, fixed_take_profit=take_profit)
    if position.remaining_cost is None:
        return ExitDecision(candidate, "HOLD", "UNKNOWN_REMAINING_COST", state,
                            fixed_take_profit=take_profit)
    state = _update_peak(position, state, quote, decision_ms)
    current_net = position.estimated_net(quote.exit_price(position.side))
    target = position.initial_stop
    reason = "INITIAL_STOP"
    desired = None
    if candidate == "B":
        favorable_move = direction * (state.peak_price - position.entry_price)
        if favorable_move >= position.price_risk:
            atr = atr_wilder(candles, decision_ms, 14)
            if not atr.ready:
                return ExitDecision(candidate, "HOLD", atr.reason, state,
                                    estimated_current_net=current_net)
            trail = state.peak_price - direction * Decimal("1.5") * atr.value
            target = max(target, trail) if position.side == "buy" else min(target, trail)
            reason = "ATR14_TRAIL"
    elif candidate == "C" and state.peak_net_cash >= Decimal("0.5") * position.initial_risk_cash:
        desired = Decimal("0.5") * state.peak_net_cash
        solved = position.entry_price + direction * (desired + position.remaining_cost) / position.cash_per_price
        target = max(target, solved) if position.side == "buy" else min(target, solved)
        state = replace(state, desired_floor_cash=desired, floor_revision=position.revision)
        reason = "HALF_PEAK_NET_FLOOR"
    target = _tick_stop(position, target, rules)
    veto = stop_veto(position, state, target, quote, rules)
    if veto is not None:
        return ExitDecision(candidate, "HOLD", veto, state, target_stop=target,
                            fixed_take_profit=take_profit, estimated_current_net=current_net,
                            estimated_stop_net=position.estimated_net(target), desired_floor_cash=desired)
    state = replace(state, proposed_stop=target)
    return ExitDecision(candidate, "PROPOSE_STOP", reason, state, target, take_profit,
                        current_net, position.estimated_net(target), desired,
                        "PROPOSED_ESTIMATE_ONLY" if desired is not None else "NO_GUARANTEE")


@dataclass(frozen=True)
class OHLCAssessment:
    label: str
    conservative_scenario: str | None
    scenario_exit_price: Decimal | None
    scenario_net_cash: Decimal | None
    actual_fill_price: Decimal | None = None


@fixed_decimal
def assess_ohlc_touch(position: Position, candle: Candle, stop: Decimal | None,
                      take_profit: Decimal | None, decision_ms: int) -> OHLCAssessment:
    """OHLC cannot supply executable fill/order evidence, including a double touch."""
    if not candle.available_at(decision_ms):
        return OHLCAssessment("UNAVAILABLE_CANDLE", None, None, None)
    stop = None if stop is None else dec(stop)
    take_profit = None if take_profit is None else dec(take_profit)
    if position.side == "buy":
        touched_stop = stop is not None and candle.low <= stop
        touched_tp = take_profit is not None and candle.high >= take_profit
    else:
        touched_stop = stop is not None and candle.high >= stop
        touched_tp = take_profit is not None and candle.low <= take_profit
    if touched_stop and touched_tp:
        # The stop-first scenario includes an adverse opening gap. It remains a
        # conditional OHLC scenario: spreads/slippage/sequence are not known.
        scenario_price = min(stop, candle.open) if position.side == "buy" else max(stop, candle.open)
        return OHLCAssessment("AMBIGUOUS_DOUBLE_TOUCH",
                              "CONSERVATIVE_STOP_FIRST_SCENARIO_NOT_ACTUAL_FILL",
                              scenario_price, position.estimated_net(scenario_price))
    return OHLCAssessment("OHLC_TOUCH_NOT_EXECUTABLE_FILL" if touched_stop or touched_tp else "NO_TOUCH",
                          None, None, None)


@dataclass(frozen=True)
class ReplayEvent:
    time_ms: int
    kind: str
    detail: str
    price: Decimal | None = None


@dataclass(frozen=True)
class ReplayResult:
    candidate: str
    status: str
    exit_reason: str
    deadline_ms: int
    request_ms: int | None
    fill_ms: int | None
    fill_price: Decimal | None
    estimated_net_cash: Decimal | None
    state: ExitState
    events: tuple[ReplayEvent, ...]
    synthetic: bool = field(default=True, init=False)
    evidence_source: str = field(default="OFFLINE_SYNTHETIC", init=False)
    broker_protection_confirmed: bool = field(default=False, init=False)


@fixed_decimal
def replay_candidate(candidate: str, position: Position, quotes: Iterable[Quote],
                     initial_fill_ms: int, rules: MarketRules = MarketRules(),
                     candles: Iterable[Candle] = (), horizon_ms: int = 3_600_000,
                     latency_ms: int = 100) -> ReplayResult:
    """Replay a supplied trace with a fixed synthetic position and explicit latency.

    Requests fill at the first later executable supplied quote after latency;
    no interpolation or stop-price fill is invented. At the deadline an exit is
    requested even if no quote exists; insufficient later trace stays PENDING_EXIT.
    Initial SL is explicitly assumed installed in this *synthetic* replay only.
    """
    if candidate not in CANDIDATES:
        raise ValueError("UNKNOWN_EXIT_CANDIDATE")
    natural(initial_fill_ms)
    natural(horizon_ms)
    natural(latency_ms)
    if horizon_ms == 0:
        raise ValueError("POSITIVE_HORIZON_REQUIRED")
    deadline = initial_fill_ms + horizon_ms
    state = ExitState(basis_revision=position.revision,
                      acknowledged_stop=position.initial_stop,
                      observed_stop=position.initial_stop)
    events = [ReplayEvent(initial_fill_ms, "SYNTHETIC_ASSUMPTION", "INITIAL_STOP_OBSERVED_AT_FILL", position.initial_stop)]
    pending_stop = None
    stop_observed_ms = initial_fill_ms
    exit_request = None
    exit_reason = "HORIZON"
    candles = tuple(candles)
    # Candle diagnostics do not execute orders and never supply peak prices.
    timeline = [(q.available_ms, 1, q.event_ms, q) for q in quotes]
    timeline.extend((bar.available_ms, 0, bar.close_ms, bar) for bar in candles
                    if bar.open_ms >= initial_fill_ms and bar.available_at(bar.available_ms))
    timeline.sort(key=lambda event: event[:3])
    tp = (position.entry_price + (1 if position.side == "buy" else -1) * 2 * position.price_risk
          if candidate == "A" else None)
    last_event_ms = None
    last_time = initial_fill_ms
    for now, _, _, observation in timeline:
        last_time = max(last_time, now)
        if now < initial_fill_ms:
            continue
        if exit_request is None and now >= deadline:
            exit_request = deadline
            exit_reason = "HORIZON"
            events.append(ReplayEvent(deadline, "EXIT_REQUEST", "HORIZON"))
        if isinstance(observation, Candle):
            if stop_observed_ms <= observation.open_ms:
                assessment = assess_ohlc_touch(position, observation, state.observed_stop, tp, now)
                if assessment.label == "AMBIGUOUS_DOUBLE_TOUCH":
                    events.append(ReplayEvent(now, "AMBIGUOUS_OHLC", assessment.label))
                    events.append(ReplayEvent(now, "CONSERVATIVE_SCENARIO", assessment.conservative_scenario,
                                              assessment.scenario_exit_price))
            continue
        quote = observation
        if quote.event_ms < initial_fill_ms:
            continue
        veto = validate_quote(quote, now, rules.max_quote_age_ms)
        if veto is None and last_event_ms is not None and quote.event_ms < last_event_ms:
            veto = "OUT_OF_ORDER_QUOTE"
        if veto is not None:
            events.append(ReplayEvent(now, "QUOTE_VETO", veto))
            continue
        last_event_ms = quote.event_ms
        price = quote.exit_price(position.side)
        if exit_request is not None:
            if now >= exit_request + latency_ms and quote.event_ms >= exit_request + latency_ms:
                events.append(ReplayEvent(now, "SYNTHETIC_FILL", exit_reason, price))
                return ReplayResult(candidate, "CLOSED", exit_reason, deadline, exit_request, now,
                                    price, position.estimated_net(price), state, tuple(events))
            continue
        if pending_stop is not None:
            requested_ms, pending_price = pending_stop
            if now >= requested_ms + latency_ms and quote.event_ms >= requested_ms + latency_ms:
                veto = stop_veto(position, state, pending_price, quote, rules)
                if veto is None:
                    state = replace(state, proposed_stop=pending_price)
                    state = acknowledge_stop(position, state, pending_price)
                    events.append(ReplayEvent(now, "SYNTHETIC_STOP_ACK", "ACCEPTED", pending_price))
                    state = observe_stop(position, state, pending_price)
                    stop_observed_ms = now
                    events.append(ReplayEvent(now, "SYNTHETIC_STOP_OBSERVED", "OBSERVED", pending_price))
                else:
                    events.append(ReplayEvent(now, "SYNTHETIC_STOP_REJECTED", veto, pending_price))
                pending_stop = None
        stop = state.observed_stop
        stop_hit = stop is not None and (price <= stop if position.side == "buy" else price >= stop)
        tp_hit = tp is not None and (price >= tp if position.side == "buy" else price <= tp)
        if stop_hit or tp_hit:
            exit_request = now
            exit_reason = "STOP" if stop_hit else "FIXED_TP"
            events.append(ReplayEvent(now, "EXIT_REQUEST", exit_reason, price))
            # A zero-latency trace still uses a genuinely supplied current quote.
            if latency_ms == 0:
                events.append(ReplayEvent(now, "SYNTHETIC_FILL", exit_reason, price))
                return ReplayResult(candidate, "CLOSED", exit_reason, deadline, exit_request, now,
                                    price, position.estimated_net(price), state, tuple(events))
            continue
        if pending_stop is not None:
            state = _update_peak(position, state, quote)
            continue
        decision = evaluate_exit(candidate, position, state, quote, now, rules, candles)
        state = decision.state
        if decision.action == "PROPOSE_STOP":
            pending_stop = (now, decision.target_stop)
            events.append(ReplayEvent(now, "STOP_PROPOSED", decision.reason, decision.target_stop))
    if exit_request is None:
        exit_request = deadline
        exit_reason = "HORIZON"
        events.append(ReplayEvent(deadline, "EXIT_REQUEST", "HORIZON"))
    events.append(ReplayEvent(max(last_time, exit_request + latency_ms), "PENDING_EXIT",
                              "NO_EXECUTABLE_QUOTE_AFTER_EXIT_READY"))
    return ReplayResult(candidate, "PENDING_EXIT", exit_reason, deadline, exit_request,
                        None, None, None, state, tuple(events))


@fixed_decimal
def compare_candidates(position: Position, quotes: Iterable[Quote], initial_fill_ms: int,
                       rules: MarketRules = MarketRules(), candles: Iterable[Candle] = (),
                       horizon_ms: int = 3_600_000, latency_ms: int = 100) -> tuple[ReplayResult, ...]:
    """Same entry/units/costs/exposure/trace for all rules; no performance claim."""
    trace, bars = tuple(quotes), tuple(candles)
    return tuple(replay_candidate(candidate, position, trace, initial_fill_ms, rules, bars,
                                  horizon_ms, latency_ms) for candidate in CANDIDATES)
