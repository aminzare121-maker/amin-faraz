"""D2 numerical fixtures; no broker or host calendar is observed."""
from dataclasses import replace
from decimal import Decimal, localcontext
import unittest

from faraz_lab.broker_contract import (
    SyntheticAccount, TypedRef, ExposureSlice, SliceOverlap, reconcile_exposures,
    PendingMarginCoverage, MarginSnapshot, map_margin, check_capacity,
    QuoteObservation, executable_price, OffsetPeriod, SessionWindow, SessionCalendar,
    local_to_utc, session_allows_entry, StopObservation, synthetic_stop_observed,
    NetCostEvidence, confirmed_net_total,
)


D = Decimal
HOUR = 3_600_000
CONTRACT_EVIDENCE = []


class BrokerContractTests(unittest.TestCase):
    def setUp(self):
        self.account = SyntheticAccount("contract-lab-account", 4, "contract-lab-owner")

    def row(self, kind="POSITION", key="shared-text-id", volume=".01", **changes):
        return replace(ExposureSlice(self.account, TypedRef(kind, key), "XAU.SYNTHETIC", "BUY",
                                     volume, "4000.20", "100", "1000"), **changes)

    def record(self, name, **values):
        CONTRACT_EVIDENCE.append({"scenario": name, "seed": 41207,
                                  "evidence_source": "OFFLINE_SYNTHETIC", "pass": True, **values})

    def test_account_revision_scope_currency_and_complete_ownership_are_bound(self):
        for change in ({"mode": "REAL"}, {"synthetic": False}, {"ownership_complete": False}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.account, **change)
        for change in ({"account_id": "other"}, {"revision": 5},
                       {"owner_scope": "other-owner"}, {"currency": "EUR"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "OWNERSHIP_BINDING"):
                reconcile_exposures(self.account, (self.row(account=replace(self.account, **change)),))

    def test_equal_text_typed_ids_are_not_implicit_overlap(self):
        ledger = reconcile_exposures(self.account, (self.row(), self.row("PENDING", volume=".02")))
        self.assertEqual(ledger.known_notional, D("4000.20"))
        self.assertEqual(ledger.unknown_notional, D("8000.40"))
        self.assertEqual(ledger.unfilled_margin, D("20"))
        self.record("typed_same_text_identity_is_distinct", position_volume=".01", pending_volume=".02",
                    known_notional=str(ledger.known_notional), unknown_notional=str(ledger.unknown_notional),
                    unfilled_margin=str(ledger.unfilled_margin))

    def test_exact_same_typed_record_dedupes_but_conflict_rejects(self):
        row = self.row()
        self.assertEqual(reconcile_exposures(self.account, (row, row)).total_notional, D("4000.20"))
        with self.assertRaisesRegex(ValueError, "CONFLICTING_TYPED_EXPOSURE"):
            reconcile_exposures(self.account, (row, replace(row, volume=".02")))

    def test_explicit_interval_overlap_credits_only_filled_pending_slice_once(self):
        position, pending = self.row(), self.row("PENDING", volume=".02")
        proof = SliceOverlap(self.account, position.reference, pending.reference, "0", "0", ".01", "fill-link")
        ledger = reconcile_exposures(self.account, (position, pending), (proof, proof))
        self.assertEqual(ledger.known_notional, D("4000.20"))
        self.assertEqual(ledger.unknown_notional, D("4000.20"))
        self.assertEqual(ledger.unfilled_margin, D("10"))
        with self.assertRaisesRegex(ValueError, "SLICE_CREDIT_REUSED"):
            reconcile_exposures(self.account, (position, pending), (proof, replace(proof, evidence_id="same-slice-new-id")))
        self.record("explicit_filled_slice_overlap", linked_volume=".01", pending_original_volume=".02",
                    known_notional=str(ledger.known_notional), unknown_notional=str(ledger.unknown_notional),
                    remaining_margin=str(ledger.unfilled_margin), duplicate_proof_credited_once=True)

    def test_unknown_valuation_direction_or_oversized_overlap_cannot_get_credit(self):
        position, pending = self.row(), self.row("PENDING", volume=".02")
        proof = SliceOverlap(self.account, position.reference, pending.reference, "0", "0", ".01", "link")
        for change in ({"side": "SELL"}, {"side": "UNKNOWN"}, {"entry": "4001"},
                       {"symbol": "OTHER.SYNTHETIC"}, {"margin_per_lot": "1001"}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "BASIS_OR_DIRECTION"):
                reconcile_exposures(self.account, (position, replace(pending, **change)), (proof,))
        with self.assertRaisesRegex(ValueError, "EXCEEDS_VOLUME_SLICE"):
            reconcile_exposures(self.account, (position, pending), (replace(proof, volume=".02"),))

    def test_notional_cap6000_vetoes_two4000_20_commitments(self):
        ledger = reconcile_exposures(self.account, (self.row(),))
        mapping = map_margin(self.account, ledger, MarginSnapshot(self.account, "10", "POST_OPEN_PRE_UNFILLED"))
        decision = check_capacity(ledger, mapping, "4000.20", "10", "6000")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reasons, ("NOTIONAL_CAP",))
        self.assertEqual(decision.total_notional, D("8000.40"))
        self.assertFalse(decision.can_execute)
        self.record("cap6000_vs8000_40", new_notional="4000.20", prior_notional=str(ledger.total_notional),
                    cap="6000", total_notional=str(decision.total_notional), reasons=list(decision.reasons))

    def test_open_margin_not_double_charged_but_every_unfilled_slice_is_reserved(self):
        open_only = reconcile_exposures(self.account, (self.row(),))
        open_map = map_margin(self.account, open_only, MarginSnapshot(self.account, "10", "POST_OPEN_PRE_UNFILLED"))
        self.assertTrue(check_capacity(open_only, open_map, "4000.20", "10", "20000").allowed)
        ledger = reconcile_exposures(self.account, (self.row(), self.row("PENDING", "pending-other")))
        insufficient = map_margin(self.account, ledger, MarginSnapshot(self.account, "15", "POST_OPEN_PRE_UNFILLED"))
        self.assertIn("MARGIN_CAP", check_capacity(ledger, insufficient, "4000.20", "10", "20000").reasons)
        exact = map_margin(self.account, ledger, MarginSnapshot(self.account, "20", "POST_OPEN_PRE_UNFILLED"))
        self.assertTrue(check_capacity(ledger, exact, "4000.20", "10", "20000").allowed)
        self.record("canonical_margin_open_not_double_charged", open_margin_already_reflected="10",
                    canonical_available="20", held_unfilled_margin=str(exact.held_unknown_margin), new_margin="10")

    def test_generic_free_margin_and_incomplete_pending_coverage_are_denied(self):
        ledger = reconcile_exposures(self.account, (self.row("PENDING"),))
        for snapshot, reason in ((MarginSnapshot(self.account, "15", "BROKER_FREE"), "UNVERIFIED_FREE_MARGIN"),
                                 (MarginSnapshot(self.account, "15", "FREE_AFTER_EXPLICIT_PENDING_DEBITS"), "COMPLETE_PENDING"),
                                 (MarginSnapshot(self.account, "15", "FREE_AFTER_EXPLICIT_PENDING_DEBITS", (), True), "MISSING_PENDING")):
            with self.subTest(basis=snapshot.basis, complete=snapshot.coverage_complete), self.assertRaisesRegex(ValueError, reason):
                map_margin(self.account, ledger, snapshot)

    def test_self_declared_ledger_or_margin_totals_are_not_accepted_as_derivation(self):
        ledger = reconcile_exposures(self.account, (self.row(),))
        snapshot = MarginSnapshot(self.account, "10", "POST_OPEN_PRE_UNFILLED")
        mapping = map_margin(self.account, ledger, snapshot)
        with self.assertRaisesRegex(ValueError, "DERIVED_CONTRACT_LEDGER"):
            map_margin(self.account, replace(ledger, known_notional=D("0")), snapshot)
        with self.assertRaisesRegex(ValueError, "DERIVED_MARGIN_MAPPING"):
            check_capacity(ledger, replace(mapping, available_margin=D("1000")), "4000.20", "20", "10000")
        with self.assertRaisesRegex(ValueError, "EXACT_DERIVED_DECIMAL"):
            replace(mapping, available_margin=10.0)
        with self.assertRaisesRegex(ValueError, "EXACT_DERIVED_DECIMAL"):
            replace(ledger, unfilled_margin=0.0)

    def test_explicit_reflected_pending_debit_is_added_back_and_deducted_once(self):
        pending = self.row("PENDING")
        ledger = reconcile_exposures(self.account, (self.row(), pending))
        proof = PendingMarginCoverage(pending.reference, "0", ".01", "10", "pending-debit")
        snapshot = MarginSnapshot(self.account, "10", "FREE_AFTER_EXPLICIT_PENDING_DEBITS", (proof,), True)
        mapping = map_margin(self.account, ledger, snapshot)
        self.assertEqual(mapping.available_margin, D("20"))
        self.assertEqual(mapping.reflected_pending_margin, D("10"))
        self.assertEqual(mapping.held_unknown_margin, D("10"))
        self.assertTrue(check_capacity(ledger, mapping, "4000.20", "10", "20000").allowed)
        self.record("explicit_pending_debit_normalization", reported_free="10", proven_pending_debit="10",
                    normalized_available=str(mapping.available_margin), held_unfilled=str(mapping.held_unknown_margin),
                    required_with_new="20", allowed=True)

    def test_margin_overlap_proof_cannot_cover_filled_slices_or_invent_credit(self):
        position, pending = self.row(), self.row("PENDING", volume=".02")
        link = SliceOverlap(self.account, position.reference, pending.reference, "0", "0", ".01", "fill-link")
        ledger = reconcile_exposures(self.account, (position, pending), (link,))
        valid = PendingMarginCoverage(pending.reference, ".01", ".01", "10", "debit")
        normalized = map_margin(self.account, ledger, MarginSnapshot(self.account, "10",
                                "FREE_AFTER_EXPLICIT_PENDING_DEBITS", (valid,), True))
        self.assertEqual(normalized.available_margin, D("20"))
        for proof, reason in ((replace(valid, start="0"), "FILLED_OR_INVALID_SLICE"),
                              (replace(valid, margin="11"), "AMOUNT_MISMATCH")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                map_margin(self.account, ledger, MarginSnapshot(self.account, "10",
                            "FREE_AFTER_EXPLICIT_PENDING_DEBITS", (proof,), True))
        with self.assertRaisesRegex(ValueError, "COVERAGE_REUSED"):
            map_margin(self.account, ledger, MarginSnapshot(self.account, "10",
                       "FREE_AFTER_EXPLICIT_PENDING_DEBITS", (valid, valid), True))
        with self.assertRaisesRegex(ValueError, "CANNOT_ADD_PENDING_CREDIT"):
            map_margin(self.account, ledger, MarginSnapshot(self.account, "20", "POST_OPEN_PRE_UNFILLED", (valid,)))

    def test_bid_ask_entry_and_closing_sides_are_explicit(self):
        quote = QuoteObservation("XAU.SYNTHETIC", "4000", "4000.20", 1000, 1005)
        prices = {(side, action): executable_price(quote, quote.symbol, side, action, 1010, 10)
                  for side in ("BUY", "SELL") for action in ("ENTRY", "CLOSE")}
        self.assertEqual(prices, {("BUY", "ENTRY"): D("4000.20"), ("BUY", "CLOSE"): D("4000"),
                                  ("SELL", "ENTRY"): D("4000"), ("SELL", "CLOSE"): D("4000.20")})
        self.record("executable_bid_ask_sides", bid="4000", ask="4000.20", observed_ms=1000,
                    now_ms=1010, max_age_ms=10, outcomes={side+"_"+action: str(value)
                                                      for (side, action), value in prices.items()})

    def test_stale_future_crossed_and_wrong_symbol_quotes_cannot_supply_price(self):
        quote = QuoteObservation("XAU.SYNTHETIC", "4000", "4000.20", 1000, 1005)
        for symbol, now, age in (("OTHER", 1010, 10), (quote.symbol, 1011, 10), (quote.symbol, 1004, 10)):
            with self.subTest(symbol=symbol, now=now), self.assertRaises(ValueError):
                executable_price(quote, symbol, "BUY", "ENTRY", now, age)
        with self.assertRaises(ValueError):
            replace(quote, ask="3999")

    def test_injected_dst_fold_requires_explicit_choice_and_gap_is_denied(self):
        fall = SessionCalendar("SYNTHETIC_FALL_BACK", 1,
                (OffsetPeriod(0, 2*HOUR, 120), OffsetPeriod(2*HOUR, 4*HOUR, 60)),
                (SessionWindow(3*HOUR, 4*HOUR),))
        local = 7*HOUR//2
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_LOCAL_TIME"):
            local_to_utc(fall, local)
        first, second = local_to_utc(fall, local, 0), local_to_utc(fall, local, 1)
        self.assertEqual((first, second), (3*HOUR//2, 5*HOUR//2))
        self.assertTrue(session_allows_entry(fall, first)[0])
        self.assertTrue(session_allows_entry(fall, second)[0])
        spring = SessionCalendar("SYNTHETIC_SPRING_FORWARD", 1,
                (OffsetPeriod(0, 2*HOUR, 60), OffsetPeriod(2*HOUR, 4*HOUR, 120)),
                (SessionWindow(HOUR, 6*HOUR),))
        with self.assertRaisesRegex(ValueError, "NONEXISTENT_OR_UNKNOWN"):
            local_to_utc(spring, local)
        self.record("injected_dst_fold_and_gap", local_ms=local, first_fold_utc_ms=first,
                    second_fold_utc_ms=second, ambiguous_without_fold="DENIED", spring_gap="DENIED",
                    host_timezone_used=False, real_broker_calendar_verified=False)

    def test_unknown_or_closed_session_and_bad_offset_schedule_deny_entry(self):
        calendar = SessionCalendar("SYNTHETIC", 1, (OffsetPeriod(0, HOUR, 0),),
                                   (SessionWindow(0, HOUR//2),))
        self.assertTrue(session_allows_entry(calendar, 0)[0])
        self.assertEqual(session_allows_entry(calendar, HOUR//2), (False, "INJECTED_SESSION_CLOSED"))
        self.assertEqual(session_allows_entry(calendar, HOUR), (False, "UNKNOWN_UTC_OFFSET"))
        self.assertEqual(session_allows_entry(replace(calendar, complete=False), 0), (False, "UNKNOWN_SESSION_CALENDAR"))
        with self.assertRaisesRegex(ValueError, "OVERLAPPING_UTC"):
            replace(calendar, offsets=(OffsetPeriod(0, HOUR, 0), OffsetPeriod(HOUR//2, 2*HOUR, 60)))

    def test_synthetic_stop_requires_current_owned_position_but_never_confirms_broker(self):
        position = self.row(position_revision=2)
        observation = StopObservation(self.account, position.reference, position.symbol, 2, 1000, "3995", True)
        self.assertTrue(synthetic_stop_observed(self.account, position, observation, 1010, 10))
        self.assertFalse(observation.broker_protection_confirmed)
        self.assertEqual(observation.evidence_source, "OFFLINE_SYNTHETIC")
        self.assertFalse(synthetic_stop_observed(self.account, position, replace(observation, complete=False), 1010, 10))
        self.assertFalse(synthetic_stop_observed(self.account, position, observation, 1011, 10))
        self.assertFalse(synthetic_stop_observed(self.account, position, observation, 999, 10))
        with self.assertRaisesRegex(ValueError, "REVISION_MISMATCH"):
            synthetic_stop_observed(self.account, position, replace(observation, position_revision=1), 1010, 10)
        with self.assertRaises(TypeError):
            StopObservation(self.account, position.reference, position.symbol, 2, 1000, "3995", True,
                            broker_protection_confirmed=True)
        self.record("synthetic_stop_provenance", position_revision=2, synthetic_observed=True,
                    broker_protection_confirmed=False, stale_or_incomplete_observation=False)

    def test_net_cost_evidence_conserves_cash_and_duplicate_deal_charges_once(self):
        proof = NetCostEvidence(self.account, TypedRef("DEAL", "shared-text-id"), "net-cost-1",
                                "-1.50", "-.30", "-.30", "0", "-2.10", True)
        self.assertEqual(confirmed_net_total(self.account, (proof, proof)), D("-2.10"))
        with self.assertRaisesRegex(ValueError, "CONFLICTING_DEAL"):
            confirmed_net_total(self.account, (proof, replace(proof, gross="-2.50", net="-3.10")))
        with self.assertRaisesRegex(ValueError, "REUSED_ACROSS_DEALS"):
            confirmed_net_total(self.account, (proof, replace(proof, deal=TypedRef("DEAL", "other-deal"))))
        with self.assertRaisesRegex(ValueError, "CONFIRMED_NET_COSTS"):
            replace(proof, confirmed=False)
        with self.assertRaisesRegex(ValueError, "CONSERVATION"):
            replace(proof, net="-1.50")
        self.record("net_cost_charge_once", gross="-1.50", allocated_entry_fee="-.30", exit_fee="-.30",
                    swap="0", net="-2.10", repeated_deal_total="-2.10")

    def test_unknown_float_nonfinite_and_mutable_inputs_fail_closed(self):
        for value in (None, 0.01, True, "NaN", "Infinity", "-1"):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                self.row(volume=value)
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_CONTRACT_TUPLE"):
            reconcile_exposures(self.account, [self.row()])
        with self.assertRaisesRegex(ValueError, "INVALID_EXPOSURE"):
            self.row(kind="DEAL")

    def test_ambient_decimal_precision_cannot_change_long_notional(self):
        row = self.row(entry="4000.123456789012345678901234567890")
        with localcontext() as context:
            context.prec = 1024
            exact = row.volume * row.entry * row.contract * 2
        with localcontext() as context:
            context.prec = 3
            ledger = reconcile_exposures(self.account, (row, replace(row, reference=TypedRef("UNKNOWN", "other"))))
            self.assertEqual(ledger.total_notional, exact)


if __name__ == "__main__":
    unittest.main()
