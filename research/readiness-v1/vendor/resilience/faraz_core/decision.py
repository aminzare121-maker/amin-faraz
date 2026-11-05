"""Fresh deterministic entry boundary. Decisions are proposals, never orders."""
from dataclasses import asdict, dataclass
from decimal import Context, localcontext
import hashlib
import json

from .numbers import dec, natural
from .risk import RiskDecision, RiskRequest, size_trade
from .temporal import Quote, validate_quote


@dataclass(frozen=True)
class EntryContext:
    decision_ms: int
    account_key: str
    bound_account_key: str
    account_revision: int
    bound_account_revision: int
    account_mode: str
    currency: str
    position_mode: str
    ownership_clear: bool
    synthetic_source: bool
    connected: bool
    session_open: bool
    session_available_ms: int
    news_clear: bool
    news_available_ms: int
    clock_verified: bool
    account_observed_ms: int
    max_age_ms: int
    quote: Quote
    signal_id: str
    signal_available_ms: int
    signal_side: str | None
    policy_hash: str
    price_tick: object
    minimum_stop_distance: object
    max_spread: object
    daily_loss: object
    daily_loss_limit: object
    total_loss: object
    total_loss_limit: object
    positions_and_pending: int
    max_positions_and_pending: int
    quote_symbol: str
    risk_account_revision: int
    risk_observed_ms: int


@dataclass(frozen=True)
class Decision:
    action: str
    reasons: tuple[str, ...]
    risk: RiskDecision | None = None
    client_intent_id: str | None = None
    payload_hash: str | None = None
    can_execute: bool = False


def decide_entry(context: EntryContext, request: RiskRequest) -> Decision:
    """Fail closed independently of the signal/risk calculator, using supplied time."""
    # Bounded decimal inputs have <=128 digits and exponent magnitude <=64.
    # This context prevents ambient precision from changing veto comparisons.
    with localcontext(Context(prec=512)):
        return _decide_entry(context, request)


def _decide_entry(context: EntryContext, request: RiskRequest) -> Decision:
    try:
        if not isinstance(context, EntryContext) or not isinstance(request, RiskRequest):
            raise ValueError('INVALID_ENTRY_CONTRACT')
        now = natural(context.decision_ms)
        age = natural(context.max_age_ms)
        reasons = []
        for name in ('ownership_clear', 'synthetic_source', 'connected',
                     'session_open', 'news_clear', 'clock_verified'):
            if type(getattr(context, name)) is not bool or not getattr(context, name):
                reasons.append(name.upper() + '_REQUIRED')
        if context.account_mode != 'DEMO' or context.currency != 'USD':
            reasons.append('SYNTHETIC_USD_DEMO_ONLY')
        if (not context.account_key or context.account_key != context.bound_account_key
                or context.account_key != request.account_id
                or natural(context.account_revision) != natural(context.bound_account_revision)
                or natural(context.risk_account_revision) != context.account_revision):
            reasons.append('ACCOUNT_BINDING_CHANGED')
        if context.quote_symbol != request.symbol:
            reasons.append('QUOTE_SYMBOL_MISMATCH')
        if context.position_mode not in ('HEDGING', 'NETTING'):
            reasons.append('POSITION_MODE_UNKNOWN')
        for timestamp, name in ((context.account_observed_ms, 'ACCOUNT'),
                                (context.session_available_ms, 'SESSION'),
                                (context.news_available_ms, 'NEWS'),
                                (context.signal_available_ms, 'SIGNAL'),
                                (context.risk_observed_ms, 'RISK_SOURCE')):
            timestamp = natural(timestamp)
            if timestamp > now or now - timestamp > age:
                reasons.append(name + '_UNAVAILABLE_OR_STALE')
        quote_reason = validate_quote(context.quote, now, age)
        if quote_reason:
            reasons.append(quote_reason)
        if context.signal_side is None:
            reasons.append('NO_SIGNAL')
        elif context.signal_side not in ('BUY', 'SELL') or context.signal_side != request.side:
            reasons.append('SIGNAL_SIDE_MISMATCH')
        if not context.signal_id or not context.policy_hash:
            reasons.append('MISSING_SIGNAL_OR_POLICY_ID')
        tick = dec(context.price_tick)
        minimum = dec(context.minimum_stop_distance)
        spread_cap = dec(context.max_spread)
        if tick <= 0 or min(minimum, spread_cap) < 0:
            raise ValueError('INVALID_PRICE_RULES')
        if context.quote.ask - context.quote.bid > spread_cap:
            reasons.append('SPREAD_LIMIT')
        stop = dec(request.stop)
        expected_entry = context.quote.ask if request.side == 'BUY' else context.quote.bid
        if dec(request.entry) != expected_entry:
            reasons.append('EXECUTABLE_ENTRY_MISMATCH')
        if stop <= 0 or stop % tick:
            reasons.append('INVALID_STOP_TICK')
        distance = context.quote.bid - stop if request.side == 'BUY' else stop - context.quote.ask
        if distance <= 0 or distance < minimum:
            reasons.append('INVALID_STOP_DISTANCE')
        for used, limit, name in ((context.daily_loss, context.daily_loss_limit, 'DAILY'),
                                  (context.total_loss, context.total_loss_limit, 'TOTAL')):
            used, limit = dec(used), dec(limit)
            if used < 0 or limit <= 0:
                raise ValueError('INVALID_LOSS_LIMIT')
            if used >= limit:
                reasons.append(name + '_DRAWDOWN_LIMIT')
        if (natural(context.max_positions_and_pending) == 0
                or natural(context.positions_and_pending) >= context.max_positions_and_pending):
            reasons.append('POSITION_PENDING_LIMIT')
        if reasons:
            return Decision('NO_TRADE', tuple(dict.fromkeys(reasons)))
        risk = size_trade(request)
        if not risk.allowed:
            return Decision('NO_TRADE', risk.reasons, risk)
        held = dec(request.held_risk) + dec(request.held_unknown_risk)
        for used, limit, name in ((context.daily_loss, context.daily_loss_limit, 'DAILY'),
                                  (context.total_loss, context.total_loss_limit, 'TOTAL')):
            if dec(used) + held + risk.risk > dec(limit):
                reasons.append(name + '_LOSS_HEADROOM')
        if reasons:
            return Decision('NO_TRADE', tuple(reasons), risk)
        identity = (context.account_key, context.account_revision, request.symbol,
                    context.signal_id, context.signal_side, context.policy_hash)
        key = hashlib.sha256(json.dumps(identity, separators=(',', ':')).encode()).hexdigest()
        payload = json.dumps({'context': asdict(context), 'request': asdict(request),
                              'risk': asdict(risk)}, sort_keys=True, default=str,
                             separators=(',', ':'))
        return Decision('ENTRY_PROPOSAL', (), risk, key,
                        hashlib.sha256(payload.encode()).hexdigest())
    except (ValueError, TypeError, ArithmeticError, AttributeError) as error:
        return Decision('NO_TRADE', (str(error) or 'INVALID_INPUT',))
