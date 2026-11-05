from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Candidate:
    side: str
    stop: float
    features: list[float]
    signal_index: int


@dataclass(frozen=True)
class Scenario:
    name: str
    spread: float = 0.50
    commission: float = 10.0
    slippage: float = 0.20
    swap_per_lot: float = 0.0
    latency_bars: int = 1


@dataclass(frozen=True)
class Policy:
    name: str = "hypothetical-research-v1-not-owner-operational-policy"
    initial_capital: float = 10000.0
    risk_fraction: float = 0.0025
    daily_dd: float = 0.02
    total_dd: float = 0.08
    max_holding_seconds: int = 14400
    reward_risk: float = 2.0
    max_positions: int = 1


@dataclass(frozen=True)
class Symbol:
    name: str = "HYPOTHETICAL-XAUUSD-USD-contract100-NOT-EPPLANET-SPEC"
    contract_size: float = 100.0
    tick_size: float = 0.01
    volume_min: float = 0.01
    volume_max: float = 10.0
    volume_step: float = 0.01
