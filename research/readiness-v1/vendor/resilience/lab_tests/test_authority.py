"""AC5-AC8: synthetic actors, actual local journals, mandatory modeled fencing."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest

from faraz_core.authorization import authorize_entry
from faraz_core.execution import BrokerEvent, MockBroker, Phase, replay
from faraz_lab.authority import (AuthorityError, AuthorityGateway, AuthorityToken,
                                  COMPONENTS, canonical_control_path)
from faraz_lab.durable import DurableExecutor
from faraz_lab.fixtures import scenario, fill_event, close_event, summary
from faraz_lab.journal import JournalError, load_entries


AUTHORITY_EVIDENCE = []
SEED = 41207


class AuthorityAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory(prefix="faraz-authority-")
        self.addCleanup(self.storage.cleanup)
        self.folder = Path(self.storage.name)
        self.authorization, self.binding, self.intent = scenario()

    def create(self, label="case", broker=None, **config):
        executor = DurableExecutor.create(self.folder / (label + ".orders"), self.binding)
        self.addCleanup(executor.close)
        broker = broker or MockBroker()
        gateway = AuthorityGateway.create(canonical_control_path(executor), executor, broker, **config)
        self.addCleanup(gateway.close)
        self.executor, self.broker = executor, broker
        self.healthy(gateway)
        return gateway

    def healthy(self, gate, now=1000):
        for component in COMPONENTS:
            gate.observe(component, "HEALTHY", now, now, observer="synthetic-observer")

    def record(self, name, gate, now=1000, **extra):
        AUTHORITY_EVIDENCE.append({"scenario": name, "seed": SEED, "cut_point": extra.pop("cut_point", name),
                                   "view": gate.view(now), "financial": summary(gate.state),
                                   "control_trace": gate.control_trace,
                                   "actual_mock_attempts": gate.actual_mock_attempts,
                                   "passed": True, **extra})

    def deny_submit(self, gate, token, now=1000, actor="phone", reason=None):
        before = gate.actual_mock_attempts
        previous = gate.state
        with self.assertRaisesRegex(AuthorityError, reason or "NO_NEW_ORDER"):
            gate.submit(actor, token, self.authorization, now)
        self.assertEqual(gate.actual_mock_attempts, before)
        self.assertIs(gate.state, previous)

    def test_ac5_single_device_failure_is_not_global_engine_failure(self):
        gate = self.create()
        token = gate.elect("laptop", "A", 1000, 500)
        gate.observe("laptop", "UNREACHABLE", 1000, 1000)
        view = gate.view(1000)
        self.assertFalse(view["NO_NEW_ORDER"])
        self.assertFalse(view["health"]["laptop"]["fresh_healthy"])
        self.assertTrue(view["health"]["phone"]["fresh_healthy"])
        self.assertIn("اتصال لپ‌تاپ تأیید نشده", view["message_fa"])
        self.assertIn("مسیر اجرایی مصنوعی", view["display_fa"]["execution"])
        self.record("AC5-laptop-only-cut-independent-engine", gate)
        gate.observe("laptop", "HEALTHY", 1000, 1000)
        gate.observe("phone", "FAILED", 1000, 1000)
        self.assertFalse(gate.view(1000)["NO_NEW_ORDER"])
        self.assertIn("اتصال گوشی تأیید نشده", gate.view(1000)["message_fa"])
        self.deny_submit(gate, token, actor="phone", reason="ACTOR_UNREACHABLE")
        self.record("AC5-phone-only-cut-independent-engine", gate)

    def test_ac5_phone_internet_cannot_replace_a_laptop_hosted_engine(self):
        gate = self.create(topology="laptop")
        token = gate.elect("phone", "A", 1000, 500)
        gate.observe("laptop", "UNREACHABLE", 1000, 1000)
        self.assertTrue(gate.view(1000)["NO_NEW_ORDER"])
        self.assertIn("اتصال گوشی جای موتور را نمی‌گیرد", gate.view(1000)["message_fa"])
        self.deny_submit(gate, token, reason="PATH_UNPROVEN:laptop")
        self.record("AC5-laptop-cut-laptop-hosted-engine", gate)

    def test_ac5_both_ui_failures_respect_explicit_unattended_policy(self):
        for unattended in (False, True):
            with self.subTest(unattended=unattended):
                gate = self.create("unattended-" + str(unattended), unattended_allowed=unattended)
                token = gate.elect("phone", "A", 1000, 500)
                for component in ("phone", "laptop"):
                    gate.observe(component, "UNREACHABLE", 1000, 1000)
                self.assertEqual(gate.view(1000)["NO_NEW_ORDER"], not unattended)
                if unattended:
                    gate.submit("engine", token, self.authorization, 1000)
                    self.assertEqual(gate.actual_mock_attempts, 1)
                else:
                    self.deny_submit(gate, token, actor="engine", reason="UNATTENDED_NOT_AUTHORIZED")
                self.record("AC5-both-UIs-cut-unattended-" + str(unattended), gate)

    def test_ac5_engine_server_broker_journal_authority_failures_block_entries(self):
        for component in ("engine", "server", "broker", "journal", "authority"):
            with self.subTest(component=component):
                gate = self.create(component)
                token = gate.elect("laptop", "A", 1000, 500)
                gate.observe(component, "UNREACHABLE", 1000, 1000)
                self.assertTrue(gate.view(1000)["NO_NEW_ORDER"])
                self.deny_submit(gate, token, reason="PATH_UNPROVEN:" + component)
                self.record("AC5-component-cut-" + component, gate)

    def test_ac6_partitioned_old_leader_and_paused_stale_epoch_are_fenced(self):
        gate = self.create()
        old = gate.elect("laptop", "A", 1000, 500)
        gate.observe("authority", "UNREACHABLE", 1001, 1001)
        # Broker stays healthy, yet coordinator loss cannot grant authority.
        self.assertTrue(gate.view(1001)["health"]["broker"]["fresh_healthy"])
        self.deny_submit(gate, old, now=1001, actor="laptop", reason="PATH_UNPROVEN:authority")
        gate.observe("authority", "HEALTHY", 1002, 1002)
        with self.assertRaisesRegex(AuthorityError, "PREVIOUS_AUTHORITY_NOT_FENCED"):
            gate.elect("phone", "B", 1002, 500)
        new = gate.elect("phone", "B", 1002, 500, fence_previous=True)
        self.assertEqual(new.epoch, old.epoch + 1)
        self.deny_submit(gate, old, now=1002, actor="laptop", reason="STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        self.assertFalse(gate.view(1002)["NO_NEW_ORDER"])
        self.record("AC6-old-leader-partition-and-resume", gate, now=1002)

    def test_ac6_unenforceable_fencing_prevents_even_an_expired_lease_takeover(self):
        gate = self.create(fencing_supported=False)
        with self.assertRaisesRegex(AuthorityError, "EFFECTIVE_FENCING_UNAVAILABLE"):
            gate.elect("phone", "A", 1000, 1)
        self.assertTrue(gate.view(1001)["NO_NEW_ORDER"])
        self.assertEqual(gate.actual_mock_attempts, 0)
        self.record("AC6-fencing-unavailable", gate, now=1001)

    def test_ac7_two_actual_contending_threads_share_one_durable_intent(self):
        gate = self.create()
        token = gate.elect("laptop", "A", 1000, 500)
        entered, second_started, release = Event(), Event(), Event()
        outcomes, errors = [], []
        armed = [True]
        def hold_admission(label, _gate):
            if label == "before_control_write" and armed[0]:
                armed[0] = False
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("lab release timeout")
        gate.fault_hook = hold_admission
        def run(actor):
            try:
                if actor == "laptop":
                    second_started.set()
                outcomes.append(gate.submit(actor, token, self.authorization, 1000)["status"])
            except BaseException as error:
                errors.append(repr(error))
        first = Thread(target=run, args=("phone",))
        second = Thread(target=run, args=("laptop",))
        first.start()
        self.assertTrue(entered.wait(5))
        second.start()
        self.assertTrue(second_started.wait(5))
        release.set()
        first.join(10)
        second.join(10)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(errors, [])
        self.assertCountEqual(outcomes, ["SYNTHETIC_SENT", "IDEMPOTENT_EXISTING"])
        self.assertEqual(gate.actual_mock_attempts, 1)
        self.assertEqual(len(gate.state.intents), 1)
        self.assertEqual(replay(self.executor.journal.entries), gate.state)
        self.record("AC7-two-actors-contending-shared-idempotency", gate,
                    cut_point="first-admit-held-before-control-write", outcomes=outcomes)

    def test_ac7_lease_clock_health_staleness_and_flapping_never_extend_authority(self):
        gate = self.create(max_health_age_ms=50)
        token = gate.elect("phone", "A", 1000, 100)
        gate.observe("phone", "UNREACHABLE", 1001, 1001)
        self.deny_submit(gate, token, now=1001, actor="phone", reason="ACTOR_UNREACHABLE")
        gate.observe("phone", "HEALTHY", 1002, 1002)
        self.deny_submit(gate, token, now=1001, reason="CLOCK_REGRESSION")
        with self.assertRaisesRegex(AuthorityError, "FUTURE_OR_REGRESSING"):
            gate.observe("phone", "HEALTHY", 1100, 1002)
        with self.assertRaisesRegex(AuthorityError, "PATH_UNPROVEN"):
            gate.renew("phone", token, 1060, 500)
        self.assertEqual(gate.view(1060)["expires_ms"], 1100)
        self.deny_submit(gate, token, now=1100, reason="LEASE_EXPIRED")
        self.assertTrue(gate.view(1100)["NO_NEW_ORDER"])
        self.record("AC7-lease-expiry-clock-skew-flapping", gate, now=1100)

    def test_ac8_unknown_ack_blocks_handoff_until_proven_cancel_and_preserves_idempotency(self):
        broker = MockBroker(lose_response=True)
        gate = self.create(broker=broker)
        old = gate.elect("laptop", "A", 1000, 500)
        gate.submit("laptop", old, self.authorization, 1000)
        self.assertEqual(gate.state.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
        self.assertIn("تا تطبیق معتبر متوقف", gate.view(1000)["message_fa"])
        with self.assertRaisesRegex(AuthorityError, "RECONCILIATION_REQUIRED_BEFORE_HANDOFF"):
            gate.elect("phone", "B", 1001, 500, fence_previous=True)
        self.assertEqual(Decimal(summary(gate.state)["unknown_risk"]), Decimal("27.50"))
        bad = BrokerEvent("unproven-cancel", self.intent.client_intent_id, 1, "RECONCILE",
                          self.intent.account_id, 0, cumulative_filled="0", order_id="lab-order",
                          authoritative=True, terminal_status="CANCELLED")
        gate.record_event(bad, 1001)
        with self.assertRaisesRegex(AuthorityError, "RECONCILIATION_REQUIRED"):
            gate.elect("phone", "B", 1001, 500, fence_previous=True)
        gate.record_event(replace(bad, event_id="proven-cancel", sequence=2, terminal_proof=True), 1002)
        new = gate.elect("phone", "B", 1002, 500, fence_previous=True)
        self.assertEqual(gate.submit("phone", new, self.authorization, 1002)["status"], "IDEMPOTENT_EXISTING")
        self.assertEqual(gate.actual_mock_attempts, 1)
        self.assertEqual(gate.state.ledger.total, 0)
        self.record("AC8-unknown-ACK-proven-cancel-before-handoff", gate, now=1002)

    def test_ac8_partial_close_pending_reconciliation_and_stop_are_preserved(self):
        broker = MockBroker((fill_event(self.intent),))
        gate = self.create(broker=broker)
        token = gate.elect("laptop", "A", 1000, 500)
        gate.submit("laptop", token, self.authorization, 1000)
        self.executor.transition("observe_stop", self.intent.client_intent_id, "3995", True)
        protected = gate.state.get(self.intent.client_intent_id).protection
        self.assertTrue(protected.synthetic_protected)
        gate.record_event(close_event(self.intent), 1001)
        with self.assertRaisesRegex(AuthorityError, "RECONCILIATION_REQUIRED"):
            gate.elect("phone", "B", 1001, 500, fence_previous=True)
        cancel = BrokerEvent("partial-final-cancel", self.intent.client_intent_id, 3, "RECONCILE",
                             self.intent.account_id, 0, cumulative_filled=".03", order_id="lab-order",
                             position_id="lab-position", authoritative=True, terminal_proof=True,
                             terminal_status="CANCELLED")
        gate.record_event(cancel, 1002)
        before_handoff = gate.state.get(self.intent.client_intent_id).protection
        new = gate.elect("phone", "B", 1002, 500, fence_previous=True)
        self.assertEqual(new.epoch, 2)
        self.assertEqual(gate.state.get(self.intent.client_intent_id).protection, before_handoff)
        self.assertEqual(before_handoff.observed_stop, Decimal("3995"))
        self.assertFalse(before_handoff.broker_protection_confirmed)
        money = summary(gate.state)
        self.assertEqual(Decimal(money["open_risk"]), Decimal("11"))
        self.assertEqual(Decimal(money["unknown_risk"]), 0)
        self.assertEqual(Decimal(money["charged_loss"]), Decimal("2.10"))
        self.record("AC8-partial-close-reconciled-safe-handoff", gate, now=1002)

    def test_control_commit_ambiguity_blocks_before_any_order_effect(self):
        gate = self.create()
        token = gate.elect("phone", "A", 1000, 500)
        def failure(label, _gate):
            if label == "before_control_fsync":
                raise OSError("injected control commit ambiguity")
        gate.fault_hook = failure
        with self.assertRaisesRegex(AuthorityError, "CONTROL_COMMIT_UNKNOWN"):
            gate.submit("phone", token, self.authorization, 1000)
        self.assertTrue(gate.poisoned)
        self.assertEqual(gate.actual_mock_attempts, 0)
        self.assertEqual(gate.state.intents, ())
        self.deny_submit(gate, token, reason="RECOVERY_REQUIRED")
        self.record("control-commit-ambiguity-no-order-effect", gate,
                    cut_point="before-control-fsync-on-admission")

    def test_restart_replays_epoch_and_shared_idempotency_but_not_old_authority(self):
        gate = self.create()
        token = gate.elect("laptop", "A", 1000, 500)
        gate.submit("laptop", token, self.authorization, 1000)
        gate.close()
        self.executor.close()
        restored_executor = DurableExecutor.open(self.folder / "case.orders", self.binding)
        self.addCleanup(restored_executor.close)
        restored = AuthorityGateway.open(canonical_control_path(restored_executor), restored_executor,
                                         self.broker, now_ms=1001)
        self.addCleanup(restored.close)
        self.assertEqual(restored.view(1001)["epoch"], 1)
        self.assertIsNone(restored.view(1001)["owner"])
        self.assertTrue(restored.view(1001)["NO_NEW_ORDER"])
        self.assertEqual(restored.actual_mock_attempts, 1)
        self.healthy(restored, 1001)
        with self.assertRaisesRegex(AuthorityError, "RECONCILIATION_REQUIRED"):
            restored.elect("phone", "B", 1001, 500, fence_previous=True)
        self.assertEqual(restored.state.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
        self.record("restart-epoch-preserved-authority-revoked", restored, now=1001)

    def test_control_tail_schema_and_cross_order_binding_fail_closed(self):
        gate = self.create()
        gate.elect("laptop", "A", 1000, 500)
        path = gate.path
        gate.close()
        good = path.read_bytes()
        for damaged in (good[:-1], good.replace(b'"version":1', b'"version":9', 1)):
            path.write_bytes(damaged)
            with self.assertRaises(AuthorityError):
                AuthorityGateway.open(path, self.executor, self.broker, now_ms=1001)
            self.assertEqual(path.read_bytes(), damaged)
        path.write_bytes(good)
        alternate = DurableExecutor.create(self.folder / "other.orders", self.binding)
        self.addCleanup(alternate.close)
        with self.assertRaisesRegex(AuthorityError, "CANONICAL_CONTROL_PATH_REQUIRED"):
            AuthorityGateway.open(path, alternate, self.broker, now_ms=1001)

    def test_positive_lease_renewal_preserves_epoch_and_revokes_old_token(self):
        gate = self.create()
        old = gate.elect("phone", "A", 1000, 100)
        fresh = gate.renew("laptop", old, 1001, 500)
        self.assertEqual(fresh.epoch, old.epoch)
        self.assertEqual(fresh.expires_ms, 1501)
        self.deny_submit(gate, old, now=1001, reason="STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        authorization = authorize_entry(replace(self.authorization.context, decision_ms=1001),
                                          self.authorization.request, 2000)
        gate.submit("laptop", fresh, authorization, 1001)
        self.assertEqual(gate.actual_mock_attempts, 1)
        self.record("positive-fresh-lease-renewal", gate, now=1001)

    def test_closed_underlying_executor_revokes_apparent_readiness(self):
        gate = self.create()
        token = gate.elect("phone", "A", 1000, 500)
        self.assertFalse(gate.view(1000)["NO_NEW_ORDER"])
        self.executor.close()
        self.assertTrue(gate.view(1000)["NO_NEW_ORDER"])
        self.deny_submit(gate, token, reason="RECOVERY_REQUIRED")
        self.record("closed-durable-executor-path-is-unavailable", gate)

    def test_live_control_prefix_corruption_revokes_authority_without_order_effect(self):
        gate = self.create()
        token = gate.elect("phone", "A", 1000, 500)
        gate.path.write_bytes(gate.path.read_bytes()[:-1])
        damaged = gate.path.read_bytes()
        self.assertTrue(gate.view(1000)["NO_NEW_ORDER"])
        self.assertTrue(gate.poisoned)
        self.deny_submit(gate, token, reason="RECOVERY_REQUIRED")
        self.assertEqual(gate.path.read_bytes(), damaged)
        self.record("live-control-tail-corruption-no-entry", gate)

    def test_live_order_journal_corruption_or_valid_shorter_prefix_revokes_readiness(self):
        for damage in ("truncated-tail", "valid-shorter-prefix"):
            with self.subTest(damage=damage):
                gate = self.create("order-prefix-" + damage)
                token = gate.elect("phone", "A", 1000, 500)
                self.assertFalse(gate.view(1000)["NO_NEW_ORDER"])
                order_path = self.executor.journal.path
                original = order_path.read_bytes()
                damaged = original[:-1] if damage == "truncated-tail" else original.splitlines(keepends=True)[0]
                order_path.write_bytes(damaged)
                if damage == "valid-shorter-prefix":
                    self.assertEqual(len(load_entries(order_path)), 1)
                    self.assertGreater(len(self.executor.journal.entries), 1)
                view = gate.view(1000)  # Same time: no clock append can mask the missing check.
                self.assertEqual(view["mode"], "UNKNOWN")
                self.assertTrue(view["NO_NEW_ORDER"])
                self.assertTrue(gate.poisoned)
                self.deny_submit(gate, token, reason="RECOVERY_REQUIRED")
                self.assertEqual(gate.actual_mock_attempts, 0)
                self.assertEqual(order_path.read_bytes(), damaged)
                self.record("live-order-prefix-no-entry-" + damage, gate,
                            cut_point="after-order-file-damage-without-time-advance")

    def test_same_order_journal_cannot_get_an_alternate_authority_after_handoff(self):
        gate = self.create()
        old = gate.elect("laptop", "A", 1000, 500)
        current = gate.elect("phone", "B", 1001, 500, fence_previous=True)
        alternative = self.folder / "alternate.control"
        for constructor in (
                lambda: AuthorityGateway.create(alternative, self.executor, self.broker),
                lambda: AuthorityGateway.open(alternative, self.executor, self.broker, now_ms=1001)):
            with self.assertRaisesRegex(AuthorityError, "CANONICAL_CONTROL_PATH_REQUIRED"):
                constructor()
        self.assertFalse(alternative.exists())
        with self.assertRaisesRegex(JournalError, "LOCK_UNAVAILABLE"):
            AuthorityGateway.open(gate.path, self.executor, self.broker, now_ms=1001)
        self.deny_submit(gate, old, now=1001, reason="STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        self.assertEqual(current.epoch, 2)
        self.assertEqual(gate.actual_mock_attempts, 0)
        self.record("single-canonical-control-namespace-after-live-handoff", gate, now=1001)

    def test_canonical_binding_survives_restart_without_epoch_reset(self):
        gate = self.create()
        first = gate.elect("laptop", "A", 1000, 500)
        second = gate.elect("phone", "B", 1001, 500, fence_previous=True)
        gate.close()
        self.executor.close()
        executor = DurableExecutor.open(self.folder / "case.orders", self.binding)
        self.addCleanup(executor.close)
        restored = AuthorityGateway.open(canonical_control_path(executor), executor, self.broker, now_ms=1002)
        self.addCleanup(restored.close)
        self.healthy(restored, 1002)
        third = restored.elect("phone", "A", 1002, 500, fence_previous=True)
        self.assertEqual((first.epoch, second.epoch, third.epoch), (1, 2, 3))
        for stale in (first, second):
            self.deny_submit(restored, stale, now=1002, reason="STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        with self.assertRaisesRegex(AuthorityError, "CANONICAL_CONTROL_PATH_REQUIRED"):
            AuthorityGateway.create(self.folder / "new-after-restart.control", executor, self.broker)
        self.record("canonical-binding-restart-monotonic-epochs", restored, now=1002)

    def test_missing_control_and_anchor_cannot_turn_initialized_journal_into_new_authority(self):
        gate = self.create()
        gate.elect("phone", "A", 1000, 500)
        gate.close()
        # Deliberate loss of owned, isolated lab sidecars; never production data.
        for path in (gate.path, Path(str(gate.path) + ".anchor")):
            self.assertTrue(path.resolve().is_relative_to(self.folder.resolve()))
            path.unlink()
        self.assertGreater(len(self.executor.journal.entries), 1)
        with self.assertRaisesRegex(AuthorityError, "FRESH_ORDER_JOURNAL_REQUIRED"):
            AuthorityGateway.create(gate.path, self.executor, self.broker)
        with self.assertRaisesRegex(AuthorityError, "ANCHOR_MISSING_OR_INVALID"):
            AuthorityGateway.open(gate.path, self.executor, self.broker, now_ms=1001)
        self.assertEqual(len(self.broker.attempted), 0)

    def test_observed_lease_expiry_cannot_be_undone_by_a_later_supplied_clock_rewind(self):
        for operation in ("submit", "renew", "view"):
            with self.subTest(operation=operation):
                gate = self.create("clock-" + operation)
                token = gate.elect("phone", "A", 1000, 100)
                if operation == "submit":
                    self.deny_submit(gate, token, now=1100, reason="LEASE_EXPIRED")
                elif operation == "renew":
                    with self.assertRaisesRegex(AuthorityError, "LEASE_EXPIRED"):
                        gate.renew("phone", token, 1100, 500)
                else:
                    self.assertTrue(gate.view(1100)["NO_NEW_ORDER"])
                self.deny_submit(gate, token, now=1000, reason="CLOCK_REGRESSION")
                self.assertEqual(gate.actual_mock_attempts, 0)
                self.assertTrue(gate.view(1100)["NO_NEW_ORDER"])
                self.record("observed-expiry-clock-rewind-" + operation, gate, now=1100)

    def test_denied_expiry_clock_high_water_survives_gateway_restart(self):
        gate = self.create()
        token = gate.elect("phone", "A", 1000, 100)
        self.deny_submit(gate, token, now=1100, reason="LEASE_EXPIRED")
        gate.close()
        with self.assertRaisesRegex(AuthorityError, "CLOCK_REGRESSION"):
            AuthorityGateway.open(gate.path, self.executor, self.broker, now_ms=1000)
        restored = AuthorityGateway.open(gate.path, self.executor, self.broker, now_ms=1101)
        self.addCleanup(restored.close)
        self.assertIsNone(restored.view(1101)["owner"])
        self.deny_submit(restored, token, now=1101, reason="STALE_OR_CONFLICTING_AUTHORITY_EPOCH")
        self.deny_submit(restored, token, now=1000, reason="CLOCK_REGRESSION")
        self.assertEqual(restored.actual_mock_attempts, 0)
        self.record("durable-expired-clock-high-water-after-restart", restored, now=1101)


if __name__ == "__main__":
    unittest.main()
