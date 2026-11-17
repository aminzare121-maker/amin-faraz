"""V5 OHLC execution integrity gates. No orders, no private data."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float

def fill(side, entry, stop, target, bars):
    """Conservative OHLC fill: opening gap is filled at OPEN, not the stop;
    same-bar stop/target ambiguity is resolved stop-first.
    Returns (price, reason)."""
    assert side in (-1, 1) and bars
    assert (stop < entry < target) if side == 1 else (target < entry < stop)
    for b in bars:
        assert b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high
        if side == 1:
            if b.open <= stop: return b.open, "gap_stop"
            if b.open >= target: return target, "gap_target"
            if b.low <= stop: return stop, "stop"
            if b.high >= target: return target, "target"
        else:
            if b.open >= stop: return b.open, "gap_stop"
            if b.open <= target: return target, "gap_target"
            if b.high >= stop: return stop, "stop"
            if b.low <= target: return target, "target"
    return bars[-1].close, "time"

def lots(equity, risk_fraction, stop_distance, contract_size=100, step=0.01, max_lot=0.1):
    """Never round UP to broker minimum: return zero if risk budget is insufficient."""
    import math
    if min(equity, risk_fraction, stop_distance, contract_size, step) <= 0: return 0.
    units = math.floor((equity*risk_fraction/(stop_distance*contract_size)+1e-12)/step)
    return round(min(units*step, max_lot), 8)

def validate():
    assert fill(1,100,95,110,[Bar(90,93,89,91)]) == (90,"gap_stop")
    assert fill(-1,100,105,90,[Bar(110,112,108,109)]) == (110,"gap_stop")
    assert fill(1,100,95,110,[Bar(100,112,94,102)]) == (95,"stop")
    assert fill(-1,100,105,90,[Bar(100,106,89,99)]) == (105,"stop")
    assert lots(1000,.005,10)==0.0
    assert lots(1000,.01,5)==0.02
    assert lots(1000,.01,15)==0.0
    return "7 deterministic execution/risk checks passed"

if __name__ == "__main__":
    print(validate())
