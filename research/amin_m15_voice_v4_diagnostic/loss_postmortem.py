#!/usr/bin/env python3
"""Evidence-only postmortem of frozen Eplanet M15 V4. NO strategy selection.

Reads previously generated fills from an existing research experiment.
All splits, including holdout, are consumed; results here are NOT new
out-of-sample confirmations. Never produces BUY/SELL order instructions.
"""
from __future__ import annotations
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "results"
PARTS = ("calibration", "validation", "holdout")
SIDES = ("reference", "filtered")
METRIC = "pnl_usd_assumed_fixed_001_lot"


def read_trades(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        trades = list(csv.DictReader(stream))
    for row in trades:
        row[METRIC] = float(row[METRIC])
        row["p_tp_calibrated"] = float(row["p_tp_calibrated"])
        row["decision_index"] = int(row["decision_index"])
        if not math.isfinite(row[METRIC]):
            raise ValueError("Non-finite PnL")
        if not 0 <= row["p_tp_calibrated"] <= 1:
            raise ValueError("Invalid calibrated probability")
    return trades


def wilson(k, n, z=1.95996398454):
    if not n:
        return [None, None]
    p = k / n
    denominator = 1 + z*z/n
    centre = (p + z*z/(2*n))/denominator
    radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return [round(centre-radius, 4), round(centre+radius, 4)]


def loss_run(xs):
    current = worst = 0
    for x in xs:
        current = current+1 if x < 0 else 0
        worst = max(worst,current)
    return worst


def describe(trades):
    y = [r[METRIC] for r in trades]
    gain = [v for v in y if v > 0]
    loss = [-v for v in y if v < 0]
    n = len(trades)
    mean_gain = statistics.mean(gain) if gain else None
    mean_loss = statistics.mean(loss) if loss else None
    break_even = (mean_loss/(mean_gain+mean_loss)
                  if mean_gain is not None and mean_loss is not None else None)
    # Break-even based on *realized winning/losing trade outcomes*, not TP probability.
    # Do not compare P(TP) against this threshold: TIMEOUT wins and losses exist.
    by_event = Counter(t["event"] for t in trades)
    tp_count = by_event.get("TARGET", 0)
    prob_tp = (statistics.mean(t["p_tp_calibrated"] for t in trades) if n else None)
    days = defaultdict(float)
    months = defaultdict(float)
    for r in trades:
        date = r["exit_day_utc"]
        days[date] += r[METRIC]
        months[date[:7]] += r[METRIC]
    ordered = sorted(trades,key=lambda t:t["decision_index"])
    p = len(ordered)//2
    halves = [sum(t[METRIC] for t in group) for group in (ordered[:p], ordered[p:])]
    total = sum(y)
    return {
        "trades": n, "net_usd_assumed": round(total, 3),
        "profit_factor": round(sum(gain)/sum(loss), 4) if loss else None,
        "profitable_trades": len(gain),
        "win_rate": round(len(gain)/n, 4) if n else None,
        "win_rate_wilson_95": wilson(len(gain), n),
        "realized_payoff_break_even_win_rate": round(break_even, 4) if break_even is not None else None,
        "win_rate_minus_realized_break_even_points": round((len(gain)/n-break_even)*100, 2)
            if n and break_even is not None else None,
        "avg_positive_trade_usd": round(mean_gain, 3) if mean_gain is not None else None,
        "avg_negative_trade_abs_usd": round(mean_loss, 3) if mean_loss is not None else None,
        "tp_count": tp_count,
        "tp_event_rate": round(tp_count/n, 4) if n else None,
        "tp_event_rate_wilson_95": wilson(tp_count,n),
        "mean_predicted_tp_probability": round(prob_tp, 4) if prob_tp is not None else None,
        "events": dict(sorted(by_event.items())),
        "first_half_net_usd": round(halves[0], 3),
        "second_half_net_usd": round(halves[1], 3),
        "worst_loss_streak": loss_run([r[METRIC] for r in ordered]),
        "days_observed": len(days),
        "days_positive": sum(v>0 for v in days.values()),
        "worst_day_usd": round(min(days.values()), 3) if days else None,
        "best_day_usd": round(max(days.values()), 3) if days else None,
        "monthly_net_usd": {k:round(v,3) for k,v in sorted(months.items())}
    }


def decide(calibration, validation, holdout):
    # DO NOT select or tune any rule with held-out outcomes.
    # This is a retrospective postmortem of an already-rejected filter.
    # An approval here is prohibited even if later code mistakes make metrics positive.
    assert all(isinstance(x,dict) for x in (calibration,validation,holdout))
    return {
        "strategy_approved": False,
        "orders_allowed": False,
        "recommended_action": "WAIT_AND_COLLECT_FRESH_EPLANET_DATA",
        "reason": "CONSUMED_HOLDOUT_AND_NO_VALIDATED_POSITIVE_EXPECTANCY",
        "holdout_usable_for_new_selection": False,
    }


def make_report(directory=OUT):
    result = {
      "purpose": "retrospective_loss_diagnosis_only",
      "input": "frozen V4 generated transaction CSVs",
      "data_used_for_new_strategy_selection": False,
      "tp_probability_not_equivalent_to_win_probability": True,
      "broker_costs_verified": False,
      "trade_position_size": "0.01 lot hypothetical",
      "blocks": {},
    }
    for part in PARTS:
        result["blocks"][part] = {}
        for side in SIDES:
            path = directory / f"{part}_{side}_trades.csv"
            result["blocks"][part][side] = describe(read_trades(path))
    result["decision"] = decide(*(result["blocks"][p]["filtered"] for p in PARTS))
    # No bonus point for reducing aggregate loss by taking fewer trades.
    # Track *expectancy*, profit factor, confidence, and drift instead.
    return result


def main():
    report = make_report()
    assert report["blocks"]["holdout"]["filtered"]["net_usd_assumed"] < 0
    assert report["blocks"]["holdout"]["filtered"]["profit_factor"] < 1
    assert report["decision"]["strategy_approved"] is False
    target = OUT / "loss_postmortem.json"
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("POSTMORTEM_PASS")
    for part in PARTS:
        for view in SIDES:
            x=report["blocks"][part][view]
            print(f"{part}/{view}: trades={x['trades']} net={x['net_usd_assumed']} "
                  f"win%={x['win_rate']} realized_break_even={x['realized_payoff_break_even_win_rate']} "
                  f"TP_event_rate={x['tp_event_rate']} P_TP_mean={x['mean_predicted_tp_probability']} "
                  f"worst_streak={x['worst_loss_streak']}")
    print(json.dumps(report["decision"],ensure_ascii=False))


if __name__ == "__main__":
    main()
