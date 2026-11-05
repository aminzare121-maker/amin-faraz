from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal


def dec(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError("Invalid decimal") from error
    if not result.is_finite():
        raise ValueError("Non-finite decimal")
    return result


def money(value) -> str:
    return str(dec(value))


@dataclass(frozen=True)
class Policy:
    # Conservative provisional DEMO limits. Owner approval required before live use.
    stage_loss_fraction: str = "0.03"
    stage_reduction: str = "0.5"
    max_daily_drawdown: str = "0.03"
    max_total_drawdown: str = "0.10"
    max_order_risk_fraction: str = "0.005"
    max_portfolio_risk_fraction: str = "0.01"
    max_notional_multiple: str = "2"
    # None: no arbitrary count cap; aggregate risk/notional/margin still veto.
    max_positions: int | None = None
    max_daily_orders: int | None = None
    max_spread: str = "0.50"
    max_slippage: str = "0.20"
    max_jump_fraction: str = "0.005"
    max_age_ms: int = 2000
    max_future_ms: int = 250
    max_roundtrip_ms: int = 750
    minimum_active: str = "25"
    daily_profit_target: str = "0.10"
    daily_profit_target_halts: bool = False
    commission_per_lot: str = "10"
    entry_context_mode: str = 'directional-confirmation'


def configured_policy(config):
    """Account-specific contract/cost envelope; loss percentages stay fixed."""
    overrides=config.get('risk_overrides',{})
    if not isinstance(overrides,dict) or set(overrides)-{'max_notional_multiple','max_spread','entry_context_mode'}:raise ValueError('Unsupported policy override')
    from dataclasses import replace
    p=replace(Policy(),**overrides)
    if p.entry_context_mode not in ('directional-confirmation','scheduled-news-v1'):raise ValueError('Invalid context mode')
    if not 0<dec(p.max_notional_multiple)<=10 or not 0<dec(p.max_spread)<=1:raise ValueError('Invalid account contract envelope')
    return p


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str = "XAUUSD"
    currency_profit: str = "USD"
    contract_size: str = "100"
    tick_size: str = "0.01"
    volume_min: str = "0.01"
    volume_max: str = "10"
    volume_step: str = "0.01"
    minimum_stop_distance: str = "0.10"
    trading_enabled: bool = True


@dataclass(frozen=True)
class Market:
    bid: str
    ask: str
    previous_mid: str
    tick_ms: int
    account_ms: int
    roundtrip_ms: int = 1
    connected: bool = True
    session_open: bool = True
    news_clear: bool = False
    raw_tick_ms: int | None = None
    clock_offset_seconds: int = 0
    clock_mapping_verified: bool = False


@dataclass(frozen=True)
class Exposure:
    # Includes ALL account positions and pending orders, not only this strategy.
    positions: int = 0
    pending_orders: int = 0
    risk_to_stops: str = "0"
    notional: str = "0"
    all_protected: bool = True


@dataclass(frozen=True)
class Account:
    identity: str
    equity: str
    free_margin: str
    mode: Literal["demo", "real", "unknown"] = "unknown"
    currency: str = "USD"


@dataclass(frozen=True)
class Intent:
    request_id: str
    symbol: str
    side: Literal["buy", "sell"]
    volume: str
    stop_loss: str
    reference_price: str
    created_ms: int
    reason: str
    evidence: tuple[str, ...]
    # Always supplied from trusted broker order_calc_* values by execution process.
    estimated_margin: str
    stop_risk: str
    take_profit: str = "0"
    max_holding_seconds: int = 0


@dataclass(frozen=True)
class Stage:
    day: str
    day_start_equity: str
    total_reference_equity: str
    stage_start_equity: str
    active_capital: str
    stage_index: int = 0
    daily_orders: int = 0
    account_identity: str = ""

    @classmethod
    def initial(cls, day: str, account: Account):
        if dec(account.equity) <= 0:
            raise ValueError("Positive equity required")
        return cls(day, account.equity, account.equity, account.equity,
                   account.equity, account_identity=account.identity)

    def as_dict(self):
        return asdict(self)
