"""Durable wrapper acceptance with synthetic evidence and injected local I/O faults."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from faraz_core.execution import MockBroker, Phase, replay
from faraz_lab.durable import DurableExecutor, DurabilityError
from faraz_lab.fixtures import scenario, reserve_intent, fill_event, close_event, summary
from faraz_lab.journal import JournalError


DURABLE_EVIDENCE = []
SEED = 41207
D = Decimal


class DurableAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="faraz-durable-")
        self.addCleanup(self.storage.cleanup)
        self.path = Path(self.storage.name) / "synthetic.journal"
        self.authorization, self.binding, self.intent = scenario()

    def create(self, **kwargs):
        executor = DurableExecutor.create(self.path, self.binding, **kwargs)
        self.addCleanup(executor.close)
        return executor

    def reopen(self):
        executor = DurableExecutor.open(self.path, self.binding)
        self.addCleanup(executor.close)
        self.assertEqual(replay(executor.journal.entries), executor.state)
        return executor

    def reserve(self, executor):
        self.assertEqual(reserve_intent(executor, self.authorization), self.intent)

    def send(self, executor, events=(), lose_response=False):
        broker = MockBroker(events, lose_response=lose_response)
        executor.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        return broker

    def assert_money(self, state, *, open_risk, unknown_risk, known_notional,
                     unknown_notional, unfilled_margin, charged_loss):
        evidence = summary(state)
        for key, expected in dict(open_risk=open_risk, unknown_risk=unknown_risk,
                                  known_notional=known_notional,
                                  unknown_notional=unknown_notional,
                                  unfilled_margin=unfilled_margin,
                                  charged_loss=charged_loss).items():
            self.assertEqual(D(evidence[key]), D(expected), key)
        self.assertEqual(D(evidence["epoch_limit"]), D("30"))
        return evidence

    def test_ac3_partial_and_confirmed_close_replay_exact_money_once(self):
        executor = self.create()
        self.reserve(executor)
        broker = self.send(executor, (fill_event(self.intent),))
        partial = self.assert_money(executor.state, open_risk="16.50", unknown_risk="11",
                                    known_notional="12000.60", unknown_notional="8000.40",
                                    unfilled_margin="20", charged_loss="0")
        event = close_event(self.intent)
        executor.transition("apply_event", event)
        executor.transition("apply_event", replace(event, event_id="lab-close-duplicate", sequence=3))
        settled = self.assert_money(executor.state, open_risk="11", unknown_risk="11",
                                    known_notional="8000.40", unknown_notional="8000.40",
                                    unfilled_margin="20", charged_loss="2.10")
        self.assertEqual(executor.state.get(self.intent.client_intent_id).closed_volume, D(".01"))
        self.assertEqual(len(broker.attempted), 1)
        executor.close()
        recovered = self.reopen()
        self.assert_money(recovered.state, open_risk="11", unknown_risk="11",
                          known_notional="8000.40", unknown_notional="8000.40",
                          unfilled_margin="20", charged_loss="2.10")
        DURABLE_EVIDENCE.append({"scenario": "AC3-partial-close-duplicate-recovery", "seed": SEED,
                                 "partial": partial, "settled": settled,
                                 "actual_mock_attempts": len(broker.attempted), "passed": True})

    def test_reserved_recovery_retains_unknown_and_never_retries(self):
        executor = self.create()
        self.reserve(executor)
        executor.close()
        restored = self.reopen()
        self.assertEqual(restored.state.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
        self.assert_money(restored.state, open_risk="0", unknown_risk="27.50",
                          known_notional="0", unknown_notional="20001.00",
                          unfilled_margin="50", charged_loss="0")
        broker = MockBroker()
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            restored.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        self.assertEqual(broker.attempted, ())

    def test_lost_response_stays_unknown_after_fresh_recovery(self):
        executor = self.create()
        self.reserve(executor)
        broker = self.send(executor, lose_response=True)
        self.assertEqual(len(broker.attempted), 1)
        executor.close()
        restored = self.reopen()
        self.assertEqual(D(summary(restored.state)["unknown_risk"]), D("27.5"))
        with self.assertRaisesRegex(ValueError, "NO_RESEND"):
            restored.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        self.assertEqual(len(broker.attempted), 1)

    def test_send_attempt_io_ambiguity_poisoned_before_any_mock_call(self):
        for fault in ("before_fsync", "after_fsync"):
            with self.subTest(fault=fault):
                path = Path(self.storage.name) / (fault + ".journal")
                armed = [False]

                def fail(label, _journal):
                    if armed[0] and label == fault:
                        raise OSError("synthetic-commit-ambiguity")

                executor = DurableExecutor.create(path, self.binding, fault_hook=fail)
                self.addCleanup(executor.close)
                self.reserve(executor)
                armed[0] = True
                broker = MockBroker((fill_event(self.intent),))
                with self.assertRaises(JournalError):
                    executor.send(broker, self.intent.client_intent_id, self.authorization, 1000)
                self.assertTrue(executor.poisoned)
                self.assertEqual(broker.attempted, ())
                self.assertEqual(executor.state.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
                self.assertEqual(executor.state.ledger.total, D("27.50"))
                with self.assertRaises(DurabilityError):
                    executor.transition("recover")

    def test_reply_commit_failure_never_publishes_uncommitted_fill_or_close(self):
        active = [False]
        fsyncs = [0]

        def fail_second(label, _journal):
            if active[0] and label == "before_fsync":
                fsyncs[0] += 1
                if fsyncs[0] == 2:
                    raise OSError("synthetic-reply-commit-failure")

        executor = self.create(fault_hook=fail_second)
        self.reserve(executor)
        active[0] = True
        broker = MockBroker((fill_event(self.intent), close_event(self.intent)))
        with self.assertRaises(JournalError):
            executor.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        self.assertTrue(executor.poisoned)
        self.assertEqual(len(broker.attempted), 1)
        self.assert_money(executor.state, open_risk="0", unknown_risk="27.50",
                          known_notional="0", unknown_notional="20001",
                          unfilled_margin="50", charged_loss="0")

    def test_caught_keyboard_interrupt_after_mock_poisoned_and_preserves_uncertainty(self):
        def interrupt(label):
            if label == "after_mock_call":
                raise KeyboardInterrupt("synthetic-interrupt-after-side-effect")

        executor = self.create(cut_hook=interrupt)
        self.reserve(executor)
        broker = MockBroker((fill_event(self.intent), close_event(self.intent)))
        with self.assertRaises(KeyboardInterrupt):
            executor.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        self.assertTrue(executor.poisoned)
        self.assertEqual(executor.state.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
        self.assert_money(executor.state, open_risk="0", unknown_risk="27.50",
                          known_notional="0", unknown_notional="20001",
                          unfilled_margin="50", charged_loss="0")
        self.assertEqual(len(broker.attempted), 1)
        with self.assertRaises(DurabilityError):
            executor.transition("recover")
        with self.assertRaises(DurabilityError):
            executor.send(broker, self.intent.client_intent_id, self.authorization, 1000)
        self.assertEqual(len(broker.attempted), 1)

    def test_incomplete_close_blocks_entry_until_matching_new_proof(self):
        executor = self.create()
        self.reserve(executor)
        self.send(executor, (fill_event(self.intent),))
        bad = replace(close_event(self.intent), net_costs_confirmed=False)
        executor.transition("apply_event", bad)
        self.assertTrue(executor.state.get(self.intent.client_intent_id).close_uncertain)
        self.assertEqual(executor.state.ledger.total, D("27.50"))
        self.assertEqual(executor.state.budget.realized_loss, 0)
        good = replace(close_event(self.intent), event_id="lab-fixed-close", sequence=3)
        executor.transition("apply_event", good)
        self.assertFalse(executor.state.get(self.intent.client_intent_id).close_uncertain)
        self.assertEqual(executor.state.ledger.total, D("22"))
        self.assertEqual(executor.state.budget.realized_loss, D("2.10"))
        executor.close()
        restored = self.reopen()
        self.assertEqual(restored.state.ledger.total, D("22"))

    def test_duplicate_conflict_and_late_fill_cannot_refund_closed_loss(self):
        executor = self.create()
        self.reserve(executor)
        self.send(executor, (fill_event(self.intent), close_event(self.intent)))
        before = len(executor.journal.entries)
        executor.transition("apply_event", close_event(self.intent))
        self.assertEqual(len(executor.journal.entries), before)
        with self.assertRaisesRegex(ValueError, "EVENT_ID_PAYLOAD_CONFLICT"):
            executor.transition("apply_event", replace(close_event(self.intent), realized_pnl="100"))
        late = replace(fill_event(self.intent), event_id="lab-late-fill", cumulative_filled=D(".04"),
                       deal_id="lab-late-deal")
        executor.transition("apply_event", late)
        self.assertTrue(executor.state.quarantined)
        self.assertEqual(executor.state.get(self.intent.client_intent_id).closed_volume, D(".01"))
        self.assertEqual(executor.state.budget.realized_loss, D("2.10"))
        self.assertEqual(executor.state.ledger.total, D("22"))

    def test_restart_stales_stop_evidence_without_erasing_history(self):
        executor = self.create()
        self.reserve(executor)
        self.send(executor, (fill_event(self.intent),))
        key = self.intent.client_intent_id
        executor.transition("propose_stop", key, "3997", "4000")
        executor.transition("acknowledge_stop", key, "3997")
        executor.transition("observe_stop", key, "3997", True)
        self.assertTrue(executor.state.get(key).protection.synthetic_protected)
        history = executor.state.get(key).protection.observed_history
        executor.close()
        restored = self.reopen()
        protection = restored.state.get(key).protection
        self.assertFalse(protection.synthetic_protected)
        self.assertFalse(protection.server_protected)
        self.assertEqual(protection.observed_history, history)

    def test_no_nonmock_send_or_transition_bypass(self):
        executor = self.create()
        self.reserve(executor)
        before = executor.state
        with self.assertRaisesRegex(ValueError, "EXACT_OFFLINE_MOCK_REQUIRED"):
            executor.send(object(), self.intent.client_intent_id, self.authorization, 1000)
        with self.assertRaisesRegex(ValueError, "OFFLINE_TRANSITION_REQUIRED"):
            executor.transition("send_synthetic", self.intent.client_intent_id, self.authorization, 1000)
        self.assertIs(executor.state, before)

    def test_account_and_policy_binding_cannot_change(self):
        executor = self.create()
        for binding in (replace(self.binding, account_id="other-synthetic-account"),
                        replace(self.binding, policy=replace(self.binding.policy, policy_hash="other-policy"))):
            with self.assertRaises(ValueError):
                executor.transition("update_context", binding)
        executor.close()
        for binding in (replace(self.binding, account_id="other-synthetic-account"),
                        replace(self.binding, policy=replace(self.binding.policy, policy_hash="other-policy"))):
            with self.assertRaises(JournalError):
                DurableExecutor.open(self.path, binding)


if __name__ == "__main__":
    unittest.main()
