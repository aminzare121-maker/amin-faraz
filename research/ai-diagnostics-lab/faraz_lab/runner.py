"""Locked temporal comparison. All raw rows and fitted artifacts stay local."""
import argparse
import hashlib
import json
import platform
import time
import traceback
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .data import DATA_SHA256, QUALITIES, build_signals, load_csv
from .learning import (SOURCE_PROVENANCE, THRESHOLD, fit_calibrator, fit_logistic,
                       fit_tree, predict_calibrated, predict_logistic, predict_tree)
from .signals import b1, b2
from .statistics import paired_bootstrap, probability_metrics
from .types import Policy, Scenario, Symbol

SCENARIOS = (
    Scenario("base"),
    Scenario("high_cost", 1.0, 20.0, .40, 5.0, 1),
    Scenario("delayed", .50, 10.0, .20, 5.0, 2),
)
ROOT = Path(__file__).resolve().parents[1]


def utc(date):
    return int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())


def folds():
    return [
        {"name": "WF1", "train": (utc("2025-11-04"), utc("2026-05-01")),
         "calibration": (utc("2026-05-01"), utc("2026-06-01")),
         "validation": (utc("2026-06-01"), utc("2026-07-01")),
         "evaluation": (utc("2026-07-01"), utc("2026-08-01"))},
        {"name": "WF2", "train": (utc("2025-11-04"), utc("2026-06-01")),
         "calibration": (utc("2026-06-01"), utc("2026-07-01")),
         "validation": (utc("2026-07-01"), utc("2026-08-01")),
         "evaluation": (utc("2026-08-01"), utc("2026-09-01"))},
        {"name": "WF3", "train": (utc("2025-11-04"), utc("2026-07-01")),
         "calibration": (utc("2026-07-01"), utc("2026-08-01")),
         "validation": (utc("2026-08-01"), utc("2026-09-01")),
         "evaluation": (utc("2026-09-01"), utc("2026-10-01"))},
        {"name": "WF4", "train": (utc("2025-11-04"), utc("2026-08-01")),
         "calibration": (utc("2026-08-01"), utc("2026-09-01")),
         "validation": (utc("2026-09-01"), utc("2026-10-01")),
         "evaluation": (utc("2026-10-01"), utc("2026-11-03"))},
    ]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def code_manifest():
    paths = [ROOT / "CONTRACT.md", *sorted(ROOT.glob("*.py")), *sorted((ROOT / "faraz_lab").glob("*.py")),
             *sorted((ROOT / "tests").glob("*.py"))]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.exists()}


def window_rows(events, signals, start, end, embargo_seconds):
    """Labels must be known STRICTLY before the fitting window's embargo."""
    rows, counts = [], Counter()
    cutoff = end - embargo_seconds
    for index, candidate in signals.items():
        event = events.get(index)
        if not event:
            counts["global_unavailable_events"] += 1
            continue
        signal_time = event["signal_time"]
        if not start <= signal_time < end:
            continue
        counts["in_window_candidates"] += 1
        if signal_time >= cutoff:
            counts["purged_signal_embargo"] += 1
            continue
        if event["exit_time"] >= cutoff:
            counts["purged_future_or_embargo_exit"] += 1
            continue
        rows.append({"index": index, "features": list(candidate.features),
                     "label": int(event["net_per_lot"] > 0), "net": event["net_per_lot"],
                     "signal_time": signal_time, "exit_time": event["exit_time"]})
    rows.sort(key=lambda r: r["signal_time"])
    counts["usable_labels"] = len(rows)
    counts["positive_labels"] = sum(r["label"] for r in rows)
    counts["negative_labels"] = len(rows)-counts["positive_labels"]
    counts["latest_known_exit"] = max((r["exit_time"] for r in rows), default=None)
    counts["label_cutoff_exclusive"] = cutoff
    return rows, dict(counts)


def experiment_models(bars, signals, events, scenario, policy):
    scored = {"M1": {}, "M2": {}}
    trials, artifacts = [], []
    embargo = policy.max_holding_seconds + (scenario.latency_bars+1)*900
    for fold in folds():
        T, ts = window_rows(events, signals, *fold["train"], embargo)
        C, cs = window_rows(events, signals, *fold["calibration"], embargo)
        V, vs = window_rows(events, signals, *fold["validation"], embargo)
        eval_start, eval_end = fold["evaluation"]
        eval_indices = [i for i in signals if eval_start <= bars[i].time+900 < eval_end]
        for arm, fit_model, predictor in (("M1", fit_logistic, predict_logistic),
                                          ("M2", fit_tree, predict_tree)):
            trial = {"arm": arm, "fold": fold["name"], "intervals": fold,
                     "train": ts, "calibration": cs, "validation": vs,
                     "evaluation_candidate_count": len(eval_indices),
                     "threshold": THRESHOLD, "hyperparameter_search": False,
                     "validation_used_for_model_or_threshold_selection": False}
            for i in eval_indices:
                scored[arm][i] = None
            try:
                model = fit_model([r["features"] for r in T], [r["label"] for r in T])
                if model is None:
                    trial.update(status="unavailable", reason="insufficient_or_one_class_train")
                    trials.append(trial)
                    continue
                model.update(data_sha256=DATA_SHA256,
                             training_latest_exit=max(r["exit_time"] for r in T),
                             training_cutoff_exclusive=ts["label_cutoff_exclusive"])
                raw_c = [predictor(model, r["features"]) for r in C]
                calibration = fit_calibrator(raw_c, [r["label"] for r in C])
                if calibration is None:
                    trial.update(status="unavailable", reason="insufficient_or_one_class_calibration",
                                 model_sha256=digest(model))
                    artifacts.append({"fold": fold["name"], "arm": arm, "model": model,
                                      "calibration": None, "status": "not_eligible_for_scoring"})
                    trials.append(trial)
                    continue
                calibration.update(latest_exit=max(r["exit_time"] for r in C),
                                   cutoff_exclusive=cs["label_cutoff_exclusive"])
                assert max(r["exit_time"] for r in T) < fold["calibration"][0]
                assert min(r["signal_time"] for r in C) >= fold["calibration"][0]
                assert max(r["exit_time"] for r in C) < fold["validation"][0]
                vp = [predict_calibrated(calibration, predictor(model, r["features"])) for r in V]
                trial.update(status="fitted", model_sha256=digest(model),
                             calibration_sha256=digest(calibration),
                             calibration_in_sample_diagnostics_only=probability_metrics(
                                 [predict_calibrated(calibration, p) for p in raw_c], [r["label"] for r in C]),
                             validation_probability_metrics=probability_metrics(vp, [r["label"] for r in V]))
                ep, ey = [], []
                for i in eval_indices:
                    p = predict_calibrated(calibration, predictor(model, signals[i].features))
                    scored[arm][i] = p
                    # Evaluation labels are diagnostics AFTER model/scoring lock;
                    # they never participate in fit/calibration/selection.
                    e = events.get(i)
                    if e:
                        ep.append(p)
                        ey.append(int(e["net_per_lot"] > 0))
                trial["evaluation_probability_metrics_by_decision_fold_with_later_settlements"] = probability_metrics(ep, ey)
                trial["evaluation_labels_unavailable"] = len(eval_indices)-len(ey)
                trial["evaluation_positive_gate_count"] = sum(scored[arm][i] >= THRESHOLD for i in eval_indices)
                artifacts.append({"fold": fold["name"], "arm": arm, "model": model,
                                  "calibration": calibration, "status": "fitted"})
            except Exception as error:
                trial.update(status="failed", reason=type(error).__name__+": "+str(error),
                             traceback=traceback.format_exc())
                for i in eval_indices:
                    scored[arm][i] = None
            trials.append(trial)
    return scored, trials, artifacts


def daily_dates(start, end):
    a = datetime.fromtimestamp(start, timezone.utc)
    return [(a+timedelta(days=i)).date().isoformat() for i in range((end-start)//86400)]


def run(input_path, output_path):
    from .simulator import backtest, simulate_event
    started = time.perf_counter()
    output = Path(output_path).resolve()
    private_root = (ROOT / "outputs.PRIVATE").resolve()
    if not output.is_relative_to(private_root) or output.exists():
        raise ValueError("Use a NEW directory inside this lab's outputs.PRIVATE")
    output.mkdir(parents=True)
    before = code_manifest()
    contract_sha = before["CONTRACT.md"]
    registry = ROOT / "experiments.registry.PRIVATE.jsonl"

    def register(record):
        with registry.open("a", encoding="utf-8") as stream:
            stream.write(canonical({"run_directory": output.name, "code_sha256": digest(before), **record})+"\n")

    register({"event": "run_started", "contract_sha256": contract_sha, "input_sha256": DATA_SHA256,
              "prior_trials": {"count": 40, "status": "previously_seen_external_analyze.py_results_not_relabelled_holdout"}})
    bars, data_meta = load_csv(input_path)
    policy, spec = Policy(), Symbol()
    records, private_records, all_trials, private_models = [], [], [], []
    all_start, all_end = folds()[0]["evaluation"][0], folds()[-1]["evaluation"][1]
    days = daily_dates(all_start, all_end)
    quality_counts = {}
    for quality in QUALITIES:
        s1, q1 = build_signals(bars, quality, b1)
        s2, q2 = build_signals(bars, quality, b2)
        quality_counts[quality] = {"B1": q1, "B2": q2}
        for scenario in SCENARIOS:
            print(f"RUN {quality} / {scenario.name}", flush=True)
            events, event_failures = {}, Counter()
            for i, candidate in s1.items():
                event = simulate_event(bars, candidate, scenario, policy, spec)
                if event is not None:
                    events[i] = event
                else:
                    event_failures["entry_unavailable_or_invalid"] += 1
            scores, trials, models = experiment_models(bars, s1, events, scenario, policy)
            for t in trials:
                t.update(quality=quality, scenario=scenario.name)
                register({"event": "model_trial", **t})
            all_trials.extend(trials)
            private_models.append({"quality": quality, "scenario": scenario.name, "artifacts": models})
            results_by_arm = {}
            for arm in ("B0", "B1", "B2", "M1", "M2"):
                signals = {} if arm == "B0" else s2 if arm == "B2" else s1
                probabilities = scores[arm] if arm in scores else {i: 1.0 for i in signals}
                result = backtest(bars, all_start, all_end, signals, probabilities,
                                  scenario, policy, spec, threshold=THRESHOLD)
                results_by_arm[arm] = result
                public = {k: v for k, v in result.items() if k not in {"trades", "equity_path", "daily_equity"}}
                public.update(arm=arm, quality=quality, scenario=scenario.name,
                              hypothetical_costs=True, previously_seen_development=True,
                              label_event_failures=dict(event_failures))
                public["fold_daily_net"] = {f["name"]: sum(result["daily_pnl"].get(d, 0)
                       for d in daily_dates(*f["evaluation"])) for f in folds()}
                public["unavailable_model_folds"] = [t["fold"] for t in trials
                          if t["arm"] == arm and t["status"] != "fitted"]
                records.append(public)
                private_records.append({"quality": quality, "scenario": scenario.name,
                                        "arm": arm, "result": result})
                register({"event": "portfolio_trial", "quality": quality, "scenario": scenario.name,
                          "arm": arm, "metrics": result["metrics"], "status": "completed"})
            for public in records[-5:]:
                if public["arm"] in ("M1", "M2"):
                    public["paired_difference_vs_B1"] = [paired_bootstrap(
                        results_by_arm[public["arm"]]["daily_pnl"], results_by_arm["B1"]["daily_pnl"],
                        days, block=b) for b in (1, 5, 10)]
    after = code_manifest()
    if before != after:
        raise RuntimeError("Lab source changed DURING this run; do not treat as reproducible evidence")
    data_after = hashlib.sha256(Path(input_path).read_bytes()).hexdigest()
    if data_after != DATA_SHA256:
        raise RuntimeError("Input changed during run")
    failed = [t for t in all_trials if t["status"] == "failed"]
    summary = {
        "schema": 1, "lab_version": __version__, "data": data_meta,
        "code_manifest": before, "code_sha256": digest(before), "contract_sha256": contract_sha,
        "python": platform.python_version(), "seed": 1729,
        "policy": asdict(policy), "symbol": asdict(spec), "scenarios": [asdict(s) for s in SCENARIOS],
        "folds": folds(), "quality_counts": quality_counts, "models_provenance": SOURCE_PROVENANCE,
        "model_trials": all_trials, "portfolio_results": records,
        "data_unchanged": data_after == DATA_SHA256, "source_unchanged_during_run": before == after,
        "failed_model_trials": len(failed), "portfolio_trials": len(records),
        "execution_seconds": round(time.perf_counter()-started, 3),
        "final_test_independent": False, "real_world_profitability_established": False,
        "promoted_or_connected": False, "network_or_broker_imports": False,
        "limitations": ["unverified provenance/rights/session", "no observed Ask/volume/spread",
                         "hypothetical contract/cost/risk policy", "bounded 4h/2R experimental exit differs from live holding0",
                         "OHLC intrabar ordering unknown; adverse stop-first",
                         "data already seen; no independent future confirmation", "power/minimum effect not locked for future test"],
    }
    (output/"summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    (output/"models.PRIVATE.json").write_text(canonical(private_models), encoding="utf-8")
    (output/"portfolios.PRIVATE.json").write_text(canonical(private_records), encoding="utf-8")
    reproducible = {k: v for k, v in summary.items() if k != "execution_seconds"}
    (output/"reproducibility.sha256").write_text(digest(reproducible)+"\n", encoding="ascii")
    register({"event": "run_completed", "portfolio_trials": len(records), "model_trials": len(all_trials),
              "failed_model_trials": len(failed), "reproducibility_sha256": digest(reproducible)})
    print(json.dumps({"complete": True, "portfolios": len(records), "model_trials": len(all_trials),
                      "failed_model_trials": len(failed), "seconds": summary["execution_seconds"],
                      "reproducibility_sha256": digest(reproducible)}, sort_keys=True), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Authorized local offline AI vs rules research; no downloads")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        run(args.input, args.output)
    except Exception as error:
        registry = ROOT/"experiments.registry.PRIVATE.jsonl"
        with registry.open("a", encoding="utf-8") as f:
            f.write(canonical({"event": "run_failed", "error": type(error).__name__+": "+str(error),
                               "traceback": traceback.format_exc()})+"\n")
        raise
