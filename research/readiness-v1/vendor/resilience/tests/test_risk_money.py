"""Offline boundary and invariant tests; no live integration or external state."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import unittest

from faraz_core.risk import (
    ExposureAmount, LinearRiskModel, RiskRequest, VolumeRules, floor_volume, size_trade,
)
from faraz_core.money import (
    CashEvent, CloseDeal, apply_cash_event, close_lot, estimate_close, mark_pnl, open_lot,
)


D = Decimal


def request(**changes):
    base = RiskRequest(
        account_id="synthetic-account", symbol="SYNTH", side="BUY", entry="100", stop="95",
        risk_budget="44", rules=VolumeRules(".04", ".02", ".10", "10"),
        model=LinearRiskModel("100", "10", "10", "10", "20", "1000"),
        exposures=(), available_margin="100000", notional_cap="100000",
        portfolio_risk_cap="100000", held_risk="0", held_unknown_risk="0",
        held_notional="0", held_unknown_notional="0", held_unknown_margin="0",
    )
    return replace(base, **changes)


class RiskTests(unittest.TestCase):
    def test_standard_grid_and_550_risk_per_lot(self):
        rules = VolumeRules(".04", ".02", ".10", "10")
        self.assertEqual(floor_volume(".08", rules), D(".08"))
        result = size_trade(request())
        self.assertTrue(result.allowed)
        self.assertEqual(result.volume, D(".08"))
        self.assertEqual(result.risk_per_lot, D("550"))
        self.assertEqual(result.risk, D("44"))
        self.assertEqual(result.margin, D("80"))
        self.assertEqual(result.notional, D("800"))

    def test_minimum_is_not_grid_anchor(self):
        rules = VolumeRules(".04", ".03", ".10", "10")
        self.assertEqual(floor_volume(".08", rules), D(".06"))
        self.assertEqual(floor_volume(".05", rules), D("0"))
        self.assertEqual(floor_volume("1", rules), D(".09"))

    def test_minimum_risk_10_budget_5_cannot_round_up(self):
        result = size_trade(request(
            entry="100", stop="90", risk_budget="5",
            rules=VolumeRules(".01", ".01", "1", "10"),
            model=LinearRiskModel("100", "0", "0", "0", "0", "1000"),
        ))
        self.assertEqual(result.action, "NO_TRADE")
        self.assertEqual(result.volume, D("0"))
        self.assertIn("BELOW_MINIMUM_VOLUME", result.reasons)

    def test_grid_floor_property_loops(self):
        for step in (D(".01"), D(".02"), D(".03"), D(".125")):
            for minimum in (D(".01"), D(".04"), D(".13")):
                rules = VolumeRules(minimum, step, "1", "10")
                for cap_units in range(0, 105):
                    cap = D(cap_units) / 100
                    volume = floor_volume(cap, rules)
                    with self.subTest(step=step, minimum=minimum, cap=cap):
                        self.assertLessEqual(volume, min(cap, D("1")))
                        self.assertEqual(volume % step, 0)
                        if volume:
                            self.assertGreaterEqual(volume, minimum)
                            self.assertGreater(volume + step, min(cap, D("1")))
                        else:
                            self.assertLess((min(cap, D("1")) // step) * step, minimum)

    def test_risk_budget_property_loop(self):
        for cents in range(0, 10001, 37):
            budget = D(cents) / 100
            result = size_trade(request(risk_budget=budget))
            if result.allowed:
                self.assertLessEqual(result.risk, budget)
                self.assertEqual(result.volume % D(".02"), 0)
                self.assertGreaterEqual(result.volume, D(".04"))
                self.assertLessEqual(result.volume, D(".10"))

    def test_directional_scope_unknown_and_deduplication(self):
        rows = (
            ExposureAmount("synthetic-account", "SYNTH", "BUY", "POSITION", "a", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "BUY", "PENDING", "a", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "BUY", "PENDING", "b", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "UNKNOWN", "UNKNOWN", "c", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "SELL", "POSITION", "d", "1"),
            ExposureAmount("other-account", "SYNTH", "BUY", "POSITION", "e", "1"),
            ExposureAmount("synthetic-account", "OTHER", "BUY", "POSITION", "f", "1"),
        )
        # POSITION a and PENDING a are distinct typed identities. Their shared
        # text identifier supplies no evidence that either covers the other.
        result = size_trade(request(exposures=rows, rules=VolumeRules(".04", ".02", ".10", ".12")))
        self.assertTrue(result.allowed)
        self.assertEqual(result.directional_volume_held, D(".08"))
        self.assertEqual(result.volume, D(".04"))
        insufficient = size_trade(request(exposures=rows, rules=VolumeRules(".04", ".02", ".10", ".10")))
        self.assertFalse(insufficient.allowed)
        self.assertEqual(insufficient.directional_volume_held, D(".08"))
        self.assertIn("BELOW_MINIMUM_VOLUME", insufficient.reasons)
        bad = rows + (replace(rows[0], volume=".03"),)
        self.assertIn("CONFLICTING_DUPLICATE_EXPOSURE", size_trade(request(exposures=bad)).reasons)

    def test_same_text_id_position_and_pending_are_both_reserved(self):
        rows = tuple(ExposureAmount("synthetic-account", "SYNTH", "BUY", kind, "shared", ".02")
                     for kind in ("POSITION", "PENDING"))
        result = size_trade(request(exposures=rows, rules=VolumeRules(".01", ".01", ".10", ".05")))
        self.assertTrue(result.allowed)
        self.assertEqual(result.directional_volume_held, D(".04"))
        self.assertEqual(result.volume, D(".01"))
        self.assertEqual(result.volume + result.directional_volume_held, D(".05"))
        # A repeated observation of the exact same typed record is idempotent.
        duplicate = size_trade(request(exposures=rows + rows, rules=VolumeRules(".01", ".01", ".10", ".05")))
        self.assertEqual(duplicate, result)

    def test_unknown_namespace_never_infers_position_order_coverage(self):
        rows = (
            ExposureAmount("synthetic-account", "SYNTH", "BUY", "POSITION", "same", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "BUY", "PENDING", "same", ".02"),
            ExposureAmount("synthetic-account", "SYNTH", "UNKNOWN", "UNKNOWN", "same", ".03"),
        )
        rules = VolumeRules(".01", ".01", ".10", ".10")
        result = size_trade(request(exposures=rows, rules=rules))
        self.assertTrue(result.allowed)
        self.assertEqual(result.directional_volume_held, D(".07"))
        self.assertEqual(result.volume, D(".03"))
        self.assertEqual(size_trade(request(exposures=tuple(reversed(rows)), rules=rules)), result)
        unknown_duplicate = size_trade(request(exposures=rows + (rows[2],), rules=rules))
        self.assertEqual(unknown_duplicate, result)
        exhausted = size_trade(request(exposures=rows, rules=replace(rules, volume_limit=".06")))
        self.assertFalse(exhausted.allowed)
        self.assertEqual(exhausted.directional_volume_held, D(".07"))
        self.assertIn("DIRECTIONAL_VOLUME_LIMIT", exhausted.reasons)
        # Unknown direction also reserves the opposite side; BUY records do not.
        sell = size_trade(request(side="SELL", stop="105", exposures=rows, rules=rules))
        self.assertTrue(sell.allowed)
        self.assertEqual(sell.directional_volume_held, D(".03"))
        self.assertEqual(sell.volume, D(".07"))

    def test_same_typed_exposure_conflicts_and_unknown_numbers_fail_closed(self):
        for kind in ("POSITION", "PENDING", "UNKNOWN"):
            row = ExposureAmount("synthetic-account", "SYNTH", "BUY", kind, "source-id", ".02")
            for altered in (replace(row, volume=".03"), replace(row, side="SELL"),
                            replace(row, side="UNKNOWN")):
                with self.subTest(kind=kind, altered=altered):
                    rejected = size_trade(request(exposures=(row, altered)))
                    self.assertFalse(rejected.allowed)
                    self.assertIn("CONFLICTING_DUPLICATE_EXPOSURE", rejected.reasons)
            for invalid in (None, True, 0.02, "NaN", "Infinity", "-Infinity", "bad"):
                with self.subTest(kind=kind, invalid=invalid):
                    rejected = size_trade(request(exposures=(replace(row, volume=invalid),)))
                    self.assertFalse(rejected.allowed)
                    self.assertIn("INVALID_OR_UNKNOWN_EXPOSURE_VOLUME", rejected.reasons)

    def test_post_grid_aggregate_veto_and_unknown_deductions(self):
        cases = (
            ({"portfolio_risk_cap": "50", "held_risk": "5", "held_unknown_risk": "2"}, "PORTFOLIO_RISK_CAP"),
            ({"available_margin": "85", "held_unknown_margin": "6"}, "MARGIN_CAP"),
            ({"notional_cap": "900", "held_notional": "50", "held_unknown_notional": "51"}, "NOTIONAL_CAP"),
        )
        for changes, reason in cases:
            result = size_trade(request(**changes))
            self.assertFalse(result.allowed)
            self.assertIn(reason, result.reasons)
            self.assertEqual(result.volume, 0)
        # Boundaries are inclusive.
        result = size_trade(request(portfolio_risk_cap="50", held_risk="5", held_unknown_risk="1",
                                    available_margin="86", held_unknown_margin="6",
                                    notional_cap="901", held_notional="50", held_unknown_notional="51"))
        self.assertTrue(result.allowed)

    def test_unknown_invalid_inputs_fail_closed(self):
        for invalid in (None, True, 1.0, "NaN", "Infinity", "-Infinity", "bad"):
            for field in ("risk_budget", "entry", "held_unknown_risk", "held_unknown_margin", "notional_cap"):
                with self.subTest(field=field, invalid=invalid):
                    result = size_trade(request(**{field: invalid}))
                    self.assertFalse(result.allowed)
                    self.assertTrue(result.reasons)
            result = size_trade(request(model=replace(request().model, exit_cost_per_lot=invalid)))
            self.assertFalse(result.allowed)
            self.assertFalse(size_trade(request(rules=replace(request().rules, volume_limit=invalid))).allowed)
        self.assertFalse(size_trade(request(held_unknown_notional="-1")).allowed)
        self.assertFalse(size_trade(request(rules=replace(request().rules, volume_limit="0"))).allowed)

    def test_adverse_stop_and_sell_symmetry(self):
        buy = size_trade(request())
        sell = size_trade(request(side="SELL", stop="105"))
        self.assertEqual((buy.volume, buy.risk), (sell.volume, sell.risk))
        self.assertIn("STOP_NOT_ADVERSE", size_trade(request(stop="101")).reasons)
        self.assertIn("STOP_NOT_ADVERSE", size_trade(request(side="SELL", stop="99")).reasons)
        self.assertFalse(size_trade(request(stop="100")).allowed)

    def test_decimal_context_and_frozen_results(self):
        with localcontext() as ctx:
            ctx.prec = 3
            result = size_trade(request())
            self.assertEqual(result.risk, D("44"))
            self.assertEqual(floor_volume(".0899999999999999999999", request().rules), D(".08"))
        with self.assertRaises(FrozenInstanceError):
            result.volume = D("99")


def costed_lot(side="BUY", confirmed=True):
    lot = open_lot("lot-1", side, "100", ".05", "100", confirmed=confirmed)
    lot = apply_cash_event(lot, CashEvent("entry-commission", "ENTRY_FEE", "-.5", True))
    return apply_cash_event(lot, CashEvent("swap-1", "SWAP", "-.25", True))


class MoneyTests(unittest.TestCase):
    def test_mark_buy_bid_sell_ask_and_no_double_spread(self):
        buy = mark_pnl(costed_lot("BUY"), "101.5", "101.7", unpaid_exit_cost=".2", slippage_reserve=".1")
        sell = mark_pnl(costed_lot("SELL"), "98.3", "98.5", unpaid_exit_cost=".2", slippage_reserve=".1")
        self.assertEqual(buy.gross, D("7.5"))
        self.assertEqual(sell.gross, D("7.5"))
        self.assertEqual(buy.net, D("6.45"))
        self.assertEqual(sell.net, D("6.45"))
        self.assertEqual(buy.status, "ESTIMATED")
        # Entry at the ask and an unchanged quote produces one spread loss.
        lot = open_lot("spread", "BUY", "100.2", "1", "100", confirmed=True)
        mark = mark_pnl(lot, "100", "100.2", unpaid_exit_cost="0", slippage_reserve="0")
        self.assertEqual(mark.net, D("-20"))

    def test_partial_fee_swap_and_realized_2_5(self):
        original = costed_lot()
        result = close_lot(original, CloseDeal("close-1", ".02", "101.5", "-.2", True))
        closed, remaining = result.allocation.money, result.ledger
        self.assertTrue(result.applied)
        self.assertEqual(closed.status, "REALIZED")
        self.assertEqual(closed.gross, D("3"))
        self.assertEqual(closed.booked_entry_fees, D("-.2"))
        self.assertEqual(closed.booked_swap, D("-.1"))
        self.assertEqual(closed.net, D("2.5"))
        self.assertEqual(remaining.remaining_volume, D(".03"))
        self.assertEqual(remaining.remaining_entry_fees, D("-.3"))
        self.assertEqual(remaining.remaining_swap, D("-.15"))
        self.assertEqual(original.remaining_volume, D(".05"))

    def test_duplicate_costs_deals_and_conflicts(self):
        lot = costed_lot()
        duplicate = apply_cash_event(lot, CashEvent("entry-commission", "ENTRY_FEE", D("-.50"), True))
        self.assertIs(duplicate, lot)
        with self.assertRaisesRegex(ValueError, "CONFLICTING_DUPLICATE_EVENT"):
            apply_cash_event(lot, CashEvent("entry-commission", "ENTRY_FEE", "-.6", True))
        deal = CloseDeal("close-1", ".02", "101.5", "-.2", True)
        first = close_lot(lot, deal)
        replay = close_lot(first.ledger, deal)
        self.assertFalse(replay.applied)
        self.assertIs(replay.ledger, first.ledger)
        self.assertEqual(replay.allocation, first.allocation)
        with self.assertRaisesRegex(ValueError, "CONFLICTING_DUPLICATE_DEAL"):
            close_lot(first.ledger, replace(deal, exit_fee="-.3"))
        with self.assertRaisesRegex(ValueError, "DEAL_ID_ALREADY_USED_BY_CASH_EVENT"):
            close_lot(lot, replace(deal, deal_id="entry-commission"))
        with self.assertRaisesRegex(ValueError, "EVENT_ID_ALREADY_USED_BY_DEAL"):
            apply_cash_event(first.ledger, CashEvent("close-1", "SWAP", "-.1", True))

    def test_estimates_never_realized_and_confirmed_deals_required(self):
        lot = costed_lot(confirmed=False)
        deal = CloseDeal("hypothetical", ".02", "101.5", "-.2", False)
        estimate = estimate_close(lot, deal, unpaid_exit_cost=".1", slippage_reserve=".05")
        self.assertEqual(estimate.status, "ESTIMATED")
        self.assertEqual(estimate.net, D("2.35"))
        self.assertEqual(lot.remaining_volume, D(".05"))
        with self.assertRaisesRegex(ValueError, "CONFIRMED_DEALS"):
            close_lot(lot, replace(deal, confirmed=True))
        with self.assertRaisesRegex(ValueError, "CONFIRMED_DEALS"):
            close_lot(costed_lot(), deal)
        with self.assertRaisesRegex(ValueError, "NOT_CONFIRMED"):
            apply_cash_event(costed_lot(), CashEvent("estimate", "SWAP", "-.1", False))

    def test_partial_allocation_conservation_property_loop(self):
        for units in range(2, 31):
            lot = open_lot("property", "BUY", "100", D(units), "1", confirmed=True)
            lot = apply_cash_event(lot, CashEvent("fee", "ENTRY_FEE", "-.7", True))
            lot = apply_cash_event(lot, CashEvent("swap", "SWAP", "-.11", True))
            for index in range(units):
                result = close_lot(lot, CloseDeal(str(index), "1", "101", "-.01", True))
                lot = result.ledger
                with localcontext() as ctx:
                    ctx.prec = 10000
                    allocated_fees = sum((c.money.booked_entry_fees for c in lot.closures), D("0"))
                    allocated_swap = sum((c.money.booked_swap for c in lot.closures), D("0"))
                    self.assertEqual(allocated_fees + lot.remaining_entry_fees, D("-.7"))
                    self.assertEqual(allocated_swap + lot.remaining_swap, D("-.11"))
            self.assertEqual(lot.remaining_volume, 0)
            self.assertEqual(lot.remaining_entry_fees, 0)
            self.assertEqual(lot.remaining_swap, 0)

    def test_invalid_money_unknown_quote_cost_size(self):
        lot = costed_lot()
        for invalid in (None, True, 1.0, "NaN", "Infinity", "-Infinity", "bad"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    open_lot("bad", "BUY", invalid, ".05", "100", confirmed=True)
                with self.assertRaises(ValueError):
                    mark_pnl(lot, "100", "101", unpaid_exit_cost=invalid, slippage_reserve="0")
                with self.assertRaises(ValueError):
                    apply_cash_event(lot, CashEvent("invalid", "SWAP", invalid, True))
                with self.assertRaises(ValueError):
                    close_lot(lot, CloseDeal("invalid", invalid, "101", "0", True))
        with self.assertRaisesRegex(ValueError, "CROSSED_QUOTE"):
            mark_pnl(lot, "101", "100", unpaid_exit_cost="0", slippage_reserve="0")
        with self.assertRaisesRegex(ValueError, "CLOSE_EXCEEDS"):
            close_lot(lot, CloseDeal("too-big", ".06", "101", "0", True))
        with self.assertRaises(ValueError):
            mark_pnl(lot, "100", "101", unpaid_exit_cost="-1", slippage_reserve="0")

    def test_late_cost_policy_and_signed_rebate(self):
        lot = close_lot(costed_lot(), CloseDeal("close", ".02", "101", "0", True)).ledger
        with self.assertRaisesRegex(ValueError, "RECONCILIATION"):
            apply_cash_event(lot, CashEvent("late-fee", "ENTRY_FEE", "-.1", True))
        updated = apply_cash_event(lot, CashEvent("later-swap", "SWAP", ".1", True))
        self.assertEqual(updated.remaining_swap, D("-.05"))
        self.assertEqual(updated.remaining_volume, D(".03"))

    def test_replaced_ledger_balances_cannot_invent_profit_or_volume(self):
        lot = costed_lot()
        partial = close_lot(lot, CloseDeal("first", ".02", "101.5", "-.2", True)).ledger
        for source in (lot, partial):
            for changes in ({"remaining_entry_fees": D("10")},
                            {"remaining_swap": D("10")},
                            {"remaining_volume": D(".01")},
                            {"remaining_entry_fees": D("0"), "remaining_swap": D("0")}):
                with self.subTest(partial=bool(source.closures), changes=changes):
                    forged = replace(source, **changes)
                    with self.assertRaisesRegex(ValueError, "CONSERVATION_MISMATCH"):
                        mark_pnl(forged, "101", "101.2", unpaid_exit_cost="0", slippage_reserve="0")
                    with self.assertRaisesRegex(ValueError, "CONSERVATION_MISMATCH"):
                        close_lot(forged, CloseDeal("next", ".01", "101", "0", True))
        # Even a coordinated change conserving the grand fee total must match
        # the proportional accounting history for each actual closing deal.
        original_close = partial.closures[0]
        changed_money = replace(original_close.money, booked_entry_fees=D(".1"), net=D("2.8"))
        forged = replace(partial, remaining_entry_fees=D("-.6"),
                         closures=(replace(original_close, money=changed_money),))
        with self.assertRaisesRegex(ValueError, "CLOSURE_ACCOUNTING_MISMATCH"):
            mark_pnl(forged, "101", "101.2", unpaid_exit_cost="0", slippage_reserve="0")

    def test_duplicate_or_rewritten_history_is_rejected(self):
        lot = costed_lot()
        partial = close_lot(lot, CloseDeal("first", ".02", "101.5", "-.2", True)).ledger
        forged_ledgers = (
            replace(lot, cash_events=lot.cash_events + (lot.cash_events[0],)),
            replace(partial, closures=partial.closures + partial.closures),
            replace(partial, cash_events=partial.cash_events + (CashEvent("first", "SWAP", D("0"), True),)),
            replace(lot, cash_events=(replace(lot.cash_events[0], confirmed=False),) + lot.cash_events[1:]),
            replace(partial, closures=(replace(partial.closures[0],
                                              deal=replace(partial.closures[0].deal, confirmed=False)),)),
            replace(partial, closures=(replace(partial.closures[0],
                                              money=replace(partial.closures[0].money, gross=D("30"))),)),
            replace(lot, cash_events=(replace(lot.cash_events[0], after_closures=1),) + lot.cash_events[1:]),
        )
        for forged in forged_ledgers:
            with self.subTest(forged=forged):
                with self.assertRaises(ValueError):
                    mark_pnl(forged, "101", "101.2", unpaid_exit_cost="0", slippage_reserve="0")

    def test_later_swap_timing_reconstructs_and_duplicate_replay_stays_safe(self):
        lot = close_lot(costed_lot(), CloseDeal("first", ".02", "101.5", "-.2", True)).ledger
        lot = apply_cash_event(lot, CashEvent("later", "SWAP", "-.09", True))
        self.assertEqual(lot.cash_events[-1].after_closures, 1)
        self.assertIs(apply_cash_event(lot, CashEvent("entry-commission", "ENTRY_FEE", "-.5", True)), lot)
        self.assertIs(apply_cash_event(lot, CashEvent("later", "SWAP", "-.09", True)), lot)
        result = close_lot(lot, CloseDeal("last", ".03", "101", "-.1", True))
        self.assertEqual(result.allocation.money.booked_swap, D("-.24"))
        self.assertEqual(result.ledger.remaining_swap, 0)
        # Replaying still validates all original costs, proportions and balances.
        replay = close_lot(result.ledger, CloseDeal("last", ".03", "101", "-.1", True))
        self.assertFalse(replay.applied)
        forged = replace(lot, cash_events=lot.cash_events[:-1] + (replace(lot.cash_events[-1], after_closures=0),))
        with self.assertRaisesRegex(ValueError, "ACCOUNTING_MISMATCH"):
            mark_pnl(forged, "101", "101.2", unpaid_exit_cost="0", slippage_reserve="0")


if __name__ == "__main__":
    unittest.main()
