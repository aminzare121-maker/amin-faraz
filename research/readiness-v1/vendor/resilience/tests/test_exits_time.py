"""Meaningful offline temporal/exit/replay checks; no private or market data."""
import unittest
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal as D, ROUND_DOWN, localcontext

from faraz_core.temporal import Candle, EventAvailability, Quote, atr_wilder, available_candles, validate_quote
from faraz_core.exits import (
    ExitState, MarketRules, Position, acknowledge_stop, assess_ohlc_touch,
    compare_candidates, evaluate_exit, observe_stop, replay_candidate, revise_position,
)


def buy(**changes):
    values = dict(side="buy", entry_price="4000.20", units="1", initial_stop="3995.00",
                  initial_risk_cash="5.50", remaining_cost="0.30")
    values.update(changes)
    return Position(**values)


def quote(bid="4003.30", ask="4003.50", time=20_000, **changes):
    values = dict(event_ms=time, available_ms=time, bid=bid, ask=ask)
    values.update(changes)
    return Quote(**values)


def flat_bars(count=15):
    return tuple(Candle(i * 1000, 1000, (i + 1) * 1000,
                        "100", "101", "99", "100") for i in range(count))


class TemporalTests(unittest.TestCase):
    def test_frozen_contract_and_quote_clock_vetoes(self):
        q = quote()
        with self.assertRaises(FrozenInstanceError):
            q.bid = D("9999")
        self.assertEqual(validate_quote(q, 19_999), "FUTURE_SOURCE_CLOCK")
        self.assertEqual(validate_quote(q, 21_001), "STALE_QUOTE")
        self.assertEqual(validate_quote(replace(q, available_ms=20_100), 20_000), "NOT_YET_AVAILABLE")
        self.assertEqual(validate_quote(replace(q, event_ms=20_100), 20_100), "FUTURE_SOURCE_CLOCK")
        self.assertEqual(validate_quote(replace(q, executable=False), 20_000), "NONEXECUTABLE_QUOTE")
        self.assertIsNone(EventAvailability(10, 20).veto(20))

    def test_final_closed_and_arrived_are_all_required(self):
        candle = Candle(0, 1000, 1200, "100", "999", "1", "101")
        self.assertEqual(available_candles([candle], 1100), ())
        self.assertEqual(available_candles([candle], 1200), (candle,))
        self.assertFalse(replace(candle, final=False).available_at(50_000))
        self.assertFalse(replace(candle, duration_ms=2000).available_at(1500))
        self.assertFalse(replace(candle, available_ms=900).available_at(50_000))

    def test_atr_explicit_warmup_true_range_and_wilder_smoothing(self):
        bars = flat_bars(15)
        warmup = atr_wilder(bars, 14_999)
        self.assertFalse(warmup.ready)
        self.assertEqual((warmup.available_bars, warmup.required_bars), (14, 15))
        self.assertEqual(atr_wilder(bars, 15_000).value, D(2))
        gap_price = replace(bars[-1], open=D(109), high=D(110), low=D(108), close=D(109))
        with localcontext() as context:
            context.prec = 512
            self.assertEqual(atr_wilder(bars[:-1] + (gap_price,), 15_000).value, D(36) / 14)
        expansion = Candle(15_000, 1000, 16_000, "100", "105", "99", "104")
        with localcontext() as context:
            context.prec = 512
            self.assertEqual(atr_wilder(bars + (expansion,), 16_000).value, D(32) / 14)

    def test_atr_and_exit_decisions_ignore_ambient_precision_and_rounding(self):
        bars = flat_bars() + (Candle(15_000, 1000, 16_000, "100", "105", "99", "104"),)
        p = buy()
        q = quote()
        normal_atr = atr_wilder(bars, 20_000)
        normal_decision = evaluate_exit("C", p, ExitState(), q, 20_000)
        normal_net = p.estimated_net(q.bid)
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_DOWN
            self.assertEqual(atr_wilder(bars, 20_000), normal_atr)
            self.assertEqual(evaluate_exit("C", p, ExitState(), q, 20_000), normal_decision)
            self.assertEqual(p.estimated_net(q.bid), normal_net)
            self.assertEqual(context.prec, 3)
            self.assertEqual(context.rounding, ROUND_DOWN)

    def test_future_and_nonfinal_suffix_do_not_change_decision_prefix(self):
        bars = flat_bars()
        future = Candle(15_000, 1000, 30_000, "100", "9999", "1", "100")
        forming = replace(future, final=False, available_ms=16_000)
        self.assertEqual(atr_wilder(bars, 20_000), atr_wilder(bars + (future, forming), 20_000))
        p = buy(entry_price="100", initial_stop="95", initial_risk_cash="5.3")
        q = quote("106", "106.2")
        prefix = evaluate_exit("B", p, ExitState(), q, 20_000, candles=bars)
        extended = evaluate_exit("B", p, ExitState(), q, 20_000, candles=bars + (future, forming))
        self.assertEqual(prefix, extended)


class ExitRuleTests(unittest.TestCase):
    def test_c_cash_floor_example_minimum_distance_and_fast_reversal(self):
        p = buy()
        held = evaluate_exit("C", p, ExitState(), quote(), 20_000,
                             MarketRules(min_stop_distance="2"))
        self.assertEqual((held.action, held.reason), ("HOLD", "MIN_STOP_DISTANCE"))
        self.assertEqual(held.estimated_current_net, D("2.80"))
        self.assertEqual(held.desired_floor_cash, D("1.40"))
        self.assertEqual(held.target_stop, D("4001.90"))
        self.assertIsNone(held.state.proposed_stop)
        reversal = evaluate_exit("C", p, held.state, quote("4001.80", "4002.00", 20_100), 20_100)
        self.assertEqual(reversal.reason, "STOP_NOT_BEHIND_EXECUTABLE_PRICE")
        self.assertEqual(reversal.state.peak_price, D("4003.30"))
        self.assertIsNone(reversal.state.acknowledged_stop)

    def test_proposal_acknowledgement_and_observation_are_distinct(self):
        p = buy()
        decision = evaluate_exit("C", p, ExitState(), quote(), 20_000)
        self.assertEqual(decision.action, "PROPOSE_STOP")
        self.assertEqual(decision.floor_status, "PROPOSED_ESTIMATE_ONLY")
        self.assertIsNone(decision.state.acknowledged_stop)
        self.assertIsNone(decision.state.observed_stop)
        ack = acknowledge_stop(p, decision.state, decision.target_stop)
        self.assertEqual(ack.acknowledged_stop, D("4001.90"))
        self.assertIsNone(ack.observed_stop)
        seen = observe_stop(p, ack, decision.target_stop)
        self.assertEqual(seen.observed_stop, D("4001.90"))
        with self.assertRaisesRegex(ValueError, "ACK_MUST_MATCH_PROPOSAL"):
            acknowledge_stop(p, decision.state, "4001.80")
        with self.assertRaisesRegex(ValueError, "WEAKEN"):
            observe_stop(p, seen, "4001.80")

    def test_stronger_ack_is_only_a_proposal_constraint_with_synthetic_evidence(self):
        p = buy()
        state = ExitState(basis_revision=0, proposed_stop="4002.00",
                          acknowledged_stop="4002.00", observed_stop="4001.90")
        held = evaluate_exit("C", p, state, quote(), 20_000)
        self.assertEqual(held.reason, "NO_STRONGER_STOP")
        self.assertEqual(held.state.acknowledged_stop, D("4002.00"))
        self.assertEqual(held.state.observed_stop, D("4001.90"))
        for output in (held, held.state):
            self.assertEqual(output.evidence_source, "OFFLINE_SYNTHETIC")
            self.assertIs(output.broker_protection_confirmed, False)
        with self.assertRaises(ValueError):
            replace(held, broker_protection_confirmed=True)
        with self.assertRaises(ValueError):
            replace(state, evidence_source="BROKER_VERIFIED")

    def test_c_sell_and_position_sizes_solve_on_tick_grid(self):
        cases = (
            (buy(), quote(), "4001.90"),
            (buy(units="2"), quote("4001.75", "4001.95"), "4001.05"),
            (buy(units="0.5", unit_value="2"), quote(), "4001.90"),
            (buy(side="sell", initial_stop="4005.40"), quote("3996.90", "3997.10"), "3998.50"),
        )
        for p, q, expected in cases:
            with self.subTest(side=p.side, units=p.units, unit_value=p.unit_value):
                result = evaluate_exit("C", p, ExitState(), q, 20_000)
                self.assertEqual(result.target_stop, D(expected))
                self.assertGreaterEqual(result.estimated_stop_net, result.desired_floor_cash)
                self.assertIsNone(result.fixed_take_profit)
        coarse = evaluate_exit("C", buy(), ExitState(), quote(), 20_000,
                               MarketRules(tick_size="0.3"))
        self.assertEqual(coarse.target_stop % D("0.3"), 0)
        self.assertGreaterEqual(coarse.estimated_stop_net, coarse.desired_floor_cash)

    def test_peak_is_executable_bid_or_ask_and_never_candle_extrema(self):
        p = buy()
        giant = Candle(0, 1000, 1000, "4000", "99999", "1", "4000")
        result = evaluate_exit("C", p, ExitState(), quote("4000.30", "9999"), 20_000, candles=[giant])
        self.assertEqual(result.state.peak_price, D("4000.30"))
        sell = buy(side="sell", initial_stop="4005.4")
        result = evaluate_exit("C", sell, ExitState(), quote("1", "4000.10"), 20_000, candles=[giant])
        self.assertEqual(result.state.peak_price, D("4000.10"))

    def test_unknown_cost_and_bad_quote_hold_without_new_peak(self):
        for candidate in ("A", "B", "C"):
            result = evaluate_exit(candidate, buy(remaining_cost=None), ExitState(), quote(), 20_000)
            self.assertEqual((result.action, result.reason), ("HOLD", "UNKNOWN_REMAINING_COST"))
            self.assertIsNone(result.state.peak_price)
        state = evaluate_exit("C", buy(), ExitState(), quote(), 20_000).state
        future = evaluate_exit("C", buy(), state, quote("5000", "5001", 30_000), 20_000)
        self.assertEqual(future.reason, "FUTURE_SOURCE_CLOCK")
        self.assertEqual(future.state, state)
        stale = evaluate_exit("C", buy(), state, quote("5000", "5001", 10_000), 20_000)
        self.assertEqual(stale.reason, "STALE_QUOTE")
        self.assertEqual(stale.state, state)

    def test_state_cannot_be_rewound_by_older_decision_or_delayed_source_quote(self):
        p = buy()
        state = evaluate_exit("C", p, ExitState(), quote(), 20_000).state
        rewind = evaluate_exit("C", p, state, quote(time=19_999), 19_999)
        self.assertEqual(rewind.reason, "DECISION_CLOCK_REGRESSION")
        self.assertEqual(rewind.state, state)
        old_source = evaluate_exit("C", p, state,
                                   quote("5000", "5001", 19_999, available_ms=20_001), 20_001)
        self.assertEqual(old_source.reason, "OUT_OF_ORDER_QUOTE")
        self.assertEqual(old_source.state, state)

    def test_stale_quote_preserves_installed_and_pending_stops(self):
        p = buy()
        result = evaluate_exit("C", p, ExitState(), quote(), 20_000)
        state = observe_stop(p, acknowledge_stop(p, result.state, result.target_stop), result.target_stop)
        held = evaluate_exit("C", p, state, quote("5000", "5001", 10_000), 20_100)
        self.assertEqual(held.reason, "STALE_QUOTE")
        self.assertEqual(held.state, state)
        self.assertEqual(held.state.proposed_stop, D("4001.90"))
        self.assertEqual(held.state.acknowledged_stop, D("4001.90"))
        self.assertEqual(held.state.observed_stop, D("4001.90"))

    def test_revision_rebases_peak_invalidates_floor_and_preserves_stronger_stop(self):
        p = buy()
        decision = evaluate_exit("C", p, ExitState(), quote(), 20_000)
        state = observe_stop(p, acknowledge_stop(p, decision.state, decision.target_stop), decision.target_stop)
        revised, reset = revise_position(p, state, remaining_cost="0.50", units="2")
        self.assertIsNone(reset.peak_price)
        self.assertIsNone(reset.desired_floor_cash)
        self.assertIsNone(reset.floor_revision)
        self.assertEqual(reset.observed_stop, D("4001.90"))
        result = evaluate_exit("C", revised, reset, quote("4001.95", "4002.15", 20_100), 20_100)
        self.assertEqual(result.state.peak_price, D("4001.95"))
        self.assertEqual(result.state.observed_stop, D("4001.90"))
        self.assertEqual(result.reason, "NO_STRONGER_STOP")
        self.assertLess(result.target_stop, result.state.observed_stop)
        # A direct supplied revision also invalidates old estimates even on a veto.
        changed = replace(p, revision=1, remaining_cost=None)
        unknown = evaluate_exit("C", changed, state, quote(), 20_000)
        self.assertIsNone(unknown.state.peak_price)
        self.assertIsNone(unknown.state.desired_floor_cash)
        self.assertEqual(unknown.state.observed_stop, state.observed_stop)

    def test_minimum_and_freeze_distance_do_not_move_a_requested_floor_away(self):
        result = evaluate_exit("C", buy(), ExitState(), quote(), 20_000,
                               MarketRules(freeze_distance="2"))
        self.assertEqual(result.reason, "FREEZE_DISTANCE")
        self.assertEqual(result.target_stop, D("4001.90"))
        self.assertIsNone(result.state.proposed_stop)

    def test_a_fixed_two_price_r_and_b_atr_trigger_without_fixed_tp(self):
        for side, initial_stop, expected_tp in (("buy", "95", "110"), ("sell", "105", "90")):
            p = buy(side=side, entry_price="100", initial_stop=initial_stop)
            result = evaluate_exit("A", p, ExitState(), quote("100", "100.2"), 20_000)
            self.assertEqual(result.target_stop, D(initial_stop))
            self.assertEqual(result.fixed_take_profit, D(expected_tp))
        p = buy(entry_price="100", initial_stop="95")
        before = evaluate_exit("B", p, ExitState(), quote("104.99", "105.19"), 20_000)
        self.assertEqual(before.target_stop, D(95))
        warmup = evaluate_exit("B", p, ExitState(), quote("106", "106.2"), 20_000)
        self.assertEqual(warmup.reason, "ATR_WARMUP")
        result = evaluate_exit("B", p, ExitState(), quote("106", "106.2"), 20_000, candles=flat_bars())
        self.assertEqual(result.target_stop, D(103))
        self.assertEqual(result.reason, "ATR14_TRAIL")
        self.assertIsNone(result.fixed_take_profit)
        sell = buy(side="sell", entry_price="100", initial_stop="105")
        result = evaluate_exit("B", sell, ExitState(), quote("93.8", "94"), 20_000, candles=flat_bars())
        self.assertEqual(result.target_stop, D(97))
        self.assertIsNone(result.fixed_take_profit)


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.p = buy(entry_price="100", initial_stop="95", initial_risk_cash="5.2", remaining_cost=".2")

    def test_deadline_without_quote_is_pending_and_first_later_executable_quote_fills(self):
        early = Quote(10, 10, "100", "100.2")
        pending = replay_candidate("C", self.p, [early], 0)
        self.assertEqual((pending.status, pending.request_ms), ("PENDING_EXIT", 3_600_000))
        self.assertIsNone(pending.fill_price)
        trace = [early, Quote(3_600_050, 3_600_050, "101", "101.2"),
                 Quote(3_600_100, 3_600_100, "101", "101.2", False),
                 Quote(3_600_150, 3_600_150, "99", "99.2")]
        result = replay_candidate("C", self.p, trace, 0)
        self.assertEqual((result.status, result.fill_ms, result.fill_price), ("CLOSED", 3_600_150, D(99)))
        self.assertEqual(result.estimated_net_cash, D("-1.2"))

    def test_gap_fill_is_current_executable_quote_after_latency_not_stop_target(self):
        trace = [Quote(10, 10, "100", "100.2"), Quote(50, 50, "94", "94.2"),
                 Quote(100, 100, "93", "93.2"), Quote(150, 150, "90", "90.2")]
        result = replay_candidate("A", self.p, trace, 0)
        self.assertEqual((result.exit_reason, result.request_ms, result.fill_ms), ("STOP", 50, 150))
        self.assertEqual(result.fill_price, D(90))
        self.assertEqual(result.estimated_net_cash, D("-10.2"))
        sell = replace(self.p, side="sell", initial_stop=D(105))
        trace = [Quote(50, 50, "105.8", "106"), Quote(150, 150, "109.8", "110")]
        result = replay_candidate("A", sell, trace, 0)
        self.assertEqual(result.fill_price, D(110))

    def test_stale_arrival_after_latency_cannot_supply_execution(self):
        result = replay_candidate("A", self.p,
                                  [Quote(50, 50, "94", "94.2"),
                                   Quote(100, 1200, "90", "90.2")], 0)
        self.assertEqual(result.status, "PENDING_EXIT")
        self.assertIsNone(result.fill_price)
        self.assertIn("STALE_QUOTE", [event.detail for event in result.events])

    def test_ohlc_double_touch_is_ambiguous_with_separate_conservative_scenario(self):
        candle = Candle(0, 1000, 1000, "100", "111", "94", "100")
        for p, stop, tp in ((self.p, "95", "110"),
                            (replace(self.p, side="sell", initial_stop=D(105)), "105", "90")):
            bar = candle if p.side == "buy" else replace(candle, high=D(106), low=D(89))
            result = assess_ohlc_touch(p, bar, stop, tp, 1000)
            self.assertEqual(result.label, "AMBIGUOUS_DOUBLE_TOUCH")
            self.assertIn("CONSERVATIVE", result.conservative_scenario)
            self.assertEqual(result.scenario_exit_price, D(stop))
            self.assertIsNone(result.actual_fill_price)
            self.assertEqual(assess_ohlc_touch(p, bar, stop, tp, 999).label, "UNAVAILABLE_CANDLE")
        opening_gap = replace(candle, open=D(90), low=D(85))
        gap_scenario = assess_ohlc_touch(self.p, opening_gap, "95", "110", 1000)
        self.assertEqual(gap_scenario.scenario_exit_price, D(90))
        self.assertIsNone(gap_scenario.actual_fill_price)

    def test_replay_ohlc_diagnostics_emit_ambiguity_without_a_fabricated_fill(self):
        candle = Candle(0, 1000, 1000, "100", "111", "94", "100")
        result = replay_candidate("A", self.p, (), 0, candles=(candle,))
        self.assertEqual(result.status, "PENDING_EXIT")
        self.assertIsNone(result.fill_price)
        self.assertIn("AMBIGUOUS_OHLC", [event.kind for event in result.events])
        self.assertIn("CONSERVATIVE_SCENARIO", [event.kind for event in result.events])
        self.assertNotIn("SYNTHETIC_FILL", [event.kind for event in result.events])

    def test_shared_trace_comparison_is_synthetic_and_has_no_b_or_c_fixed_tp(self):
        trace = (Quote(15_100, 15_100, "111", "111.2"),
                 Quote(15_200, 15_200, "110", "110.2"),
                 Quote(15_300, 15_300, "104", "104.2"),
                 Quote(15_400, 15_400, "103", "103.2"),
                 Quote(3_615_100, 3_615_100, "102", "102.2"))
        results = compare_candidates(self.p, trace, 15_000, candles=flat_bars())
        self.assertEqual(tuple(result.candidate for result in results), ("A", "B", "C"))
        self.assertTrue(all(result.synthetic for result in results))
        self.assertTrue(all(result.evidence_source == "OFFLINE_SYNTHETIC" for result in results))
        self.assertTrue(all(result.broker_protection_confirmed is False for result in results))
        self.assertEqual([result.estimated_net_cash for result in results], [D("9.8"), D("2.8"), D("2.8")])
        self.assertEqual([result.exit_reason for result in results], ["FIXED_TP", "STOP", "STOP"])
        self.assertEqual(self.p.units, 1)
        self.assertEqual(self.p.remaining_cost, D(".2"))
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_DOWN
            self.assertEqual(compare_candidates(self.p, trace, 15_000, candles=flat_bars()), results)


if __name__ == "__main__":
    unittest.main()
