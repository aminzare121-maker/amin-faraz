"""Recomputable entry authorization for the offline synthetic executor.

These frozen inputs are logical evidence inside one Python process. They are not
a signature, authenticated market data, or broker attestation. The executor must
pin a policy separately and supply an explicit current-time recheck before each
synthetic request. No hash or caller-supplied Decision is trusted as authority.
"""
from dataclasses import dataclass, fields, replace
from decimal import Decimal

from .decision import EntryContext, decide_entry
from .numbers import dec, natural
from .risk import ExposureAmount, LinearRiskModel, RiskRequest, VolumeRules
from .temporal import Quote


DECISION_VERSION = "faraz-entry-v1"
_CONTEXT_NUMERIC_RULES = (
    "price_tick", "minimum_stop_distance", "max_spread",
    "daily_loss_limit", "total_loss_limit",
)
_CONTEXT_INTEGER_RULES = ("max_age_ms", "max_positions_and_pending")
_CONTEXT_TEXT_RULES = ("currency", "position_mode")
_IDENTITY_FIELDS = (
    "account_key", "bound_account_key", "account_revision",
    "bound_account_revision", "account_mode", "currency", "position_mode",
    "signal_id", "signal_side", "policy_hash", "quote_symbol",
    "risk_account_revision",
)
_OBSERVATION_FIELDS = (
    "account_observed_ms", "session_available_ms", "news_available_ms",
    "signal_available_ms", "risk_observed_ms",
)
_INPUT_DATACLASSES = (
    EntryContext, RiskRequest, VolumeRules, LinearRiskModel, ExposureAmount, Quote,
)


def _immutable_input(value):
    """Reject mutable payloads hidden in the input contracts' object fields."""
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is Decimal:
        dec(value)
        return
    if type(value) is tuple:
        for item in value:
            _immutable_input(item)
        return
    if type(value) in _INPUT_DATACLASSES:
        for field in fields(value):
            _immutable_input(getattr(value, field.name))
        return
    raise ValueError("IMMUTABLE_AUTHORIZATION_INPUT_REQUIRED")


@dataclass(frozen=True)
class EntryAuthorization:
    context: EntryContext
    request: RiskRequest
    expires_ms: int
    decision_version: str = DECISION_VERSION

    def __post_init__(self):
        if type(self.context) is not EntryContext or type(self.request) is not RiskRequest:
            raise ValueError("INVALID_AUTHORIZATION_CONTRACT")
        _immutable_input(self.context)
        _immutable_input(self.request)
        natural(self.expires_ms)
        natural(self.context.decision_ms)
        if self.expires_ms < self.context.decision_ms:
            raise ValueError("AUTHORIZATION_ALREADY_EXPIRED")
        if not isinstance(self.decision_version, str) or not self.decision_version:
            raise ValueError("DECISION_VERSION_REQUIRED")


@dataclass(frozen=True)
class PolicyPin:
    policy_hash: str
    context_rules: tuple
    volume_rules: tuple
    model_rules: tuple
    risk_budget: Decimal
    notional_cap: Decimal
    portfolio_risk_cap: Decimal
    decision_version: str = DECISION_VERSION

    def __post_init__(self):
        if not isinstance(self.policy_hash, str) or not self.policy_hash.strip():
            raise ValueError("POLICY_HASH_REQUIRED")
        for value in (self.context_rules, self.volume_rules, self.model_rules):
            if type(value) is not tuple:
                raise ValueError("IMMUTABLE_POLICY_PIN_REQUIRED")
            _immutable_input(value)
        for name in ("risk_budget", "notional_cap", "portfolio_risk_cap"):
            value = dec(getattr(self, name))
            if value < 0:
                raise ValueError("NONNEGATIVE_POLICY_CAP_REQUIRED")
            object.__setattr__(self, name, value)
        if self.decision_version != DECISION_VERSION:
            raise ValueError("UNSUPPORTED_DECISION_VERSION")


def pin_policy(context, request):
    """Capture policy contents, including rules hidden behind policy_hash."""
    if type(context) is not EntryContext or type(request) is not RiskRequest:
        raise ValueError("INVALID_AUTHORIZATION_CONTRACT")
    _immutable_input(context)
    _immutable_input(request)
    if type(request.rules) is not VolumeRules or type(request.model) is not LinearRiskModel:
        raise ValueError("INVALID_POLICY_RULE_CONTRACT")
    numeric = tuple((name, dec(getattr(context, name))) for name in _CONTEXT_NUMERIC_RULES)
    integer = tuple((name, natural(getattr(context, name))) for name in _CONTEXT_INTEGER_RULES)
    text = tuple((name, getattr(context, name)) for name in _CONTEXT_TEXT_RULES)
    return PolicyPin(
        context.policy_hash, numeric + integer + text,
        tuple((field.name, dec(getattr(request.rules, field.name)))
              for field in fields(request.rules)),
        tuple((field.name, dec(getattr(request.model, field.name)))
              for field in fields(request.model)),
        dec(request.risk_budget), dec(request.notional_cap), dec(request.portfolio_risk_cap),
    )


def _proposal(context, request, label):
    decision = decide_entry(context, request)
    if (decision.action != "ENTRY_PROPOSAL" or decision.risk is None
            or not decision.risk.allowed or not decision.client_intent_id
            or not decision.payload_hash):
        raise ValueError(label + ":" + ",".join(decision.reasons))
    return decision


def validate_authorization(authorization, pin, now_ms=None):
    """Recompute the original decision and, optionally, its current freshness.

    The returned decision always hashes the original immutable inputs. A later
    current-time check is a veto only, so it cannot silently replace the intent.
    """
    if type(authorization) is not EntryAuthorization or type(pin) is not PolicyPin:
        raise ValueError("VALIDATED_AUTHORIZATION_REQUIRED")
    if authorization.decision_version != DECISION_VERSION:
        raise ValueError("UNSUPPORTED_DECISION_VERSION")
    if pin_policy(authorization.context, authorization.request) != pin:
        raise ValueError("PINNED_POLICY_MISMATCH")
    original = _proposal(authorization.context, authorization.request, "AUTHORIZATION_NO_TRADE")
    if now_ms is not None:
        now_ms = natural(now_ms)
        if now_ms < authorization.context.decision_ms:
            raise ValueError("AUTHORIZATION_FROM_FUTURE")
        if now_ms > authorization.expires_ms:
            raise ValueError("AUTHORIZATION_EXPIRED")
        _proposal(replace(authorization.context, decision_ms=now_ms), authorization.request,
                  "AUTHORIZATION_RECHECK_NO_TRADE")
    return original


def authorize_entry(context, request, expires_ms):
    """Create logical authorization only after recomputing an allowed proposal."""
    authorization = EntryAuthorization(context, request, expires_ms)
    validate_authorization(authorization, pin_policy(context, request), context.decision_ms)
    return authorization


def validate_fresh_authorization(original, fresh, pin, now_ms):
    """Recheck refreshed observations without changing an authorized intent.

    Time, observations, counters and held exposure may advance. Policy contents,
    account and signal identity, executable entry, stop and resulting order size
    must stay bound. The execution ledger independently checks held exposure and
    realized-loss lower bounds; these supplied snapshots are not authenticated.
    """
    now_ms = natural(now_ms)
    original_decision = validate_authorization(original, pin)
    if now_ms < original.context.decision_ms:
        raise ValueError("AUTHORIZATION_FROM_FUTURE")
    if now_ms > original.expires_ms:
        raise ValueError("AUTHORIZATION_EXPIRED")
    if type(fresh) is not EntryAuthorization or fresh.context.decision_ms != now_ms:
        raise ValueError("CURRENT_FRESH_AUTHORIZATION_REQUIRED")
    fresh_decision = validate_authorization(fresh, pin, now_ms)
    if any(getattr(original.context, field) != getattr(fresh.context, field)
           for field in _IDENTITY_FIELDS):
        raise ValueError("FRESH_AUTHORIZATION_IDENTITY_CHANGED")
    if any(getattr(fresh.context, field) < getattr(original.context, field)
           for field in _OBSERVATION_FIELDS):
        raise ValueError("FRESH_OBSERVATION_REGRESSION")
    if (fresh.context.quote.event_ms < original.context.quote.event_ms
            or fresh.context.quote.available_ms < original.context.quote.available_ms):
        raise ValueError("FRESH_QUOTE_REGRESSION")
    if (dec(fresh.context.daily_loss) < dec(original.context.daily_loss)
            or dec(fresh.context.total_loss) < dec(original.context.total_loss)):
        raise ValueError("FRESH_LOSS_COUNTER_REGRESSION")
    if any(getattr(original.request, name) != getattr(fresh.request, name)
           for name in ("account_id", "symbol", "side")):
        raise ValueError("FRESH_AUTHORIZATION_INTENT_CHANGED")
    if any(dec(getattr(original.request, name)) != dec(getattr(fresh.request, name))
           for name in ("entry", "stop")):
        raise ValueError("FRESH_AUTHORIZATION_INTENT_CHANGED")
    if (original_decision.client_intent_id != fresh_decision.client_intent_id
            or any(getattr(original_decision.risk, name) != getattr(fresh_decision.risk, name)
                   for name in ("volume", "risk_per_lot", "risk", "margin", "notional"))):
        raise ValueError("FRESH_AUTHORIZATION_INTENT_CHANGED")
    return fresh_decision
