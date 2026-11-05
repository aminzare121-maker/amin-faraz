"""Offline, synthetic-only contract tests. No original CSV, project, or account imports.

Assertions target leakage, execution costs, missing-model admission, portfolio
carry, and reproducibility rather than fitted performance on historical data.
"""

import hashlib
import importlib
import json
import math
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path


# -I deliberately omits CWD: add only this independently authorized lab.
LAB_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))

from faraz_lab import data, learning, signals, statistics
from faraz_lab.types import Bar, Candidate, Policy, Scenario, Symbol


T0 = int(datetime(2026, 7, 6, tzinfo=timezone.utc).timestamp())  # Monday.
ZERO = Scenario("synthetic-zero-cost-unit-test", 0, 0, 0, 0, 1)
FEATURES = [0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0]


def bars(count=10, start=T0):
    return [Bar(start + i * 900, 100.0, 100.2, 99.8, 100.0)
            for i in range(count)]


def candidate(index=0, side="buy", stop=None):
    return Candidate(side, (99.0 if side == "buy" else 101.0) if stop is None else stop,
                     list(FEATURES), index)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def training_data(count=80):
    X, y = [], []
    for i in range(count):
        label = i % 2
        direction = 1.0 if label else -1.0
        X.append([direction * (1 + i / 1000), direction, direction / 2,
                  1.0, 1.0, direction * 2, direction])
        y.append(label)
    return X, y


class SignalCausalityTests(unittest.TestCase):
    def test_breakout_is_nonvacuously_prefix_invariant(self):
        past = bars(64)
        past[-1] = Bar(past[-1].time, 100.0, 103.2, 99.9, 103.0)
        first = signals.b1(past, 63)
        self.assertIsNotNone(first)
        future = [Bar(past[-1].time + (i + 1) * 900, 1_000_000.0,
                      1_000_010.0, 999_990.0, 1_000_005.0) for i in range(20)]
        self.assertEqual(first, signals.b1(past + future, 63))
        self.assertEqual(len(first.features), 7)
        self.assertEqual(first.features[4], 1.0)
        self.assertTrue(signals.FEATURE_METADATA["relative_tick_volume"]["imputed"])

    def test_crossover_is_nonvacuously_prefix_invariant(self):
        past = bars(64)
        past[-1] = Bar(past[-1].time, 100.0, 101.2, 99.9, 101.0)
        first = signals.b2(past, 63)
        self.assertIsNotNone(first)
        future = [Bar(past[-1].time + 900, 1.0, 2.0, .5, 1.5)]
        self.assertEqual(first, signals.b2(past + future, 63))

    def test_warmup_and_gap_gate_are_explicit(self):
        past = bars(64)
        past[-1] = replace(past[-1], close=103.0, high=103.2)
        for producer in (signals.b1, signals.b2):
            self.assertIsNone(producer(past, 62))
            irregular = [replace(b, time=b.time + (900 if i >= 20 else 0))
                         for i, b in enumerate(past)]
            self.assertIsNone(producer(irregular, 63))
            self.assertIsNotNone(producer(irregular, 63, allow_history_gaps=True))

    def test_quality_gate_uses_only_observed_history(self):
        past = bars(64)
        future = [Bar(past[-1].time + 90_000, 100, 100, 100, 100)]
        for quality in data.QUALITIES:
            self.assertEqual(data.quality_gate(past, 63, quality),
                             data.quality_gate(past + future, 63, quality))
        flat_past = list(past)
        flat_past[20] = Bar(past[20].time, 100, 100, 100, 100)
        self.assertIsNotNone(data.quality_gate(flat_past, 63, "strict"))
        self.assertIsNone(data.quality_gate(flat_past, 63, "flat_inclusive_weekdays"))

    def test_weekend_sensitivity_is_explicit_not_a_claim_of_market_calendar(self):
        saturday = int(datetime(2026, 7, 4, tzinfo=timezone.utc).timestamp())
        observed = bars(64, saturday)
        self.assertIsNotNone(data.quality_gate(observed, 63, "strict"))
        self.assertIsNotNone(data.quality_gate(observed, 63, "flat_inclusive_weekdays"))
        self.assertIsNone(data.quality_gate(observed, 63, "inclusive_irregular"))


class LearningContractTests(unittest.TestCase):
    def test_missing_model_never_becomes_a_rule_score(self):
        for predictor, value in ((learning.predict_logistic, FEATURES),
                                 (learning.predict_tree, FEATURES),
                                 (learning.predict_calibrated, .8)):
            with self.subTest(predictor=predictor.__name__):
                with self.assertRaises(ValueError):
                    predictor(None, value)

    def test_insufficient_or_one_class_fit_is_explicitly_unavailable(self):
        X, y = training_data()
        for fitter in (learning.fit_logistic, learning.fit_tree):
            self.assertIsNone(fitter(X[:29], y[:29]))
            self.assertIsNone(fitter(X, [1] * len(X)))
        self.assertIsNone(learning.fit_calibrator([.3, .7] * 9, [0, 1] * 9))
        self.assertIsNone(learning.fit_calibrator([.7] * 30, [1] * 30))

    def test_invalid_numeric_input_is_not_silently_imputed(self):
        X, y = training_data()
        X[0][0] = float("nan")
        for fitter in (learning.fit_logistic, learning.fit_tree):
            with self.assertRaises(ValueError):
                fitter(X, y)
        with self.assertRaises(ValueError):
            learning.fit_calibrator([float("inf")] * 30, [0, 1] * 15)

    def test_artifacts_are_deterministic_json_and_have_nonconstant_scores(self):
        X, y = training_data()
        for fitter, predictor in ((learning.fit_logistic, learning.predict_logistic),
                                  (learning.fit_tree, learning.predict_tree)):
            with self.subTest(fitter=fitter.__name__):
                model = fitter(X, y)
                self.assertIsNotNone(model)
                self.assertEqual(canonical_hash(model), canonical_hash(fitter(X, y)))
                restored = json.loads(json.dumps(model, allow_nan=False))
                low, high = predictor(restored, X[0]), predictor(restored, X[1])
                self.assertTrue(0 < low < high < 1)
                self.assertEqual(high, predictor(model, X[1]))

    def test_fit_rows_tracks_actual_exit_without_wrapper_fabrication(self):
        X, y = training_data(40)
        rows = [{"learning_features": x, "net": 2.0 if label else -1.0,
                 "time": T0 + i * 900} for i, (x, label) in enumerate(zip(X, y))]
        self.assertEqual(learning.fit(rows)["training_latest_exit"], rows[-1]["time"])
        self.assertIsNone(learning.fit_logistic(X, y)["training_latest_exit"])

    def test_constant_and_extreme_calibration_remain_finite(self):
        labels = [0] * 30 + [1] * 10
        for probability in (0.0, .01, .5, .99, 1.0):
            with self.subTest(probability=probability):
                model = learning.fit_calibrator([probability] * len(labels), labels)
                calibrated = learning.predict_calibrated(model, probability)
                self.assertTrue(math.isfinite(calibrated))
                self.assertAlmostEqual(calibrated, .25, delta=.01)
                self.assertEqual(canonical_hash(model), canonical_hash(
                    learning.fit_calibrator([probability] * len(labels), labels)))
                self.assertEqual(calibrated, learning.predict_calibrated(
                    json.loads(json.dumps(model, allow_nan=False)), probability))


class TemporalBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = importlib.import_module("faraz_lab.runner")

    def test_purge_uses_actual_exit_and_strict_embargo_boundary(self):
        start, end, embargo = 10_000, 20_000, 900
        pairs = [(11_000, 19_099), (11_000, 19_100), (11_000, 19_500),
                 (10_000, 19_099), (9_999, 12_000), (20_000, 21_000)]
        candidates = {i: candidate(i) for i in range(len(pairs))}
        events = {i: {"signal_time": s, "exit_time": e, "net_per_lot": (-1) ** i}
                  for i, (s, e) in enumerate(pairs)}
        rows, stats = self.runner.window_rows(events, candidates, start, end, embargo)
        self.assertEqual({r["index"] for r in rows}, {0, 3})
        self.assertTrue(all(r["exit_time"] < end - embargo for r in rows))
        self.assertEqual(stats["label_cutoff_exclusive"], 19_100)

    def test_fold_windows_are_ordered_disjoint_and_evaluation_seams_touch(self):
        folds = self.runner.folds()
        self.assertEqual(len(folds), 4)
        for fold in folds:
            T, C, V, E = (fold[k] for k in ("train", "calibration", "validation", "evaluation"))
            self.assertTrue(T[0] < T[1] == C[0] < C[1] == V[0] < V[1] == E[0] < E[1])
        self.assertTrue(all(a["evaluation"][1] == b["evaluation"][0]
                            for a, b in zip(folds, folds[1:])))

    def _synthetic_windows(self, train_count=40):
        observed, candidates, events, evaluation_indices = [], {}, {}, []
        X, y = training_data(40)
        dates = ("2026-04-02", "2026-05-02", "2026-06-02", "2026-07-02")
        for group, date in enumerate(dates):
            for j in range(train_count if group == 0 else 40):
                i = len(observed)
                when = self.runner.utc(date) + 1800 * j
                observed.append(Bar(when - 900, 100, 101, 99, 100))
                candidates[i] = Candidate("buy", 99, list(X[j]), i)
                events[i] = {"signal_time": when, "exit_time": when + 900,
                             "net_per_lot": 1.0 if y[j] else -1.0}
                if group == 3:
                    evaluation_indices.append(i)
        return observed, candidates, events, evaluation_indices

    def test_validation_and_eval_labels_do_not_refit_or_change_frozen_scores(self):
        observed, candidates, events, ids = self._synthetic_windows()
        scores, trials, artifacts = self.runner.experiment_models(
            observed, candidates, events, ZERO, Policy())
        altered_events = {i: dict(e) for i, e in events.items()}
        altered_candidates = dict(candidates)
        validation_start = self.runner.utc("2026-06-01")
        evaluation_start = self.runner.utc("2026-07-01")
        for i, event in altered_events.items():
            if event["signal_time"] >= validation_start:
                event["net_per_lot"] *= -1
            if validation_start <= event["signal_time"] < evaluation_start:
                old = candidates[i]
                altered_candidates[i] = replace(old, features=[v * 1000 for v in old.features])
        scores2, trials2, artifacts2 = self.runner.experiment_models(
            observed, altered_candidates, altered_events, ZERO, Policy())
        first = [a for a in artifacts if a["fold"] == "WF1"]
        second = [a for a in artifacts2 if a["fold"] == "WF1"]
        self.assertEqual(len(first), 2)
        self.assertTrue(all(a["status"] == "fitted" for a in first))
        self.assertEqual(canonical_hash(first), canonical_hash(second))
        for arm in ("M1", "M2"):
            self.assertEqual([scores[arm][i] for i in ids], [scores2[arm][i] for i in ids])
            self.assertTrue(all(scores[arm][i] is not None for i in ids))
        for trial in trials + trials2:
            self.assertFalse(trial["hyperparameter_search"])
            self.assertFalse(trial["validation_used_for_model_or_threshold_selection"])

    def test_insufficient_train_yields_none_scores_not_baseline_scores(self):
        observed, candidates, events, ids = self._synthetic_windows(train_count=20)
        scores, trials, _ = self.runner.experiment_models(observed, candidates, events, ZERO, Policy())
        for arm in ("M1", "M2"):
            self.assertTrue(all(scores[arm][i] is None for i in ids))
            trial = next(t for t in trials if t["fold"] == "WF1" and t["arm"] == arm)
            self.assertEqual(trial["status"], "unavailable")

    def test_bootstrap_uses_common_zero_days_and_is_reproducible(self):
        days = [f"2026-07-{i:02}" for i in range(1, 11)]
        result = statistics.paired_bootstrap({days[0]: 10}, {}, days)
        self.assertEqual(result, statistics.paired_bootstrap({days[0]: 10}, {}, days))
        self.assertEqual(result["calendar_days"], 10)
        self.assertEqual(result["daily_delta_mean"], 1)
        self.assertEqual(result["total_net_delta"], 10)
        self.assertFalse(result["independent_future_test"])


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.simulator = importlib.import_module("faraz_lab.simulator")

    def event(self, observed, setup=None, scenario=ZERO, policy=None):
        result = self.simulator.simulate_event(observed, setup or candidate(), scenario,
                                              policy or Policy(), Symbol())
        self.assertIsNotNone(result)
        return result

    def portfolio(self, observed, setups=None, probabilities=None, scenario=ZERO, policy=None,
                  start=None, end=None):
        setups = {0: candidate()} if setups is None else setups
        probabilities = {i: 1.0 for i in setups} if probabilities is None else probabilities
        return self.simulator.backtest(observed, observed[0].time if start is None else start,
                                       observed[-1].time + 900 if end is None else end,
                                       setups, probabilities, scenario, policy or Policy(), Symbol())

    def test_latency_and_stop_first_when_both_intrabar_levels_are_reachable(self):
        observed = bars(5)
        observed[0] = replace(observed[0], high=110, low=90)
        observed[2] = replace(observed[2], high=103, low=98)
        event = self.event(observed)
        self.assertEqual(event["entry_index"], 2)
        self.assertEqual(event["entry_time"], T0 + 1800)
        self.assertEqual(event["exit_index"], 2)
        self.assertAlmostEqual(event["exit_price"], 99)
        self.assertAlmostEqual(event["net_per_lot"], -100)

    def test_buy_and_sell_pay_spread_slip_and_roundtrip_commission_once(self):
        scenario = Scenario("synthetic-cost", .5, 10, .2, 0, 1)
        for side in ("buy", "sell"):
            event = self.event(bars(4), candidate(side=side, stop=95 if side == "buy" else 105), scenario)
            self.assertAlmostEqual(event["net_per_lot"], -100)
            self.assertAlmostEqual(event["commission_per_lot"], 10)

    def test_sell_stop_checks_ask_even_when_bid_high_does_not_touch_stop(self):
        observed = bars(4)
        observed[2] = replace(observed[2], high=100.6)
        scenario = Scenario("synthetic-ask", .5, 10, .2, 0, 1)
        event = self.event(observed, candidate(side="sell", stop=101), scenario)
        self.assertEqual(event["exit_index"], 2)
        self.assertAlmostEqual(event["entry_price"], 99.8)
        self.assertAlmostEqual(event["exit_price"], 101.2)
        self.assertAlmostEqual(event["net_per_lot"], -150)

    def test_stop_gap_fills_worse_open_not_stale_stop_and_is_not_dropped(self):
        observed = bars(4)
        observed[3] = Bar(T0 + 9000, 98, 98.4, 97.8, 98)
        event = self.event(observed)
        self.assertEqual(event["exit_time"], observed[3].time)
        self.assertAlmostEqual(event["exit_price"], 98)
        self.assertAlmostEqual(event["net_per_lot"], -200)
        result = self.portfolio(observed, end=T0 + 2700)
        self.assertEqual(len(result["trades"]), 1)
        self.assertGreater(result["trades"][0]["exit_time"], T0 + 2700)
        self.assertLess(result["trades"][0]["net_pnl"], 0)

    def test_missing_intended_entry_expires_instead_of_waiting_for_future_bar(self):
        observed = bars(5)
        observed[2:] = [replace(b, time=b.time + 900) for b in observed[2:]]
        self.assertIsNone(self.simulator.simulate_event(observed, candidate(), ZERO, Policy(), Symbol()))

    def test_gap_timeout_uses_first_available_observation_not_fabricated_deadline(self):
        observed = bars(4)
        observed[3] = replace(observed[3], time=T0 + 7200)
        event = self.event(observed, policy=replace(Policy(), max_holding_seconds=900))
        self.assertEqual(event["exit_time"], T0 + 7200)
        self.assertEqual(event["exit_index"], 3)

    def test_end_of_dataset_liquidates_open_position_with_costs(self):
        event = self.event(bars(4), candidate(stop=95), Scenario("end-cost", .5, 10, .2, 0, 1))
        self.assertEqual(event["exit_time"], T0 + 3600)
        self.assertEqual(event["exit_index"], 3)
        self.assertAlmostEqual(event["net_per_lot"], -100)
        self.assertIn("final", event["exit_reason"])

    def test_future_flat_exposure_is_retained_not_screened_after_the_outcome(self):
        observed = bars(4)
        observed[3] = Bar(observed[3].time, 100, 100, 100, 100)
        event = self.event(observed, candidate(stop=95))
        self.assertTrue(event["flags"]["flat_exposure"])
        self.assertEqual(len(self.portfolio(observed)["trades"]), 1)

    def test_invalid_future_bar_invalidates_pricing_instead_of_dropping_the_trade(self):
        observed = bars(4)
        observed[3] = replace(observed[3], low=101)  # inconsistent with open100.
        with self.assertRaises(ValueError):
            self.simulator.simulate_event(observed, candidate(), ZERO, Policy(), Symbol())

    def test_rollover_is_counted_from_actual_exposure_interval(self):
        start = int(datetime(2026, 7, 6, 21, 15, tzinfo=timezone.utc).timestamp())
        event = self.event(bars(4, start), candidate(stop=95), Scenario("rollover", .5, 10, .2, 5, 1))
        self.assertAlmostEqual(event["swap_per_lot"], 5)
        self.assertAlmostEqual(event["net_per_lot"], -105)

    def test_volume_rounds_down_including_adverse_costs_and_minimum_is_not_forced(self):
        result = self.portfolio(bars(4), scenario=Scenario("risk-cost", .5, 10, .2, 0, 1))
        self.assertEqual(len(result["trades"]), 1)
        self.assertAlmostEqual(result["trades"][0]["volume"], .12)
        tiny = replace(Policy(), initial_capital=100, risk_fraction=.001)
        self.assertEqual(self.portfolio(bars(4), policy=tiny)["trades"], [])

    def test_missing_nan_none_or_below_threshold_scores_cannot_fall_back_to_rules(self):
        for probabilities in ({}, {0: None}, {0: float("nan")}, {0: float("inf")}, {0: .5499}):
            with self.subTest(probabilities=probabilities):
                self.assertEqual(self.portfolio(bars(4), probabilities=probabilities)["trades"], [])

    def test_intrabar_mtm_drawdown_latches_daily_guard_despite_recovery(self):
        observed = bars(9)
        observed[2] = replace(observed[2], high=110, low=94)
        setups = {0: candidate(stop=90), 3: candidate(3, stop=90)}
        policy = replace(Policy(), risk_fraction=.01, daily_dd=.005, total_dd=.9,
                         max_holding_seconds=900)
        result = self.portfolio(observed, setups, policy=policy)
        self.assertEqual(len(result["trades"]), 1)
        # Admission caps nominal100USD risk to the remaining50USD DD headroom.
        # .05lot reaches +50 then -30 under the disclosed conservative OHLC
        # ordering:80USD drawdown, although timeout subsequently realizes zero.
        self.assertAlmostEqual(result["trades"][0]["volume"], .05)
        self.assertGreaterEqual(result["metrics"]["max_drawdown"], 80 - 1e-8)
        self.assertAlmostEqual(result["ending_equity"], policy.initial_capital)

    def test_intrabar_mtm_total_guard_cannot_be_reset_by_recovery(self):
        observed = bars(9)
        observed[2] = replace(observed[2], high=110, low=94)
        setups = {0: candidate(stop=90), 3: candidate(3, stop=90)}
        policy = replace(Policy(), risk_fraction=.01, daily_dd=.9, total_dd=.005,
                         max_holding_seconds=900)
        self.assertEqual(len(self.portfolio(observed, setups, policy=policy)["trades"]), 1)

    def test_new_tehran_day_resets_daily_guard_before_midnight_close_decision(self):
        # First position trips the old day's conservative MTM guard and then
        # realizes zero. Bar3 closes at20:30UTC, exactly00:00 next day in the
        # fixed+03:30 research calendar: its decision belongs to the NEW day.
        start = int(datetime(2026, 7, 6, 19, 30, tzinfo=timezone.utc).timestamp())
        observed = bars(9, start)
        observed[2] = replace(observed[2], high=110, low=94)
        setups = {0: candidate(stop=90), 3: candidate(3, stop=90)}
        policy = replace(Policy(), risk_fraction=.01, daily_dd=.005, total_dd=.9,
                         max_holding_seconds=900)
        result = self.portfolio(observed, setups, policy=policy)
        boundary = int(datetime(2026, 7, 6, 20, 30, tzinfo=timezone.utc).timestamp())
        self.assertEqual(len(result["trades"]), 2)
        self.assertLess(result["trades"][0]["exit_time"], boundary)
        self.assertEqual(result["trades"][1]["signal_time"], boundary)
        self.assertEqual(result["trades"][1]["entry_time"], boundary + 900)
        self.assertEqual(result["counters"]["daily_guard_days"], 1)
        self.assertAlmostEqual(result["ending_equity"], policy.initial_capital)

    def test_entry_at_window_end_is_prospectively_excluded(self):
        self.assertEqual(self.portfolio(bars(5), end=T0 + 1800)["trades"], [])

    def test_overlapping_positions_are_not_opened(self):
        setups = {0: candidate(stop=95), 1: candidate(1, stop=95)}
        result = self.portfolio(bars(8), setups)
        self.assertEqual(len(result["trades"]), 1)

    def test_portfolio_reproducibility_and_daily_increment_reconciliation(self):
        observed = bars(10)
        observed[4] = replace(observed[4], high=103)
        result = self.portfolio(observed)
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(canonical_hash(result), canonical_hash(self.portfolio(observed)))
        self.assertAlmostEqual(sum(result["daily_pnl"].values()),
                               result["ending_equity"] - Policy().initial_capital)


if __name__ == "__main__":
    unittest.main()
