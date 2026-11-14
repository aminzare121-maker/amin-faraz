#!/usr/bin/env python3
"""Bounded GitHub replay on 997 genuine Eplanet M15 candles.

Not a replacement for the 23,643-row V3 experiment. No live orders.
The only strategy below is a frozen diagnostic momentum baseline, not an
approved trading signal. Broker contract and costs remain ASSUMPTIONS.
"""
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "Eplanet_M15_REAL_SAMPLE_997.csv"
REPORT = HERE / "bounded_ci_result.json"
EXPECTED_SHA256 = "b6e0e26e4aaf715773eec2387ff3427601e256fac12f127aec1e7e7f0058dec5"
HORIZON = 4
LOT = 0.01
CONTRACT_OZ_ASSUMED = 100
SPREAD_POINT_ASSUMED = 0.01
SLIP_PER_SIDE_OZ_ASSUMED = 0.05
COMMISSION_ROUND_TRIP_PER_LOT_ASSUMED = 7.0


def read_bars(path=DATA):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256, "SOURCE_HASH_MISMATCH"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 997, "NOT_EXPECTED_REAL_SAMPLE"
    bars = []
    for r in rows:
        x = {k: float(r[k]) for k in ("open", "high", "low", "close", "tick_volume", "spread")}
        x["time"] = int(r["time"])
        assert x["low"] <= min(x["open"], x["close"]) <= max(x["open"], x["close"]) <= x["high"]
        assert x["spread"] >= 0 and x["tick_volume"] >= 0
        bars.append(x)
    assert bars[0]["time"] == 1762340400 and bars[-1]["time"] == 1763622000
    assert all(b["time"] > a["time"] for a, b in zip(bars, bars[1:]))
    return bars


def atr_at(bars, i, lookback=20):
    if i < lookback:
        return None
    ranges = []
    for k in range(i - lookback + 1, i + 1):
        b = bars[k]
        prev_close = bars[k-1]["close"]
        ranges.append(max(b["high"]-b["low"], abs(b["high"]-prev_close), abs(b["low"]-prev_close)))
    return max(0.02, sum(ranges) / len(ranges))


def has_contiguous_future(bars, i, horizon):
    if i + horizon >= len(bars):
        return False
    return all(bars[k+1]["time"] - bars[k]["time"] == 900
               for k in range(i, i+horizon))


def frozen_signal(bars, i):
    """Uses closed bars at or before i only. Not model V3."""
    a = atr_at(bars, i)
    if a is None or i < 4:
        return "WAIT"
    displacement = bars[i]["close"] - bars[i-4]["close"]
    if displacement > 0.9 * a:
        return "BUY"
    if displacement < -0.9 * a:
        return "SELL"
    return "WAIT"


def simulate_trade(bars, i, side, horizon=HORIZON, atr_override=None):
    """Entry next bar OPEN, bid-OHLC assumption, conservative collision."""
    if not has_contiguous_future(bars, i, horizon):
        return None
    a = atr_override if atr_override is not None else atr_at(bars, i)
    if a is None or side not in ("BUY", "SELL"):
        return None
    entry_bar = bars[i+1]
    spread = entry_bar["spread"] * SPREAD_POINT_ASSUMED
    slip = SLIP_PER_SIDE_OZ_ASSUMED
    commission_per_oz = COMMISSION_ROUND_TRIP_PER_LOT_ASSUMED / CONTRACT_OZ_ASSUMED
    entry = (entry_bar["open"] + spread + slip if side == "BUY"
             else entry_bar["open"] - slip)
    stop = entry - a if side == "BUY" else entry + a
    target = entry + 2*a if side == "BUY" else entry - 2*a
    event = "TIMEOUT"
    exit_i = i + horizon
    exit_price = None
    for k in range(i+1, i+horizon+1):
        b = bars[k]
        bid_high, bid_low = b["high"], b["low"]
        ask_high = bid_high + b["spread"]*SPREAD_POINT_ASSUMED
        ask_low = bid_low + b["spread"]*SPREAD_POINT_ASSUMED
        if side == "BUY":
            hit_stop, hit_tp = bid_low <= stop, bid_high >= target
        else:
            hit_stop, hit_tp = ask_high >= stop, ask_low <= target
        if hit_stop:
            event = "STOP_COLLISION" if hit_tp else "STOP"
            exit_i = k
            exit_price = (min(stop, b["open"])-slip if side == "BUY"
                          else max(stop, b["open"]+b["spread"]*SPREAD_POINT_ASSUMED)+slip)
            break
        if hit_tp:
            event = "TARGET"
            exit_i = k
            exit_price = target-slip if side == "BUY" else target+slip
            break
    if exit_price is None:
        b = bars[exit_i]
        exit_price = b["close"]-slip if side == "BUY" else b["close"]+b["spread"]*SPREAD_POINT_ASSUMED+slip
    net_per_oz = exit_price-entry-commission_per_oz if side == "BUY" else entry-exit_price-commission_per_oz
    return {"signal_index":i, "exit_index":exit_i, "side":side, "event":event,
            "net_usd_assumed":round(net_per_oz * LOT * CONTRACT_OZ_ASSUMED, 6)}


def replay(bars):
    trades = []
    last_exit = -1
    skipped_gap = 0
    for i in range(80, len(bars)-HORIZON):
        if i <= last_exit:
            continue
        s = frozen_signal(bars, i)
        if s == "WAIT":
            continue
        t = simulate_trade(bars, i, s)
        if t is None:
            skipped_gap += 1
            continue
        trades.append(t)
        last_exit = t["exit_index"]
    net = [x["net_usd_assumed"] for x in trades]
    gains = sum(x for x in net if x > 0)
    losses = -sum(x for x in net if x < 0)
    return {"number_of_trades":len(trades), "net_usd_assumed":round(sum(net), 2),
            "profit_factor_assumed":round(gains/losses, 4) if losses else None,
            "win_rate":round(sum(x>0 for x in net)/len(net), 4) if net else None,
            "stop_collision_count":sum(t["event"]=="STOP_COLLISION" for t in trades),
            "signals_skipped_for_session_gaps":skipped_gap,
            "signals":trades}


def run_tests():
    bars = read_bars()
    assert len(bars) == 997
    assert atr_at(bars, 19) is None and atr_at(bars, 20) is not None
    old = frozen_signal(bars, 230)
    future_changed = [dict(x) for x in bars]
    for b in future_changed[231:]:
        b["open"] *= 1.3
        b["high"] *= 1.3
        b["low"] *= 1.3
        b["close"] *= 1.3
    assert frozen_signal(future_changed, 230) == old, "FUTURE_LEAK"

    collision = [
        {"time":900*k, "open":100.0, "high":110.0 if k==1 else 101.0,
         "low":90.0 if k==1 else 99.0, "close":100.0,
         "spread":0.0, "tick_volume":100.0}
        for k in range(4)
    ]
    for side in ("BUY", "SELL"):
        t = simulate_trade(collision, 0, side, horizon=2, atr_override=2.0)
        assert t["event"] == "STOP_COLLISION" and t["net_usd_assumed"] < 0, (side, t)
    gap = [dict(x) for x in collision]
    gap[2]["time"] += 3600
    gap[3]["time"] += 3600
    assert simulate_trade(gap, 0, "BUY", horizon=2, atr_override=2.0) is None
    return bars


def main():
    bars = run_tests()
    result = replay(bars)
    report = {
        "status": "TECHNICAL_SAMPLE_CI_ONLY",
        "approved_live_signal": False,
        "full_23643_candle_v3_backtest_performed_on_github": False,
        "data_origin": "first 997 rows of Eplanet_M15_20251105_20261105_merged.csv",
        "sample_sha256": EXPECTED_SHA256,
        "sample_rows": len(bars),
        "start_unix": bars[0]["time"],
        "end_unix": bars[-1]["time"],
        "baseline": "frozen 4-candle momentum diagnostic; not V3 machine-learning model",
        "strategy_rule": "ATR20 stop, 2*ATR20 target, max 4 M15 bars; no overlap",
        "costs_assumed_not_broker_verified": {
            "lot": LOT, "contract_oz": CONTRACT_OZ_ASSUMED,
            "spread_point": SPREAD_POINT_ASSUMED,
            "slippage_price_each_side": SLIP_PER_SIDE_OZ_ASSUMED,
            "commission_per_lot_round_trip_usd": COMMISSION_ROUND_TRIP_PER_LOT_ASSUMED
        },
        "metrics":{k:v for k,v in result.items() if k != "signals"}
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    print("TECHNICAL_TESTS_PASS")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
