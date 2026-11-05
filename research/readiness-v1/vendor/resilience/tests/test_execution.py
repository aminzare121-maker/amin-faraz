"""Synthetic, in-memory scenarios; these tests cannot connect to any broker."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import unittest

from faraz_core.authorization import EntryAuthorization, authorize_entry, pin_policy
from faraz_core.decision import EntryContext
from faraz_core.risk import ExposureAmount, VolumeRules, LinearRiskModel, RiskRequest
from faraz_core.temporal import Quote
from faraz_core.execution import (
    BrokerEvent, DemoBinding, Intent, MemoryExecutor, MockBroker, Phase,
    acknowledge_stop, apply_event, approve, observe_stop, propose, propose_stop,
    recover, replay, reserve, send_synthetic, start, timeout, update_context,
    intent_from_authorization,
)


class ExecutionTests(unittest.TestCase):
    def intent(self, key="intent-1", side="BUY", volume="0.05", **changes):
        # Build genuine decisions for every normal execution fixture. The ID is
        # derived by decide_entry; labels are just human-readable test aliases.
        amount = Decimal(volume) if not isinstance(volume, float) else volume
        if isinstance(amount, float):
            return Intent(key, "synthetic-demo", 1, "SYNTH", side, amount, "550", "100", "95")
        risk_per_lot = Decimal(changes.pop("risk_per_lot", "550"))
        with localcontext() as context:
            context.prec = 512
            budget = amount * risk_per_lot
            extra_cost = risk_per_lot - Decimal("500")
        step = Decimal(1).scaleb(min(-2, amount.as_tuple().exponent))
        request = RiskRequest("synthetic-demo", "SYNTH", side, "100",
                              "95" if side == "BUY" else "105", budget,
                              VolumeRules(step, step, "1", "2"),
                              LinearRiskModel("100", extra_cost, "0", "0", "0", "1000"),
                              (), "100000", "1000000", "1000", "0", "0", "0", "0", "0")
        quote = Quote(1000, 1000, "99.9", "100") if side == "BUY" else Quote(1000, 1000, "100", "100.1")
        context = EntryContext(1000, "synthetic-demo", "synthetic-demo", 1, 1,
                               "DEMO", "USD", "HEDGING", True, True, True, True, 1000,
                               True, 1000, True, 1000, 1000, quote, key, 1000, side,
                               "test-policy-v1", ".01", "0", ".5", "0", "1000", "0",
                               "1000", 0, 100, "SYNTH", 1, 1000)
        authorization = authorize_entry(context, request, 2000)
        intent = intent_from_authorization(authorization, pin_policy(context, request))
        if not hasattr(self, "keys"):
            self.keys = {}
        self.keys[key] = intent.client_intent_id
        return replace(intent, **changes) if changes else intent

    def key(self, label):
        if not hasattr(self, "keys") or label not in self.keys:
            self.intent(label)
        return self.keys[label]

    def binding(self, intent=None, **changes):
        intent = intent or self.intent()
        authorization = intent.authorization
        return DemoBinding("synthetic-demo", 1,
                           policy=pin_policy(authorization.context, authorization.request),
                           budget_epoch_id="test-fixed-epoch", epoch_risk_limit="1000", **changes)

    def send(self, state, key):
        return send_synthetic(state, key, state.get(key).intent.authorization, 1000)

    def mock_send(self, executor, broker, key):
        return executor.send(broker, key, executor.state.get(key).intent.authorization, 1000)

    def reserved(self, intent=None, total="100", same_side="100", epoch="1000"):
        intent = intent or self.intent()
        state = propose(start(replace(self.binding(intent), epoch_risk_limit=epoch)), intent)
        state = approve(state, intent.client_intent_id, intent.requested_risk)
        return reserve(state, intent.client_intent_id, total, same_side)

    def event(self, event_id="fill-1", sequence=1, kind="FILL", fill="0.03", **changes):
        arguments = dict(event_id=event_id, client_intent_id=self.key("intent-1"), sequence=sequence,
                         kind=kind, account_id="synthetic-demo", account_revision=1,
                         cumulative_filled=fill, order_id="broker-order-77")
        if kind == "FILL":
            arguments.update(deal_id="broker-deal-91", position_id="broker-position-8")
        arguments.update(changes)
        return BrokerEvent(**arguments)

    def partial(self, side="BUY"):
        state = self.send(self.reserved(self.intent(side=side)), self.key("intent-1"))
        return apply_event(state, self.event())

    def full(self, volume="0.05", epoch="1000"):
        state = self.send(self.reserved(self.intent(volume=volume), epoch=epoch), self.key("intent-1"))
        return apply_event(state, self.event(fill=volume))

    def close(self, key="close-1", sequence=2, volume="0.01", pnl="-2", **changes):
        arguments = dict(deal_id=key, position_id="broker-position-8", close_volume=volume,
                         realized_pnl=pnl, authoritative=True, terminal_proof=True,
                         net_costs_confirmed=True, net_pnl_provenance="SYNTHETIC_CONFIRMED_NET",
                         cost_evidence_id="net-costs-" + key, close_order_id="close-order-" + key,
                         budget_epoch_id="test-fixed-epoch")
        arguments.update(changes)
        return self.event("event-" + key, sequence, "CLOSE", fill=None, **arguments)

    def test_partial_fill_keeps_the_whole_budget_until_definitive_cancel(self):
        state = self.reserved()
        self.assertEqual(state.ledger.reserved_risk, Decimal("27.50"))
        state = self.send(state, self.key("intent-1"))
        state = apply_event(state, self.event())
        self.assertEqual(state.get(self.key("intent-1")).phase, Phase.UNKNOWN)
        self.assertEqual(state.ledger.open_risk, Decimal("16.50"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("11.00"))
        self.assertEqual(state.ledger.total, Decimal("27.50"))
        unproven = self.event("cancel-no-proof", 2, "CANCELLED")
        state = apply_event(state, unproven)
        self.assertEqual(state.ledger.unknown_risk, Decimal("11.00"))
        self.assertEqual(state.quarantined[-1].reason, "TERMINAL_PROOF_REQUIRED")
        proven = self.event("cancel-proven", 3, "CANCELLED", terminal_proof=True)
        state = apply_event(state, proven)
        self.assertEqual(state.ledger.total, Decimal("16.50"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("0"))
        self.assertEqual(state.get(self.key("intent-1")).terminal_status, "CANCELLED")

    def test_crash_or_timeout_after_reserve_requires_reconciliation_before_release(self):
        for operation in (lambda value: timeout(value, self.key("intent-1")), recover):
            state = operation(self.reserved())
            self.assertEqual(state.get(self.key("intent-1")).phase, Phase.UNKNOWN)
            self.assertEqual(state.ledger.unknown_risk, Decimal("27.50"))
            self.assertEqual(state.requests, ())
            with self.assertRaisesRegex(ValueError, "NO_RESEND"):
                self.send(state, self.key("intent-1"))
            state = apply_event(state, self.event("no-send", 1, "RECONCILE", fill="0",
                                                  order_id=None, authoritative=True,
                                                  terminal_proof=True, terminal_status="NOT_SENT"))
            self.assertEqual(state.ledger.total, Decimal("0"))
            self.assertEqual(state.get(self.key("intent-1")).phase, Phase.RECONCILED)
            self.assertEqual(replay(state.trace), state)

    def test_recovered_reservation_unproven_no_send_snapshot_cannot_release(self):
        state = recover(self.reserved())
        state = apply_event(state, self.event("unproven-no-send", 1, "RECONCILE", fill="0",
                                              order_id=None, authoritative=True,
                                              terminal_status="NOT_SENT"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("27.50"))
        self.assertEqual(state.quarantined[-1].reason, "INVALID_RECONCILIATION_PROOF")

    def test_uncertain_send_cannot_retry_even_after_logical_restart(self):
        executor = MemoryExecutor(trace=self.reserved().trace)
        broker = MockBroker(lose_response=True)
        self.mock_send(executor, broker, self.key("intent-1"))
        self.assertEqual(len(broker.attempted), 1)
        self.assertEqual(executor.state.get(self.key("intent-1")).phase, Phase.UNKNOWN)
        self.assertEqual(executor.state.ledger.unknown_risk, Decimal("27.50"))
        executor = MemoryExecutor(trace=executor.state.trace)
        executor.transition("recover")
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            self.mock_send(executor, broker, self.key("intent-1"))
        self.assertEqual(len(broker.attempted), 1)

    def test_recovery_of_sent_outcome_retains_risk_and_invalidates_stop_currency(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        restored = recover(replay(state.trace))
        self.assertEqual(restored.get(self.key("intent-1")).phase, Phase.UNKNOWN)
        self.assertEqual(restored.ledger.total, state.ledger.total)
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            self.send(restored, self.key("intent-1"))

    def test_idempotency_key_rejects_changed_payload_without_creating_another_intent(self):
        state = self.reserved()
        self.assertIs(propose(state, self.intent()), state)
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_PAYLOAD_CONFLICT"):
            propose(state, self.intent(volume="0.06"))
        self.assertEqual(len(state.intents), 1)
        self.assertEqual(state.ledger.total, Decimal("27.50"))

    def test_idempotency_key_includes_full_payload_fingerprint(self):
        state = self.reserved()
        with self.assertRaisesRegex(ValueError, "IDEMPOTENCY_PAYLOAD_CONFLICT"):
            propose(state, self.intent(payload_hash="policy-and-context-v2"))
        state = self.send(state, self.key("intent-1"))
        self.assertEqual(state.requests[-1].payload_hash, state.get(self.key("intent-1")).intent.payload_hash)

    def test_exact_duplicate_event_is_ignored_and_conflicting_duplicate_rejected(self):
        state = self.partial()
        self.assertIs(apply_event(state, self.event()), state)
        with self.assertRaisesRegex(ValueError, "EVENT_ID_PAYLOAD_CONFLICT"):
            apply_event(state, self.event(fill="0.04"))
        self.assertEqual(state.get(self.key("intent-1")).filled_volume, Decimal("0.03"))

    def test_out_of_order_cancel_cannot_release_and_authoritative_snapshot_can(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        state = apply_event(state, self.event(sequence=3))
        old_cancel = self.event("old-cancel", 2, "CANCELLED", terminal_proof=True)
        state = apply_event(state, old_cancel)
        self.assertEqual(state.quarantined[-1].reason, "OUT_OF_ORDER")
        self.assertEqual(state.ledger.total, Decimal("27.50"))
        snapshot = self.event("snapshot", 4, "RECONCILE", terminal_status="CANCELLED",
                              authoritative=True, terminal_proof=True)
        state = apply_event(state, snapshot)
        self.assertEqual(state.ledger.total, Decimal("16.50"))
        self.assertEqual(replay(state.trace), state)

    def test_contradictory_late_fill_revokes_a_prior_terminal_release(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        cancellation = self.event("cancel-before-fill", 2, "CANCELLED", fill="0",
                                  terminal_proof=True)
        state = apply_event(state, cancellation)
        self.assertEqual(state.ledger.total, Decimal("0"))
        state = apply_event(state, self.event())
        self.assertEqual(state.get(self.key("intent-1")).phase, Phase.UNKNOWN)
        self.assertEqual(state.ledger.total, Decimal("27.50"))
        self.assertEqual(state.get(self.key("intent-1")).filled_volume, Decimal("0"))
        state = apply_event(state, self.event("reconcile", 3, "RECONCILE",
                                              authoritative=True, terminal_proof=True,
                                              terminal_status="CANCELLED"))
        self.assertEqual(state.ledger.open_risk, Decimal("16.50"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("0"))

    def test_decreasing_or_excess_cumulative_fill_is_quarantined(self):
        state = self.partial()
        for index, fill in enumerate(("0.01", "0.06"), 2):
            state = apply_event(state, self.event(f"bad-{index}", index, fill=fill))
            self.assertEqual(state.quarantined[-1].reason, "INCONSISTENT_CUMULATIVE_FILL")
            self.assertEqual(state.ledger.total, Decimal("27.50"))
            self.assertEqual(state.get(self.key("intent-1")).filled_volume, Decimal("0.03"))

    def test_order_identity_conflict_cannot_reassign_a_managed_position(self):
        state = self.partial()
        state = apply_event(state, self.event("foreign-order", 2, fill="0.05",
                                              order_id="different-order"))
        self.assertEqual(state.quarantined[-1].reason, "ORDER_ID_MISMATCH")
        self.assertEqual(state.get(self.key("intent-1")).order_id, "broker-order-77")
        self.assertEqual(state.ledger.total, Decimal("27.50"))

    def test_same_deal_id_with_another_event_id_cannot_manufacture_an_extra_fill(self):
        state = self.partial()
        state = apply_event(state, self.event("same-deal-new-event", 2, fill="0.04"))
        self.assertEqual(state.quarantined[-1].reason, "DEAL_ID_PAYLOAD_CONFLICT")
        self.assertEqual(state.get(self.key("intent-1")).filled_volume, Decimal("0.03"))
        self.assertEqual(state.ledger.open_risk, Decimal("16.50"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("11.00"))
        self.assertEqual(replay(state.trace), state)

    def test_wrong_account_and_unsent_events_cannot_book_a_fill(self):
        state = self.reserved()
        state = apply_event(state, self.event(account_id="other-account"))
        self.assertEqual(state.quarantined[-1].reason, "EVENT_ACCOUNT_MISMATCH")
        state = apply_event(state, self.event("unsent"))
        self.assertEqual(state.quarantined[-1].reason, "UNSENT_INTENT")
        self.assertEqual(state.ledger.open_risk, Decimal("0"))
        self.assertEqual(state.ledger.reserved_risk, Decimal("27.50"))

    def test_full_fill_retains_all_open_risk_without_a_retry(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        state = apply_event(state, self.event(fill="0.05"))
        record = state.get(self.key("intent-1"))
        self.assertEqual(record.phase, Phase.RECONCILED)
        self.assertEqual(state.ledger.open_risk, Decimal("27.50"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("0"))
        self.assertEqual(record.intent.client_intent_id, self.key("intent-1"))
        self.assertEqual(record.order_id, "broker-order-77")
        self.assertEqual(record.deal_ids, ("broker-deal-91",))
        self.assertEqual(record.position_ids, ("broker-position-8",))
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            self.send(state, self.key("intent-1"))

    def test_rejection_requires_explicit_zero_fill_terminal_evidence(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        state = apply_event(state, self.event("reject-unproven", 1, "REJECTED", fill="0",
                                              order_id=None))
        self.assertEqual(state.ledger.total, Decimal("27.50"))
        state = apply_event(state, self.event("reject-proof", 2, "REJECTED", fill="0",
                                              order_id=None, terminal_proof=True))
        self.assertEqual(state.ledger.total, Decimal("0"))

    def test_replay_restores_attempts_quarantine_ledger_and_protection_exactly(self):
        state = self.partial()
        state = observe_stop(state, self.key("intent-1"), "95")
        state = propose_stop(state, self.key("intent-1"), "97", "101", "1")
        state = acknowledge_stop(state, self.key("intent-1"), "97")
        state = apply_event(state, self.event("old", 1, "ACK", fill=None))
        restored = replay(state.trace)
        self.assertEqual(restored, state)
        self.assertEqual(restored.requests, state.requests)
        self.assertEqual(restored.quarantined, state.quarantined)
        self.assertEqual(restored.get(self.key("intent-1")).protection.observed_stop, Decimal("95"))
        with self.assertRaises(FrozenInstanceError):
            restored.binding.revision = 9

    def test_account_revision_change_blocks_reserved_action_without_freeing_risk(self):
        state = self.reserved()
        state = update_context(state, replace(state.binding, revision=2))
        with self.assertRaisesRegex(ValueError, "ACCOUNT_REVISION_CHANGED"):
            self.send(state, self.key("intent-1"))
        self.assertEqual(state.requests, ())
        self.assertEqual(state.ledger.total, Decimal("27.50"))
        with self.assertRaisesRegex(ValueError, "ACCOUNT_REVISION_REGRESSION"):
            update_context(state, replace(state.binding, revision=1))

    def test_switching_away_and_back_does_not_reenable_old_bound_intent(self):
        state = self.reserved()
        state = update_context(state, replace(state.binding, account_id="another-demo"))
        state = update_context(state, replace(state.binding, account_id="synthetic-demo"))
        with self.assertRaisesRegex(ValueError, "ACCOUNT_REVISION_CHANGED"):
            self.send(state, self.key("intent-1"))

    def test_live_non_synthetic_unmanaged_and_netting_paths_are_refused(self):
        for changes in ({"mode": "LIVE"}, {"synthetic": False}):
            with self.assertRaisesRegex(ValueError, "SYNTHETIC_DEMO_ONLY"):
                DemoBinding("anything", 1, **changes)
        for changes in ({"unmanaged_positions": True}, {"netting_ambiguous": True},
                        {"position_mode": "NETTING"}):
            state = start(DemoBinding("synthetic-demo", 1, **changes))
            with self.assertRaises(ValueError):
                propose(state, self.intent())
        executor = MemoryExecutor(trace=self.reserved().trace)
        with self.assertRaisesRegex(ValueError, "MOCK_BROKER_ONLY"):
            executor.send(object(), self.key("intent-1"))
        self.assertEqual(executor.state.requests, ())

    def test_disconnected_stale_and_revised_context_invalidate_observation_not_history(self):
        for changes in ({"connected": False}, {"fresh": False}, {"revision": 2}):
            state = observe_stop(self.partial(), self.key("intent-1"), "95")
            binding = replace(state.binding, **changes)
            state = update_context(state, binding)
            protection = state.get(self.key("intent-1")).protection
            self.assertEqual(protection.observed_stop, Decimal("95"))
            self.assertEqual(protection.observed_history, (Decimal("95"),))
            self.assertFalse(protection.synthetic_protected)
            with self.assertRaises(ValueError):
                propose_stop(state, self.key("intent-1"), "97", "101")

    def test_proposed_and_acknowledged_stop_do_not_claim_server_observation(self):
        state = self.partial()
        protection = state.get(self.key("intent-1")).protection
        self.assertEqual(protection.proposed_stop, Decimal("95"))
        self.assertIsNone(protection.acknowledged_stop)
        self.assertIsNone(protection.observed_stop)
        state = propose_stop(state, self.key("intent-1"), "97", "101")
        state = acknowledge_stop(state, self.key("intent-1"), "97")
        self.assertFalse(state.get(self.key("intent-1")).protection.synthetic_protected)
        state = observe_stop(state, self.key("intent-1"), "97")
        self.assertTrue(state.get(self.key("intent-1")).protection.synthetic_protected)

    def test_partial_position_updates_preserve_a_previously_observed_server_stop(self):
        state = observe_stop(self.partial(), self.key("intent-1"), "95")
        self.assertIs(observe_stop(state, self.key("intent-1")), state)
        state = apply_event(state, self.event("ack-later", 2, "ACK", fill=None))
        protection = state.get(self.key("intent-1")).protection
        self.assertEqual(protection.observed_stop, Decimal("95"))
        self.assertTrue(protection.synthetic_protected)
        state = observe_stop(state, self.key("intent-1"), complete=True)
        protection = state.get(self.key("intent-1")).protection
        self.assertFalse(protection.synthetic_protected)
        self.assertEqual(protection.observed_stop, Decimal("95"))
        self.assertEqual(protection.safety_fault, "SERVER_STOP_NOT_PRESENT")

    def test_stop_tightening_has_same_side_distance_and_nonweakening_bounds(self):
        for side, safe, weak, wrong, close, price in (
                ("BUY", "98", "97", "102", "100.5", "101"),
                ("SELL", "102", "103", "98", "99.5", "99")):
            state = self.partial(side)
            state = propose_stop(state, self.key("intent-1"), safe, price, "1")
            with self.assertRaisesRegex(ValueError, "STOP_WEAKENING_FORBIDDEN"):
                propose_stop(state, self.key("intent-1"), weak, price, "1")
            for invalid in (wrong, close):
                with self.assertRaisesRegex(ValueError, "STOP_WRONG_SIDE_OR_DISTANCE"):
                    propose_stop(state, self.key("intent-1"), invalid, price, "1")
            with self.assertRaisesRegex(ValueError, "UNPROPOSED_STOP_ACK"):
                acknowledge_stop(state, self.key("intent-1"), weak)

    def test_weaker_server_evidence_is_retained_and_revokes_protection_claim(self):
        state = observe_stop(self.partial(), self.key("intent-1"), "98")
        state = observe_stop(state, self.key("intent-1"), "97")
        protection = state.get(self.key("intent-1")).protection
        self.assertEqual(protection.observed_stop, Decimal("97"))
        self.assertEqual(protection.observed_history, (Decimal("98"), Decimal("97")))
        self.assertFalse(protection.synthetic_protected)
        self.assertEqual(protection.safety_fault, "SERVER_STOP_WEAKENED")
        with self.assertRaisesRegex(ValueError, "STOP_WEAKENING_FORBIDDEN"):
            propose_stop(state, self.key("intent-1"), "97.5", "101")
        state = observe_stop(state, self.key("intent-1"), "98")
        self.assertTrue(state.get(self.key("intent-1")).protection.synthetic_protected)

    def test_multiple_position_ids_cannot_be_managed_as_one_stop(self):
        state = observe_stop(self.partial(), self.key("intent-1"), "95")
        state = apply_event(state, self.event("second-position", 2, fill="0.04",
                                              deal_id="second-deal", position_id="position-2"))
        self.assertFalse(state.get(self.key("intent-1")).protection.synthetic_protected)
        self.assertEqual(state.get(self.key("intent-1")).protection.observed_stop, Decimal("95"))
        with self.assertRaisesRegex(ValueError, "UNAMBIGUOUS_MANAGED_POSITION_REQUIRED"):
            propose_stop(state, self.key("intent-1"), "98", "101")

    def test_new_cumulative_fill_without_position_identity_needs_authoritative_mapping(self):
        state = observe_stop(self.partial(), self.key("intent-1"), "95")
        state = apply_event(state, self.event("cancel-plus-unseen-fill", 2, "CANCELLED",
                                              fill="0.04", terminal_proof=True))
        self.assertEqual(state.ledger.open_risk, Decimal("22.00"))
        self.assertFalse(state.get(self.key("intent-1")).protection.synthetic_protected)
        with self.assertRaisesRegex(ValueError, "UNAMBIGUOUS_MANAGED_POSITION_REQUIRED"):
            observe_stop(state, self.key("intent-1"), "98")
        state = apply_event(state, self.event("position-proof", 3, "RECONCILE", fill="0.04",
                                              terminal_status="CANCELLED", terminal_proof=True,
                                              authoritative=True, position_id="broker-position-8"))
        state = observe_stop(state, self.key("intent-1"), "98")
        self.assertTrue(state.get(self.key("intent-1")).protection.synthetic_protected)

    def test_total_and_same_side_risk_bounds_count_unresolved_reservations(self):
        state = self.partial()
        second = self.intent("intent-2")
        state = approve(propose(state, second), self.key("intent-2"), "27.5")
        with self.assertRaisesRegex(ValueError, "SAME_SIDE_RISK_LIMIT"):
            reserve(state, self.key("intent-2"), "100", "50")
        with self.assertRaisesRegex(ValueError, "TOTAL_RISK_LIMIT"):
            reserve(state, self.key("intent-2"), "50", "100")
        state = reserve(state, self.key("intent-2"), "55", "55")
        self.assertEqual(state.ledger.total, Decimal("55"))

    def test_opposite_side_does_not_consume_same_side_limit_but_counts_total(self):
        state = self.reserved()
        opposite = self.intent("opposite", side="SELL")
        state = approve(propose(state, opposite), self.key("opposite"), "27.5")
        state = reserve(state, self.key("opposite"), "55", "27.5")
        self.assertEqual(state.ledger.total, Decimal("55"))

    def test_unapproved_or_mismatched_risk_cannot_reserve_or_send(self):
        intent = self.intent()
        state = propose(start(self.binding(intent)), intent)
        with self.assertRaisesRegex(ValueError, "RISK_APPROVAL_MISMATCH"):
            approve(state, self.key("intent-1"), "20")
        with self.assertRaisesRegex(ValueError, "RISK_APPROVAL_REQUIRED"):
            reserve(state, self.key("intent-1"), "100", "100")
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            self.send(state, self.key("intent-1"))
        self.assertEqual(state.ledger.total, Decimal("0"))

    def test_exact_arithmetic_does_not_round_a_large_precision_reservation_down(self):
        intent = self.intent(volume="0.12345678901234567890123456789", risk_per_lot="1000")
        state = self.reserved(intent, total="1000", same_side="1000")
        self.assertEqual(state.ledger.total, Decimal("123.45678901234567890123456789"))
        with self.assertRaises(ValueError):
            self.intent(volume=0.05)

    def test_malformed_response_cannot_roll_back_the_already_attempted_send(self):
        first = self.event("same-id", 1)
        conflicting = self.event("same-id", 2, fill="0.04")
        broker = MockBroker((first, conflicting))
        executor = MemoryExecutor(trace=self.reserved().trace)
        with self.assertRaisesRegex(ValueError, "EVENT_ID_PAYLOAD_CONFLICT"):
            self.mock_send(executor, broker, self.key("intent-1"))
        self.assertEqual(executor.state.ledger.total, Decimal("27.50"))
        self.assertEqual(len(executor.state.requests), 1)
        self.assertEqual(len(broker.attempted), 1)
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            self.mock_send(executor, broker, self.key("intent-1"))
        self.assertEqual(len(broker.attempted), 1)

    def test_mock_event_script_is_synthetic_and_completely_replayable(self):
        events = (self.event(), self.event("cancel", 2, "CANCELLED", terminal_proof=True))
        executor = MemoryExecutor(trace=self.reserved().trace)
        broker = MockBroker(events)
        self.mock_send(executor, broker, self.key("intent-1"))
        self.assertEqual(executor.state.ledger.total, Decimal("16.50"))
        self.assertEqual(replay(executor.state.trace), executor.state)
        self.assertTrue(broker.attempted[0].synthetic)
        self.assertEqual(broker.attempted[0].client_intent_id, self.key("intent-1"))

    def test_raw_low_risk_intent_with_invented_hash_cannot_send(self):
        raw = Intent("invented-id", "synthetic-demo", 1, "SYNTH", "BUY",
                     "1", ".001", "100", "95", "self-claimed-approved-hash")
        state = propose(start(DemoBinding("synthetic-demo", 1)), raw)
        state = approve(state, raw.client_intent_id, ".001")
        state = reserve(state, raw.client_intent_id, "100", "100")
        with self.assertRaisesRegex(ValueError, "VALIDATED_ENTRY_AUTHORIZATION_REQUIRED"):
            send_synthetic(state, raw.client_intent_id, now_ms=1000)
        executor = MemoryExecutor(trace=state.trace)
        broker = MockBroker()
        with self.assertRaisesRegex(ValueError, "VALIDATED_ENTRY_AUTHORIZATION_REQUIRED"):
            executor.send(broker, raw.client_intent_id, now_ms=1000)
        self.assertEqual(broker.attempted, ())
        self.assertEqual(executor.state.requests, ())

    def test_send_recomputes_original_even_after_volume_stop_or_hash_tampering(self):
        state = self.reserved()
        record = state.get(self.key("intent-1"))
        for changes in ({"volume": Decimal(".06")}, {"initial_sl": Decimal("94")},
                        {"risk_per_lot": Decimal("1")}, {"payload_hash": "forged"}):
            tampered = replace(record, intent=replace(record.intent, **changes))
            attacked = replace(state, intents=(tampered,))
            with self.assertRaisesRegex(ValueError, "INTENT_AUTHORIZATION_MISMATCH"):
                self.send(attacked, self.key("intent-1"))
            self.assertEqual(attacked.requests, ())

    def test_constructed_authorization_for_no_trade_cannot_send(self):
        state = self.reserved()
        record = state.get(self.key("intent-1"))
        original = record.intent.authorization
        bad = EntryAuthorization(replace(original.context, signal_side=None), original.request, 2000)
        attacked = replace(state, intents=(replace(record, intent=replace(record.intent, authorization=bad)),))
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_NO_TRADE"):
            self.send(attacked, self.key("intent-1"))

    def test_send_requires_explicit_current_recheck_and_original_expiry(self):
        state = self.reserved()
        key = self.key("intent-1")
        with self.assertRaisesRegex(ValueError, "EXPLICIT_FRESH"):
            send_synthetic(state, key)
        authorization = state.get(key).intent.authorization
        context = replace(authorization.context, decision_ms=2001, account_observed_ms=2001,
                          session_available_ms=2001, news_available_ms=2001,
                          signal_available_ms=2001, risk_observed_ms=2001,
                          quote=Quote(2001, 2001, "99.9", "100"))
        fresh = authorize_entry(context, authorization.request, 3000)
        with self.assertRaisesRegex(ValueError, "AUTHORIZATION_EXPIRED"):
            send_synthetic(state, key, fresh, 2001)
        self.assertEqual(state.requests, ())

    def test_later_fresh_check_can_advance_time_without_rewriting_original_payload(self):
        state = self.reserved()
        key = self.key("intent-1")
        authorization = state.get(key).intent.authorization
        fresh = authorize_entry(replace(authorization.context, decision_ms=1100,
                                        quote=Quote(1100, 1100, "99.9", "100"),
                                        account_observed_ms=1100, risk_observed_ms=1100),
                                 authorization.request, 2000)
        state = send_synthetic(state, key, fresh, 1100)
        self.assertEqual(state.requests[-1].payload_hash, state.get(key).intent.payload_hash)
        self.assertEqual(replay(state.trace), state)

    def test_same_policy_hash_cannot_hide_relaxed_rules_at_send(self):
        state = self.reserved()
        key = self.key("intent-1")
        authorization = state.get(key).intent.authorization
        relaxed = authorize_entry(replace(authorization.context, max_spread="100"),
                                  authorization.request, 2000)
        with self.assertRaisesRegex(ValueError, "PINNED_POLICY_MISMATCH"):
            send_synthetic(state, key, relaxed, 1000)

    def test_changed_executable_quote_or_disconnected_recheck_cannot_send(self):
        state = self.reserved()
        key = self.key("intent-1")
        authorization = state.get(key).intent.authorization
        for changes in ({"connected": False}, {"quote": Quote(1000, 1000, "100", "100.1")}):
            fresh = EntryAuthorization(replace(authorization.context, **changes), authorization.request, 2000)
            with self.assertRaisesRegex(ValueError, "NO_TRADE"):
                send_synthetic(state, key, fresh, 1000)

    def test_fresh_snapshot_cannot_omit_existing_open_and_unknown_risk(self):
        state = self.partial()
        second = self.intent("intent-2")
        state = reserve(approve(propose(state, second), second.client_intent_id, "27.5"),
                        second.client_intent_id, "100", "100")
        with self.assertRaisesRegex(ValueError, "UNDERREPORTS_HELD_EXPOSURE"):
            self.send(state, second.client_intent_id)
        original = second.authorization
        request = replace(original.request, held_risk="16.5", held_unknown_risk="11",
                          held_notional="300", held_unknown_notional="200", held_unknown_margin="20",
                          exposures=(ExposureAmount("synthetic-demo", "SYNTH", "BUY", "UNKNOWN",
                                                    "first-held-order", ".05"),))
        fresh = authorize_entry(replace(original.context, positions_and_pending=1), request, 2000)
        state = send_synthetic(state, second.client_intent_id, fresh, 1000)
        self.assertEqual(len(state.requests), 2)

    def test_partial_and_full_close_release_only_confirmed_slices_and_charge_net_loss(self):
        state = apply_event(self.full(), self.close(volume=".02", pnl="-6"))
        self.assertEqual(state.get(self.key("intent-1")).closed_volume, Decimal(".02"))
        self.assertEqual(state.ledger.open_risk, Decimal("16.5"))
        self.assertEqual(state.budget.realized_loss, Decimal("6"))
        state = apply_event(state, self.close("close-2", 3, ".03", "10"))
        self.assertEqual(state.ledger.total, Decimal("0"))
        self.assertEqual(state.budget.realized_loss, Decimal("6"))
        self.assertEqual(state.budget.realized_profit, Decimal("10"))
        self.assertEqual(state.budget.risk_limit, Decimal("1000"))
        self.assertEqual(state.budget.remaining_limit, Decimal("994"))
        self.assertEqual(replay(state.trace), state)
        with self.assertRaisesRegex(ValueError, "CONFIRMED_POSITION_REQUIRED"):
            propose_stop(state, self.key("intent-1"), "98", "101")

    def test_close_of_known_partial_fill_preserves_unknown_entry_remainder(self):
        state = apply_event(self.partial(), self.close(volume=".02", pnl="-3"))
        self.assertEqual(state.ledger.open_risk, Decimal("5.5"))
        self.assertEqual(state.ledger.unknown_risk, Decimal("11"))
        self.assertEqual(state.budget.realized_loss, Decimal("3"))
        self.assertEqual(state.get(self.key("intent-1")).phase, Phase.UNKNOWN)

    def test_unknown_or_gross_only_close_evidence_does_not_release_open_risk(self):
        for changes in ({"realized_pnl": None}, {"net_costs_confirmed": False},
                        {"net_pnl_provenance": "GROSS_ONLY"}, {"cost_evidence_id": None},
                        {"terminal_proof": False}, {"authoritative": False}):
            state = apply_event(self.full(), self.close(**changes))
            self.assertEqual(state.ledger.total, Decimal("27.5"))
            self.assertEqual(state.budget.realized_loss, Decimal("0"))
            self.assertTrue(state.get(self.key("intent-1")).close_uncertain)
            self.assertEqual(state.quarantined[-1].reason, "CONFIRMED_NET_CLOSE_PROOF_REQUIRED")

    def test_repeated_close_deal_is_idempotent_even_with_a_different_event_id(self):
        event = self.close(volume=".02", pnl="-6")
        state = apply_event(self.full(), event)
        self.assertIs(apply_event(state, event), state)
        state = apply_event(state, replace(event, event_id="duplicate-id", sequence=3))
        self.assertEqual(state.ledger.open_risk, Decimal("16.5"))
        self.assertEqual(state.budget.realized_loss, Decimal("6"))
        conflict = replace(event, event_id="conflict-id", sequence=4, close_volume=Decimal(".03"))
        state = apply_event(state, conflict)
        self.assertEqual(state.quarantined[-1].reason, "CLOSE_DEAL_ID_PAYLOAD_CONFLICT")
        self.assertEqual(state.ledger.open_risk, Decimal("16.5"))
        self.assertEqual(state.budget.realized_loss, Decimal("6"))
        self.assertEqual(replay(state.trace), state)

    def test_old_close_proof_is_quarantined_until_new_sequenced_proof_arrives(self):
        state = self.send(self.reserved(), self.key("intent-1"))
        state = apply_event(state, self.event(sequence=3, fill=".05"))
        state = apply_event(state, self.close(sequence=2))
        self.assertEqual(state.quarantined[-1].reason, "OUT_OF_ORDER_CLOSE")
        self.assertEqual(state.ledger.total, Decimal("27.5"))
        state = apply_event(state, self.close("confirmed-close", 4))
        self.assertEqual(state.ledger.total, Decimal("22"))
        self.assertEqual(state.budget.realized_loss, Decimal("2"))

    def test_close_cannot_exceed_open_quantity_or_reuse_entry_deal(self):
        for changes, reason in (({"volume": ".06"}, "CLOSE_EXCEEDS_CONFIRMED_OPEN_VOLUME"),
                                ({"key": "broker-deal-91"}, "ENTRY_DEAL_CANNOT_BE_CLOSE_DEAL"),
                                ({"budget_epoch_id": "another-epoch"}, "CLOSE_BUDGET_EPOCH_MISMATCH"),
                                ({"position_id": "unknown-position"}, "CLOSE_POSITION_IDENTITY_AMBIGUOUS")):
            state = apply_event(self.full(), self.close(**changes))
            self.assertEqual(state.quarantined[-1].reason, reason)
            self.assertEqual(state.ledger.total, Decimal("27.5"))

    def test_confirmed_gap_loss_above_epoch_is_charged_and_blocks_new_reservations(self):
        state = self.full(volume=".01", epoch="10")
        state = apply_event(state, self.close(volume=".01", pnl="-20"))
        self.assertEqual(state.ledger.total, Decimal("0"))
        self.assertEqual(state.budget.realized_loss, Decimal("20"))
        self.assertEqual(state.budget.remaining_limit, Decimal("0"))
        second = self.intent("intent-2", volume=".01")
        state = approve(propose(state, second), second.client_intent_id, "5.5")
        with self.assertRaisesRegex(ValueError, "FIXED_EPOCH_RISK_BUDGET"):
            reserve(state, second.client_intent_id, "100", "100")

    def test_profit_close_does_not_automatically_expand_fixed_budget(self):
        state = apply_event(self.full(volume=".01", epoch="10"), self.close(volume=".01", pnl="1000"))
        self.assertEqual(state.budget.risk_limit, Decimal("10"))
        self.assertEqual(state.budget.remaining_limit, Decimal("10"))
        for label in ("intent-2", "intent-3"):
            intent = self.intent(label, volume=".01")
            state = approve(propose(state, intent), intent.client_intent_id, "5.5")
            if label == "intent-2":
                state = reserve(state, intent.client_intent_id, "100", "100")
            else:
                with self.assertRaisesRegex(ValueError, "FIXED_EPOCH_RISK_BUDGET"):
                    reserve(state, intent.client_intent_id, "100", "100")

    def test_late_contradictory_fill_after_close_never_refunds_realized_loss(self):
        state = apply_event(self.partial(), self.close(volume=".03", pnl="-4"))
        self.assertEqual(state.ledger.total, Decimal("11"))
        state = apply_event(state, self.event("late-fill", 1, fill=".04", deal_id="late-deal"))
        self.assertEqual(state.get(self.key("intent-1")).closed_volume, Decimal(".03"))
        self.assertEqual(state.ledger.total, Decimal("11"))
        self.assertEqual(state.budget.realized_loss, Decimal("4"))

    def test_memory_stop_observation_can_only_claim_synthetic_protection(self):
        state = observe_stop(self.partial(), self.key("intent-1"), "95")
        protection = state.get(self.key("intent-1")).protection
        self.assertTrue(protection.synthetic_protected)
        self.assertFalse(protection.server_protected)
        self.assertFalse(protection.broker_protection_confirmed)
        self.assertEqual(protection.evidence_source, "OFFLINE_SYNTHETIC")

    def test_unresolved_close_blocks_every_new_entry_stage_until_matching_proof(self):
        state = self.full()
        pending = self.intent("already-proposed")
        approved = self.intent("already-approved")
        reserved = self.intent("already-reserved")
        for intent in (pending, approved, reserved):
            state = propose(state, intent)
        state = approve(state, approved.client_intent_id, "27.5")
        state = approve(state, reserved.client_intent_id, "27.5")
        state = reserve(state, reserved.client_intent_id, "100", "100")
        state = apply_event(state, self.close("unresolved", 2, net_costs_confirmed=False))
        new = self.intent("new-entry")
        for action in (lambda: propose(state, new),
                       lambda: approve(state, pending.client_intent_id, "27.5"),
                       lambda: reserve(state, approved.client_intent_id, "100", "100"),
                       lambda: self.send(state, reserved.client_intent_id)):
            with self.assertRaisesRegex(ValueError, "UNRESOLVED_CLOSE_EVIDENCE"):
                action()
        # An unrelated valid close cannot certify the unresolved deal's costs.
        state = apply_event(state, self.close("unrelated", 3))
        self.assertTrue(state.get(self.key("intent-1")).close_uncertain)
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_CLOSE_EVIDENCE"):
            propose(state, new)
        state = apply_event(state, replace(self.close("unresolved", 4), event_id="corrected-proof"))
        self.assertFalse(state.get(self.key("intent-1")).close_uncertain)
        state = propose(state, new)
        self.assertEqual(state.get(new.client_intent_id).phase, Phase.PROPOSED)
        self.assertEqual(replay(state.trace), state)

    def test_missing_deal_identity_requires_explicit_superseding_close_reference(self):
        state = apply_event(self.full(), self.close("unknown-id", 2, deal_id=None))
        state = apply_event(state, self.close("known-later", 3))
        self.assertTrue(state.get(self.key("intent-1")).close_uncertain)
        # The same accepted close can carry authoritative linkage to the earlier
        # unidentifiable update without releasing or charging its slice twice.
        proof = replace(self.close("known-later", 4), event_id="linked-proof",
                        reconciles_event_id="event-unknown-id")
        state = apply_event(state, proof)
        self.assertFalse(state.get(self.key("intent-1")).close_uncertain)
        self.assertEqual(state.ledger.total, Decimal("22"))
        self.assertEqual(state.budget.realized_loss, Decimal("2"))

    def test_old_duplicate_close_proof_cannot_clear_newer_conflicting_evidence(self):
        event = self.close("confirmed", 2)
        state = apply_event(self.full(), event)
        state = apply_event(state, replace(event, event_id="conflicting-newer", sequence=4,
                                            close_volume=Decimal(".02")))
        state = apply_event(state, replace(event, event_id="stale-proof", sequence=3))
        self.assertTrue(state.get(self.key("intent-1")).close_uncertain)
        self.assertEqual(state.quarantined[-1].reason, "OUT_OF_ORDER_CLOSE_RECONCILIATION")
        state = apply_event(state, replace(event, event_id="fresh-proof", sequence=5))
        self.assertFalse(state.get(self.key("intent-1")).close_uncertain)
        self.assertEqual(state.ledger.total, Decimal("22"))
        self.assertEqual(state.budget.realized_loss, Decimal("2"))


if __name__ == "__main__":
    unittest.main()
