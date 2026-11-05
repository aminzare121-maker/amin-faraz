"""Past-C activity budgets and fixed random controls; no fitting or selection.

Frozen phase-one execution is reused unchanged. No outcome, future trade count,
exposure or normalization ratio participates in a prospective admission rule.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import math
from statistics import mean

from faraz_lab.simulator import backtest
from faraz_lab.statistics import paired_bootstrap


TARGETS = ("M1_raw", "M1_cal", "M2_raw", "M2_cal")
SEEDS = (1729, 2718, 31415, 42017, 65537)
THRESHOLD = .55
RESAMPLES = 1000
BOOTSTRAP_SEED = 1729
UTC = timezone.utc


def uniform(seed: int, fold_name: str, signal_index: int) -> float:
    """The exact predeclared common SHA-256 draw, independent of the target."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Randomization seed must be an integer")
    if not isinstance(fold_name, str) or not fold_name or "|" in fold_name:
        raise ValueError("A nonempty unambiguous fold name is required")
    if isinstance(signal_index, bool) or not isinstance(signal_index, int) or signal_index < 0:
        raise ValueError("Signal index must be a nonnegative integer")
    message = f"phase2-v1|{seed}|{fold_name}|{signal_index}".encode("ascii")
    return int.from_bytes(hashlib.sha256(message).digest()[:8], "big") / (2 ** 64)


def _valid_probability(value) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
        return math.isfinite(number) and 0 <= number <= 1
    except (TypeError, ValueError, OverflowError):
        return False


def _days(start: int, end: int) -> list[str]:
    first = datetime.fromtimestamp(start, UTC).date()
    last = datetime.fromtimestamp(end - 1, UTC).date()
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def _folds(folds):
    if not folds:
        raise ValueError("At least one frozen evaluation fold is required")
    result = []
    seen = set()
    previous_end = None
    for fold in folds:
        name = fold["name"]
        if not isinstance(name, str) or not name or "|" in name or name in seen:
            raise ValueError("Unique nonempty ASCII-compatible fold names required")
        name.encode("ascii")
        start, end = fold["evaluation"]
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, int) or not isinstance(end, int) or start >= end):
            raise ValueError("Evaluation boundaries must be increasing Unix seconds")
        # Public fold totals are daily increments. Reject a partial-day split
        # rather than count the same daily increment in two different folds.
        if start % 86400 or end % 86400:
            raise ValueError("Fold boundaries must be UTC midnight for daily attribution")
        if previous_end is not None and previous_end != start:
            raise ValueError("Evaluation folds must be ordered and contiguous")
        calibration = fold.get("calibration")
        if calibration is not None and calibration[1] > start:
            raise ValueError("Calibration activity budget cannot extend into evaluation")
        result.append({"name": name, "evaluation": (start, end)})
        previous_end = end
        seen.add(name)
    return result


def _normalization(result: dict) -> dict:
    trades = result["trades"]
    net = float(result["metrics"]["net_pnl"])
    planned = sum(float(trade["planned_stop_risk"]) for trade in trades)
    seconds = sum(float(trade["effective_holding_seconds"]) for trade in trades)
    exposure_hours = seconds / 3600
    lot_hours = sum(float(trade["volume"]) * float(trade["effective_holding_seconds"]) / 3600
                    for trade in trades)
    exposed = exposure_hours > 0 and lot_hours > 0
    overruns = []
    gap_overruns = []
    for trade in trades:
        overrun = max(0.0, -float(trade["net"]) - float(trade["planned_stop_risk"]))
        if overrun > 1e-8:
            overruns.append(overrun)
            if trade["flags"].get("gap_stop") or trade["flags"].get("gap_exposure"):
                gap_overruns.append(overrun)
    return {"descriptive_only": True, "prospective_gate_uses_normalization": False,
            "allocated_planned_stop_risk_usd": planned,
            "exposure_seconds": seconds, "exposure_hours": exposure_hours,
            "lot_hours": lot_hours,
            "net_over_planned_risk": net / planned if exposed and planned > 0 else None,
            "net_per_exposure_hour": net / exposure_hours if exposed else None,
            "net_per_lot_hour": net / lot_hours if exposed else None,
            "status": "defined_descriptive" if exposed and planned > 0 else "undefined_zero_exposure_or_risk",
            "risk_overrun_trade_count": len(overruns),
            "risk_overrun_usd": sum(overruns),
            "gap_associated_risk_overrun_trades": len(gap_overruns),
            "gap_associated_risk_overrun_usd": sum(gap_overruns),
            "holding_time_note": "Frozen OHLC exit-time bounds and actual observed gaps; not tick timestamps",
            "risk_note": "Allocated planned stop risk includes hypothetical adverse slip/fees/reserve, not guaranteed maximum gap loss"}


def _candidate_counts(bars, signals, scores, folds) -> dict:
    result = {}
    for fold in folds:
        start, end = fold["evaluation"]
        indices = [i for i in signals if start <= bars[i].time + 900 < end]
        valid = [i for i in indices if _valid_probability(scores.get(i))]
        accepted = sum(float(scores[i]) >= THRESHOLD for i in valid)
        result[fold["name"]] = {
            "candidate_count": len(indices), "available_score_count": len(valid),
            "accepted_score_count": accepted,
            "rejected_score_count": len(valid) - accepted,
            "unavailable_score_count": len(indices) - len(valid),
            "denominator": "All prospective E candidates before entry/portfolio/risk admission; labels not required"}
    return result


def evaluate_activity(bars, signals_b1, signals_b2, score_maps, q_by_fold,
                      scenario, policy, spec, folds, primary=False):
    """Return aggregate public results and strictly separate private details.

    Random q is supplied by the independent frozen inference diagnostic from
    usable past C rows only. This function never estimates q from evaluation.
    """
    intervals = _folds(folds)
    start = intervals[0]["evaluation"][0]
    end = intervals[-1]["evaluation"][1]
    days = _days(start, end)
    budgets = {}
    for fold in intervals:
        name = fold["name"]
        declared = q_by_fold.get(name, {})
        budgets[name] = {}
        for target in TARGETS:
            value = declared.get(target)
            if value is not None and not _valid_probability(value):
                raise ValueError(f"Invalid past-C activity budget for {name}/{target}")
            budgets[name][target] = None if value is None else float(value)

    base_scores = {arm: dict(score_maps.get(arm) or {})
                   for arm in (*TARGETS, "BASE_C")}
    arm_signals = {"B0": {}, "B1": signals_b1, "B2": signals_b2,
                   **{arm: signals_b1 for arm in (*TARGETS, "BASE_C")}}
    all_scores = {"B0": {}, "B1": {i: 1.0 for i in signals_b1},
                  "B2": {i: 1.0 for i in signals_b2}, **base_scores}
    random_gates = {}
    random_uniforms = {seed: {} for seed in SEEDS}
    random_arms_by_target = {target: [] for target in TARGETS}
    index_fold = {}
    for fold in intervals:
        fold_start, fold_end = fold["evaluation"]
        indices = sorted(i for i in signals_b1
                         if fold_start <= bars[i].time + 900 < fold_end)
        for i in indices:
            index_fold[i] = fold["name"]
        for seed in SEEDS:
            random_uniforms[seed][fold["name"]] = {
                i: uniform(seed, fold["name"], i) for i in indices}

    for target in TARGETS:
        for seed in SEEDS:
            arm = f"R_{target}_seed{seed}"
            gates = {}
            for index, fold_name in sorted(index_fold.items()):
                q = budgets[fold_name][target]
                draw = random_uniforms[seed][fold_name][index]
                # q=1 always admits, including the vanishingly rare binary64
                # rounding of an integer/2**64 draw to exactly 1.0.
                gates[index] = None if q is None else float(q == 1 or (q != 0 and draw < q))
            random_gates[arm] = gates
            all_scores[arm] = gates
            arm_signals[arm] = signals_b1
            random_arms_by_target[target].append(arm)

    arm_order = ("B0", "B1", "B2", *TARGETS, "BASE_C",
                 *(arm for target in TARGETS for arm in random_arms_by_target[target]))
    portfolios = {}
    public_rows = []
    for arm in arm_order:
        result = backtest(bars, start, end, arm_signals[arm], all_scores[arm],
                          scenario, policy, spec, threshold=THRESHOLD)
        portfolios[arm] = result
        public_rows.append({"arm": arm,
                            "metrics": deepcopy(result["metrics"]),
                            "counters": deepcopy(result["counters"]),
                            "flags": deepcopy(result["flags"]),
                            "fold_daily_net": {
                                fold["name"]: sum(result["daily_pnl"].get(day, 0.0)
                                                  for day in _days(*fold["evaluation"]))
                                for fold in intervals},
                            "candidate_gate_counts": _candidate_counts(
                                bars, arm_signals[arm], all_scores[arm], intervals),
                            "normalization": _normalization(result)})
    if len(portfolios) != 28:
        raise AssertionError("Fixed design requires exactly 28 portfolios per condition")

    ensemble_daily = {}
    ensemble_rows = []
    for target in TARGETS:
        arms = random_arms_by_target[target]
        ensemble_daily[target] = {
            day: sum(portfolios[arm]["daily_pnl"].get(day, 0.0) for arm in arms) / len(SEEDS)
            for day in days}
        nets = [portfolios[arm]["metrics"]["net_pnl"] for arm in arms]
        exposures = [_normalization(portfolios[arm])["exposure_hours"] for arm in arms]
        lot_hours = [_normalization(portfolios[arm])["lot_hours"] for arm in arms]
        trades = [portfolios[arm]["metrics"]["trades"] for arm in arms]
        ensemble_rows.append({"target": target, "arms": list(arms), "seeds": list(SEEDS),
                              "seed_selection": "none; all five retained with equal weight",
                              "net_pnl_mean": mean(nets), "net_pnl_range": [min(nets), max(nets)],
                              "exposure_hours_mean": mean(exposures),
                              "exposure_hours_range": [min(exposures), max(exposures)],
                              "lot_hours_mean": mean(lot_hours),
                              "lot_hours_range": [min(lot_hours), max(lot_hours)],
                              "trades_mean": mean(trades), "trades_range": [min(trades), max(trades)],
                              "uncertainty_note": "Five seeds are a limited fixed randomization, not an adequate-power claim"})

    comparisons = []
    blocks = (1, 5, 10) if primary else (5,)
    for target in TARGETS:
        baselines = (("B0", portfolios["B0"]["daily_pnl"], "fixed_no_trade"),
                     ("B1", portfolios["B1"]["daily_pnl"], "frozen_rules"),
                     (f"R_{target}_mean5", ensemble_daily[target], "equal_weight_mean_of_five_fixed_seeds"))
        for baseline_name, daily, kind in baselines:
            comparisons.append({"arm": target, "baseline": baseline_name,
                                "baseline_kind": kind,
                                "paired_ci": [paired_bootstrap(
                                    portfolios[target]["daily_pnl"], daily, days,
                                    block=block, reps=RESAMPLES, seed=BOOTSTRAP_SEED)
                                    for block in blocks],
                                "matching_note": "Common UTC days including zeros; expected C-only activity budget, not matched realized E exposure",
                                "inference": "Exploratory, unadjusted, already-seen retrospective simulation; no confirmatory edge or deployment permission"})

    public = {"portfolios": public_rows, "comparisons": comparisons,
              "activity_budgets": deepcopy(budgets),
              "randomization": {
                  "targets": list(TARGETS), "seeds": list(SEEDS),
                  "threshold": THRESHOLD, "portfolios_per_condition": len(portfolios),
                  "uniform_formula": "int.from_bytes(SHA256(ASCII phase2-v1|seed|fold_name|signal_index)[:8], big)/2**64",
                  "common_draws": "Target/quality/cost absent from hash key; same seed/fold/index reuses the same uniform",
                  "q_source": "Acceptance fraction on original usable past C rows only, supplied frozen before E",
                  "missing_q": "unavailable/no-trade, distinct from an observed zero acceptance budget",
                  "activity_matching": "expected acceptance budget only; no E count, return, exposure or seed-winner matching",
                  "ensembles": ensemble_rows,
                  "bootstrap_blocks": list(blocks), "bootstrap_seed": BOOTSTRAP_SEED,
                  "bootstrap_repetitions": RESAMPLES, "common_utc_calendar_days": len(days),
                  "no_new_fit_or_calibration": True}}
    private = {"portfolios": portfolios,
               "scores": {arm: dict(all_scores[arm]) for arm in arm_order},
               "random_gate_maps": {arm: dict(gates) for arm, gates in random_gates.items()},
               "randomization_uniforms": random_uniforms,
               "random_ensemble_daily_pnl": ensemble_daily,
               "common_utc_days": days}
    return public, private
