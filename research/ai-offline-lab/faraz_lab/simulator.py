"""Hypothetical Bid-bar research simulator, with no broker/project imports.

OHLC cannot establish an intrabar tick path. Exit timestamps for intrabar
touches are conservative bar-close bounds; drawdown uses a disclosed adverse
intrabar ordering. Neither simulated fills nor the symbol/policy are live facts.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math

from .types import Bar, Candidate, Policy, Scenario, Symbol


INTERVAL = 900
UTC = dt.timezone.utc
TEHRAN_RESEARCH_OFFSET = dt.timedelta(hours=3, minutes=30)


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _validate(scenario: Scenario, policy: Policy, spec: Symbol) -> None:
    positive = (spec.contract_size, spec.tick_size, spec.volume_min,
                spec.volume_step, spec.volume_max, policy.initial_capital,
                policy.max_holding_seconds, policy.reward_risk)
    if not all(_finite(x) and x > 0 for x in positive):
        raise ValueError("Finite positive symbol/capital/holding/reward values required")
    if not 0 < policy.risk_fraction < 1 or not 0 < policy.daily_dd < 1 or not 0 < policy.total_dd < 1:
        raise ValueError("Research risk fractions must lie strictly between zero and one")
    if policy.max_positions != 1:
        raise ValueError("This predeclared harness supports exactly one position")
    if spec.volume_min > spec.volume_max:
        raise ValueError("Invalid volume bounds")
    if any(not _finite(x) or x < 0 for x in (scenario.spread, scenario.commission,
                                            scenario.slippage, scenario.swap_per_lot)):
        raise ValueError("Costs must be finite nonnegative hypothetical debits")
    if not isinstance(scenario.latency_bars, int) or isinstance(scenario.latency_bars, bool) or scenario.latency_bars < 0:
        raise ValueError("latency_bars must be a nonnegative integer")


def _valid_bar(bar: Bar) -> bool:
    return (isinstance(bar.time, int) and not isinstance(bar.time, bool)
            and all(_finite(x) and x > 0 for x in (bar.open, bar.high, bar.low, bar.close))
            and bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high)


def _tick(price: float, tick_size: float, upward: bool) -> float:
    quantum = Decimal(str(tick_size))
    rounded = (Decimal(str(price)) / quantum).to_integral_value(
        rounding=ROUND_CEILING if upward else ROUND_FLOOR)
    return float(rounded * quantum)


def _roundovers(entry_time: int, mark_time: int) -> int:
    """Hypothetical constant debit at each UTC22 crossing; no triple-swap claim."""
    if mark_time <= entry_time:
        return 0
    return max(0, (mark_time - 22 * 3600) // 86400 - (entry_time - 22 * 3600) // 86400)


def _setup(bars, candidate, scenario, policy, spec):
    if candidate.side not in ("buy", "sell") or not isinstance(candidate.signal_index, int):
        return None
    index = candidate.signal_index
    if index < 0 or index >= len(bars) or not _valid_bar(bars[index]):
        return None
    entry_index = index + 1 + scenario.latency_bars
    intended_time = bars[index].time + INTERVAL * (1 + scenario.latency_bars)
    if entry_index >= len(bars):
        return None
    bar = bars[entry_index]
    if bar.time != intended_time or not _valid_bar(bar):
        return None  # This known-at-entry order expires; never chase a future quote.
    if not _finite(candidate.stop) or candidate.stop <= 0:
        return None
    buy = candidate.side == "buy"
    entry_quote = bar.open + (scenario.spread if buy else 0.0)
    entry = _tick(entry_quote + (scenario.slippage if buy else -scenario.slippage), spec.tick_size, buy)
    stop = _tick(candidate.stop, spec.tick_size, not buy)
    # Stop must protect the current executable exit side, not just the worse
    # entry fill. A gap can make a previously valid signal stop invalid.
    exit_quote_now = bar.open if buy else bar.open + scenario.spread
    if entry <= 0 or (buy and stop >= exit_quote_now) or (not buy and stop <= exit_quote_now):
        return None
    distance = abs(entry - stop)
    target = _tick(entry + (1 if buy else -1) * policy.reward_risk * distance,
                   spec.tick_size, not buy)
    if target <= 0 or (buy and target <= entry) or (not buy and target >= entry):
        return None
    stop_fill = _tick(stop + (-scenario.slippage if buy else scenario.slippage), spec.tick_size, not buy)
    if stop_fill <= 0:
        return None
    # Reserve one possible rollover for a <=24h desired hold; a future gap can
    # exceed this budget and is reported, never used to reject the entry.
    swap_reserve = scenario.swap_per_lot * math.ceil(policy.max_holding_seconds / 86400)
    risk = abs(entry - stop_fill) * spec.contract_size + scenario.commission + swap_reserve
    return {"entry_index": entry_index, "entry_time": bar.time,
            "signal_time": bars[index].time + INTERVAL, "entry_price": entry,
            "stop": stop, "target": target, "risk_per_lot": risk,
            "swap_reserve_per_lot": swap_reserve}


def simulate_event(bars, candidate, scenario, policy, spec) -> dict | None:
    """Isolated per-one-lot outcome; only prospective entry failures return None.

    Future bad OHLC aborts pricing explicitly rather than selectively dropping a
    losing/unresolved evaluation trade. Intrabar exit_time is an upper bound.
    """
    _validate(scenario, policy, spec)
    setup = _setup(bars, candidate, scenario, policy, spec)
    if setup is None:
        return None
    buy = candidate.side == "buy"
    direction = 1 if buy else -1
    entry = setup["entry_price"]
    stop, target = setup["stop"], setup["target"]
    deadline = setup["entry_time"] + policy.max_holding_seconds
    path = []
    flags = {"ambiguous_stop_target": False, "gap_exposure": False,
             "gap_stop": False, "flat_exposure": False,
             "forced_final_liquidation": False,
             "price_improvement_ignored": False,
             "intrabar_exit_time_is_upper_bound": False}
    gap_count = flat_count = 0
    last_time = None

    def executable(bid: float) -> float:
        quote = bid if buy else bid + scenario.spread
        return _tick(quote + (-scenario.slippage if buy else scenario.slippage), spec.tick_size, not buy)

    def pnl(price: float, time: int) -> float:
        swap = _roundovers(setup["entry_time"], time) * scenario.swap_per_lot
        return direction * (price - entry) * spec.contract_size - scenario.commission - swap

    for index in range(setup["entry_index"], len(bars)):
        bar = bars[index]
        if not _valid_bar(bar):
            raise ValueError("Invalid future OHLC encountered while exposed; trial pricing unavailable")
        if last_time is not None:
            if bar.time <= last_time:
                raise ValueError("Nonincreasing exposed observations")
            if bar.time - last_time != INTERVAL:
                gap_count += 1
                flags["gap_exposure"] = True
        flat = bar.open == bar.high == bar.low == bar.close
        flat_count += int(flat)
        flags["flat_exposure"] |= flat
        ask_add = 0.0 if buy else scenario.spread
        opened, high, low = bar.open + ask_add, bar.high + ask_add, bar.low + ask_add
        open_price = executable(bar.open)
        open_net = pnl(open_price, bar.time)
        adverse_price = executable(bar.low if buy else bar.high)
        favorable_price = executable(bar.high if buy else bar.low)
        mark_time = bar.time + INTERVAL
        reason = None
        time_basis = "observed_bar_close_bound"
        ambiguous = False
        # Opening quote is known to precede this candle's unknown high/low.
        gap_stop = opened <= stop if buy else opened >= stop
        gap_target = opened >= target if buy else opened <= target
        if gap_stop:
            reason, exit_price, mark_time = "stop", open_price, bar.time
            flags["gap_stop"] = True
            time_basis = "observed_bar_open"
        elif gap_target:
            reason = "target"
            exit_price = _tick(target + (-scenario.slippage if buy else scenario.slippage), spec.tick_size, not buy)
            mark_time = bar.time
            time_basis = "observed_bar_open"
            flags["price_improvement_ignored"] = True
        elif bar.time >= deadline:
            reason, exit_price, mark_time = "time_exit", open_price, bar.time
            time_basis = "observed_bar_open"
        else:
            touched_stop = low <= stop if buy else high >= stop
            touched_target = high >= target if buy else low <= target
            if touched_stop:
                reason = "stop"
                exit_price = _tick(stop + (-scenario.slippage if buy else scenario.slippage), spec.tick_size, not buy)
                ambiguous = touched_target
                flags["ambiguous_stop_target"] |= ambiguous
            elif touched_target:
                reason = "target"
                exit_price = _tick(target + (-scenario.slippage if buy else scenario.slippage), spec.tick_size, not buy)
            elif index == len(bars) - 1:
                reason, exit_price = "final_liquidation", executable(bar.close)
                flags["forced_final_liquidation"] = True
                time_basis = "observed_final_bar_close_bound"

        if reason is not None:
            if exit_price <= 0:
                raise ValueError("Nonpositive hypothetical exit price")
            exit_net = pnl(exit_price, mark_time)
            if time_basis == "observed_bar_open":
                # The rest of the candle is after the already-known exit.
                adverse_net = min(open_net, exit_net)
                favorable_net = max(open_net, exit_net)
            elif reason == "stop":
                adverse_net = min(open_net, exit_net)
                # Both barriers touched: honor stop-first rather than pretending
                # the favorable target was reached while the trade remained open.
                favorable_net = max(open_net, exit_net) if ambiguous else max(open_net, pnl(favorable_price, mark_time))
            else:
                adverse_net = min(open_net, exit_net, pnl(adverse_price, mark_time))
                favorable_net = max(open_net, exit_net)
            close_net = exit_net
            flags["intrabar_exit_time_is_upper_bound"] = time_basis != "observed_bar_open"
        else:
            adverse_net = min(open_net, pnl(adverse_price, mark_time))
            favorable_net = max(open_net, pnl(favorable_price, mark_time))
            close_net = pnl(executable(bar.close), mark_time)
        path.append({"index": index, "time": mark_time, "bar_time": bar.time,
                     "open_per_lot": open_net, "adverse_per_lot": adverse_net,
                     "favorable_per_lot": favorable_net, "close_per_lot": close_net,
                     "is_exit": reason is not None, "flat": flat,
                     "gap_from_previous": last_time is not None and bar.time - last_time != INTERVAL})
        if reason is not None:
            swap = _roundovers(setup["entry_time"], mark_time) * scenario.swap_per_lot
            gross = direction * (exit_price - entry) * spec.contract_size
            net = gross - scenario.commission - swap
            return {**setup, "side": candidate.side, "signal_index": candidate.signal_index,
                    "exit_index": index, "exit_time": mark_time, "exit_price": exit_price,
                    "exit_reason": reason, "exit_time_basis": time_basis,
                    "gross_per_lot": gross, "net_per_lot": net,
                    "commission_per_lot": scenario.commission, "swap_per_lot": swap,
                    "label": int(net > 0), "path": path, "flags": flags,
                    "ambiguous": flags["ambiguous_stop_target"],
                    "gap_exposure_bars": gap_count, "flat_exposure_bars": flat_count,
                    "effective_holding_seconds": mark_time - setup["entry_time"],
                    "desired_holding_seconds": policy.max_holding_seconds,
                    "risk_budget_overrun_per_lot": max(0.0, -net - setup["risk_per_lot"])}
        last_time = bar.time
    raise AssertionError("Every finite input must settle at the final observed close")


def _day(time: int) -> str:
    return dt.datetime.fromtimestamp(time, UTC).date().isoformat()


def _risk_day(time: int) -> str:
    return (dt.datetime.fromtimestamp(time, UTC) + TEHRAN_RESEARCH_OFFSET).date().isoformat()


def _volume(budget: float, risk: float, spec: Symbol) -> float:
    if not _finite(budget) or not _finite(risk) or budget <= 0 or risk <= 0:
        return 0.0
    step = Decimal(str(spec.volume_step))
    affordable = min(Decimal(str(budget)) / Decimal(str(risk)), Decimal(str(spec.volume_max)))
    size = (affordable / step).to_integral_value(rounding=ROUND_FLOOR) * step
    return float(size) if size >= Decimal(str(spec.volume_min)) else 0.0


def backtest(bars, start, end, signals, probabilities, scenario, policy, spec, threshold=.55) -> dict:
    """One chronological position/pending-order portfolio; no fold resets.

    Reports use UTC dates; the independent hypothetical daily guard uses fixed
    UTC+03:30. Future observations may settle an existing position only.
    """
    _validate(scenario, policy, spec)
    if not isinstance(start, int) or not isinstance(end, int) or start >= end:
        raise ValueError("UTC Unix-second start < end required")
    if not _finite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Invalid probability threshold")
    scores = probabilities or {}
    signals = signals or {}
    cash = float(policy.initial_capital)
    equity = cash
    peak = cash
    day_peak = cash
    risk_day = None
    daily_blocked = False
    total_blocked = False
    guarded_days = set()
    max_dd = max_dd_pct = 0.0
    counters = {"n_signals": 0, "entries": 0, "unavailable_score": 0,
                "below_threshold": 0, "overlap_position_or_pending": 0,
                "entry_expired": 0, "entry_after_window": 0,
                "invalid_entry_or_stop": 0, "min_volume_no_trade": 0,
                "daily_guard_no_trade": 0, "total_guard_no_trade": 0,
                "invalid_candidate_index": 0}
    pending = None
    active = None
    trades = []
    daily_marks = {}
    equity_at_end = cash
    last_processed_date = _day(start)

    def observe(value, time):
        nonlocal equity, peak, day_peak, max_dd, max_dd_pct
        nonlocal daily_blocked, total_blocked, equity_at_end
        if not _finite(value):
            raise ValueError("Nonfinite portfolio equity")
        equity = value
        peak = max(peak, value)
        day_peak = max(day_peak, value)
        drawdown = peak - value
        max_dd = max(max_dd, drawdown)
        max_dd_pct = max(max_dd_pct, drawdown / peak * 100 if peak > 0 else 0)
        if day_peak > 0 and day_peak - value >= day_peak * policy.daily_dd - 1e-10:
            daily_blocked = True
            guarded_days.add(risk_day)
        if peak > 0 and peak - value >= peak * policy.total_dd - 1e-10:
            total_blocked = True
        if time <= end:
            equity_at_end = value

    for index, bar in enumerate(bars):
        if bar.time + INTERVAL < start:
            continue
        if bar.time >= end and active is None and pending is None:
            break
        if not _valid_bar(bar):
            raise ValueError("Invalid observed OHLC: portfolio trial unavailable")
        current_risk_day = _risk_day(bar.time)
        if current_risk_day != risk_day:
            risk_day = current_risk_day
            day_peak = equity  # prior observed MTM; gap losses count on arrival day
            daily_blocked = False
        if pending is not None:
            expected = pending["intended_time"]
            if bar.time > expected or (index >= pending["entry_index"] and bar.time != expected):
                counters["entry_expired"] += 1
                pending = None
            elif bar.time == expected:
                candidate = pending["candidate"]
                pending = None
                if daily_blocked:
                    counters["daily_guard_no_trade"] += 1
                elif total_blocked or cash <= 0:
                    counters["total_guard_no_trade"] += 1
                else:
                    event = simulate_event(bars, candidate, scenario, policy, spec)
                    if event is None:
                        counters["invalid_entry_or_stop"] += 1
                    else:
                        budget = min(cash * policy.risk_fraction,
                                     cash - day_peak * (1 - policy.daily_dd),
                                     cash - peak * (1 - policy.total_dd))
                        volume = _volume(budget, event["risk_per_lot"], spec)
                        if volume == 0:
                            counters["min_volume_no_trade"] += 1
                        else:
                            # No future event flags/outcome participate in sizing.
                            active = {"event": event, "volume": volume,
                                      "path": {p["index"]: p for p in event["path"]},
                                      "risk_budget": budget}
                            counters["entries"] += 1

        if active is not None:
            event, volume = active["event"], active["volume"]
            row = active["path"].get(index)
            if row is None:
                raise AssertionError("Missing exposed observation")
            observe(cash + volume * row["open_per_lot"], bar.time)
            # OHLC ordering is unknown: this is a conservative drawdown bound,
            # not a fabricated tick sequence or a claim about actual execution.
            observe(cash + volume * row["favorable_per_lot"], row["time"])
            observe(cash + volume * row["adverse_per_lot"], row["time"])
            observe(cash + volume * row["close_per_lot"], row["time"])
            if row["is_exit"]:
                gross = volume * event["gross_per_lot"]
                net = volume * event["net_per_lot"]
                trade = {k: v for k, v in event.items() if k != "path"}
                trade.update({"volume": volume, "gross": gross, "net": net,
                              "gross_pnl": gross, "net_pnl": net,
                              "commission": volume * event["commission_per_lot"],
                              "swap": volume * event["swap_per_lot"],
                              "risk_budget": active["risk_budget"],
                              "planned_stop_risk": volume * event["risk_per_lot"]})
                cash += net
                equity = cash
                if event["exit_time"] <= end:
                    equity_at_end = equity
                trades.append(trade)
                active = None
        else:
            equity = cash
            if bar.time + INTERVAL <= end:
                equity_at_end = equity
        if bar.time + INTERVAL > start:
            day = _day(bar.time)
            daily_marks[day] = equity
            last_processed_date = day

        decision_time = bar.time + INTERVAL
        # A candle ending at Tehran midnight belongs to the previous risk day
        # for its intrabar marks, but a new decision at that instant belongs to
        # the new day. Do not carry yesterday's latched entry veto for one bar.
        decision_risk_day = _risk_day(decision_time)
        if decision_risk_day != risk_day:
            risk_day = decision_risk_day
            day_peak = equity
            daily_blocked = False
        if start <= decision_time < end and index in signals:
            counters["n_signals"] += 1
            candidate = signals[index]
            if candidate.signal_index != index:
                counters["invalid_candidate_index"] += 1
                continue
            if active is not None or pending is not None:
                counters["overlap_position_or_pending"] += 1
                continue
            score = scores.get(index)
            if isinstance(score, bool) or not _finite(score) or not 0 <= float(score) <= 1:
                counters["unavailable_score"] += 1
                continue
            if float(score) < threshold:
                counters["below_threshold"] += 1
                continue
            if daily_blocked:
                counters["daily_guard_no_trade"] += 1
                continue
            if total_blocked or cash <= 0:
                counters["total_guard_no_trade"] += 1
                continue
            intended = decision_time + scenario.latency_bars * INTERVAL
            if intended >= end:
                counters["entry_after_window"] += 1
                continue
            pending = {"candidate": candidate, "intended_time": intended,
                       "entry_index": index + 1 + scenario.latency_bars}

    if active is not None:
        raise AssertionError("Exposed position was not settled")
    if pending is not None:
        counters["entry_expired"] += 1
    start_date = dt.datetime.fromtimestamp(start, UTC).date()
    end_date = dt.datetime.fromtimestamp(end - 1, UTC).date()
    final_date = max(end_date, dt.date.fromisoformat(last_processed_date))
    daily_equity, daily_pnl, equity_path = {}, {}, []
    previous_equity = float(policy.initial_capital)
    day = start_date
    while day <= final_date:
        key = day.isoformat()
        value = daily_marks.get(key, previous_equity)
        increment = value - previous_equity
        daily_equity[key], daily_pnl[key] = value, increment
        equity_path.append({"date": key, "equity": value, "pnl": increment})
        previous_equity = value
        day += dt.timedelta(days=1)
    wins = sum(t["net"] for t in trades if t["net"] > 0)
    losses = -sum(t["net"] for t in trades if t["net"] < 0)
    no_trade = counters["n_signals"] - len(trades)
    counters["no_trade"] = no_trade
    counters["daily_guard_days"] = len(guarded_days)
    counters["total_guard_tripped"] = int(total_blocked)
    metrics = {"trades": len(trades), "num_trades": len(trades),
               "n_signals": counters["n_signals"], "no_trade": no_trade,
               "net_pnl": cash - policy.initial_capital,
               "period_net_pnl": equity_at_end - policy.initial_capital,
               "post_end_pnl": cash - equity_at_end,
               "return_pct": (cash / policy.initial_capital - 1) * 100,
               "expectancy": (cash - policy.initial_capital) / len(trades) if trades else None,
               "profit_factor": wins / losses if losses > 0 else None,
               "gross_profit": wins, "gross_loss": losses,
               "gross_market_pnl": sum(t["gross"] for t in trades),
               "total_commission": sum(t["commission"] for t in trades),
               "total_swap": sum(t["swap"] for t in trades),
               "max_drawdown": max_dd, "max_drawdown_pct": max_dd_pct,
               "worst_day": min(daily_pnl.values(), default=0.0),
               "turnover_lots": 2 * sum(t["volume"] for t in trades),
               "exposure_seconds": sum(t["effective_holding_seconds"] for t in trades),
               "ambiguous_trades": sum(t["ambiguous"] for t in trades),
               "flat_exposure_trades": sum(t["flags"]["flat_exposure"] for t in trades),
               "gap_exposure_trades": sum(t["flags"]["gap_exposure"] for t in trades),
               "forced_final_liquidations": sum(t["flags"]["forced_final_liquidation"] for t in trades)}
    return {"metrics": metrics, "counters": counters, "trades": trades,
            "daily_pnl": daily_pnl, "daily_equity": daily_equity,
            "equity_path": equity_path, "ending_equity": cash,
            "equity_at_end": equity_at_end,
            "flags": {"hypothetical_research_policy_not_owner_policy": True,
                      "hypothetical_symbol_not_broker_spec": True,
                      "bid_bar_side_assumed_unverified": True,
                      "margin_and_liquidity_not_modelled": True,
                      "report_calendar": "UTC daily close; unobserved days carry last observed equity",
                      "risk_guard_calendar": "fixed UTC+03:30 research day",
                      "daily_guard_basis": "peak-to-conservative-MTM drawdown; blocks new entries, no forced close",
                      "mtm_cost_basis": "liquidation-side quote incl adverse slip, full roundtrip commission and accrued swap",
                      "drawdown_order": "favorable-before-adverse OHLC bound; intrabar order unobserved",
                      "profit_factor_undefined": losses == 0,
                      "settlement_after_end": any(t["exit_time"] > end for t in trades)}}
