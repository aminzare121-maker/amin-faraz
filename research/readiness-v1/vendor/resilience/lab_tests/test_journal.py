"""Deterministic local-file faults; no terminal, broker feed or network exists."""
from dataclasses import replace
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from faraz_core.authorization import authorize_entry, pin_policy
from faraz_core.execution import (DemoBinding, Phase, TraceEntry, approve,
                                  intent_from_authorization, propose, recover,
                                  replay, reserve, start, update_context)
from faraz_lab.codec import (CodecError, canonical_bytes, dumps, from_data,
                             loads, to_data)
from faraz_lab.journal import Journal, JournalError, load_entries
from tests.test_decision import fixture


def seeded_trace():
    context, request = fixture()
    context = replace(context, daily_loss_limit="100", total_loss_limit="200")
    request = replace(request, risk_budget="27.50")
    policy = pin_policy(context, request)
    authorization = authorize_entry(context, request, 2000)
    intent = intent_from_authorization(authorization, policy)
    binding = DemoBinding(context.account_key, 0, policy=policy,
                          budget_epoch_id="journal-test-epoch", epoch_risk_limit="30")
    state = start(binding)
    state = propose(state, intent)
    state = approve(state, intent.client_intent_id, intent.requested_risk)
    state = reserve(state, intent.client_intent_id, "30", "30")
    return binding, intent, state


class CodecTests(unittest.TestCase):
    def test_nested_authorization_roundtrip_and_decimal_scale_are_exact(self):
        binding, intent, state = seeded_trace()
        values = (state.trace, binding, intent, Phase.UNKNOWN,
                  (Decimal("0.0000000000012300"), Decimal("-2.1000")))
        with localcontext() as context:
            context.prec = 2
            recovered = loads(dumps(values))
        self.assertEqual(recovered, values)
        self.assertIs(type(recovered[3]), Phase)
        self.assertEqual(recovered[4][0].as_tuple(), values[4][0].as_tuple())

    def test_mutable_float_unknown_type_and_nonfinite_are_rejected(self):
        for value in (1.0, [1], {"x": 1}, Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=str(value)), self.assertRaises(CodecError):
                dumps(value)
        for wire in (b'{"$type":"arbitrary.module.Class","fields":{}}',
                     b'{"$type":"Decimal","value":"NaN"}',
                     b'{"$type":"Decimal","value":"01.00"}', b'1.5', b'[1]', b'NaN'):
            with self.subTest(wire=wire), self.assertRaises(CodecError):
                loads(wire)

    def test_missing_extra_duplicate_or_untyped_fields_fail_closed(self):
        data = to_data(seeded_trace()[0])
        for change in (lambda row: row["fields"].pop("account_id"),
                       lambda row: row["fields"].update(unknown_field="x"),
                       lambda row: row["fields"].update(epoch_risk_limit="30")):
            altered = json.loads(json.dumps(data))
            change(altered)
            with self.assertRaises(CodecError):
                from_data(altered)
        with self.assertRaisesRegex(CodecError, "DUPLICATE_JSON_KEY"):
            loads(b'{"$type":"tuple","$type":"Decimal","value":"1"}')
        with self.assertRaisesRegex(CodecError, "NONCANONICAL_ENCODING"):
            loads(b' 1')


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="faraz-journal-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "commands.jsonl"
        self.binding, self.intent, self.state = seeded_trace()

    def write(self, count=None):
        with Journal.create(self.path, self.binding) as journal:
            for entry in self.state.trace[1:count]:
                journal.append(entry)
            return journal.entries

    def rewrite(self, frames):
        self.path.write_bytes(b"".join(canonical_bytes(frame) + b"\n" for frame in frames))

    def frames(self):
        return [json.loads(line) for line in self.path.read_bytes().splitlines()]

    def test_create_append_open_replay_and_no_overwrite(self):
        entries = self.write()
        self.assertEqual(entries, self.state.trace)
        self.assertEqual(load_entries(self.path, self.binding), self.state.trace)
        with Journal.open(self.path, self.binding) as journal:
            self.assertEqual(replay(journal.entries), self.state)
            journal.append(TraceEntry("recover", ()))
        self.assertEqual(replay(load_entries(self.path)), recover(self.state))
        before = self.path.read_bytes()
        with self.assertRaises(JournalError):
            Journal.create(self.path, self.binding)
        self.assertEqual(self.path.read_bytes(), before)

    def test_binding_and_account_switch_are_rejected(self):
        self.write()
        with self.assertRaisesRegex(JournalError, "BINDING_MISMATCH"):
            load_entries(self.path, replace(self.binding, account_id="other-synthetic-account"))
        with Journal.open(self.path) as journal:
            changed = update_context(self.state,
                                     replace(self.binding, account_id="other-synthetic-account"))
            with self.assertRaisesRegex(JournalError, "BINDING_CHANGED"):
                journal.append(changed.trace[-1])
            self.assertTrue(journal.poisoned)

    def test_second_writer_is_blocked_until_close_and_lock_file_is_not_a_lease(self):
        first = Journal.create(self.path, self.binding)
        try:
            with self.assertRaisesRegex(JournalError, "LOCK_UNAVAILABLE"):
                Journal.open(self.path)
        finally:
            first.close()
        self.assertTrue(Path(str(self.path) + ".lock").exists())
        with Journal.open(self.path) as second:
            self.assertEqual(second.entries, (TraceEntry("start", (self.binding,)),))

    def test_partial_tail_empty_file_and_interior_corruption_never_repair(self):
        self.write()
        good = self.path.read_bytes()
        for raw in (b"", good[:-1], good + b'{"format":',
                    good.replace(b"journal-test-epoch", b"journal-test-Xpoch", 1)):
            with self.subTest(length=len(raw)):
                self.path.write_bytes(raw)
                with self.assertRaises(JournalError):
                    load_entries(self.path)
                self.assertEqual(self.path.read_bytes(), raw)
                with self.assertRaises(JournalError):
                    Journal.open(self.path)
                self.assertEqual(self.path.read_bytes(), raw)

    def test_sequence_gap_duplicate_fork_unknown_schema_and_foreign_binding_fail(self):
        self.write()
        good = self.frames()
        variants = []
        for index, field, value in ((1, "sequence", 99), (1, "sequence", 1),
                                    (1, "previous_hash", "f" * 64),
                                    (0, "version", 999), (1, "binding_hash", "f" * 64)):
            rows = json.loads(json.dumps(good))
            rows[index][field] = value
            # Recompute checksum deliberately: structural/binding checks must
            # stand independently of checksum corruption detection.
            body = {key: item for key, item in rows[index].items() if key != "checksum"}
            rows[index]["checksum"] = hashlib.sha256(canonical_bytes(body)).hexdigest()
            variants.append(rows)
        variants.append(good[:2] + good[1:])
        for frames in variants:
            self.rewrite(frames)
            with self.assertRaises(JournalError):
                load_entries(self.path)

    def test_invalid_transition_cannot_be_written(self):
        with Journal.create(self.path, self.binding) as journal:
            before = self.path.read_bytes()
            with self.assertRaisesRegex(JournalError, "INVALID_TRANSITION_TRACE"):
                journal.append(TraceEntry("send_synthetic", ("nonexistent", None, 1000)))
            self.assertTrue(journal.poisoned)
            self.assertEqual(self.path.read_bytes(), before)

    def test_append_detects_prefix_mutation_before_another_write(self):
        with Journal.create(self.path, self.binding) as journal:
            self.path.write_bytes(self.path.read_bytes()[:-1])
            broken = self.path.read_bytes()
            with self.assertRaises(JournalError):
                journal.append(self.state.trace[1])
            self.assertTrue(journal.poisoned)
            self.assertEqual(self.path.read_bytes(), broken)

    def test_io_failure_poisoning_keeps_visibility_and_forbids_retry(self):
        for method in ("_write", "_flush", "_fsync"):
            with self.subTest(method=method):
                path = self.path.with_name(method + ".jsonl")
                with Journal.create(path, self.binding) as journal:
                    previous = journal.entries
                    with patch.object(journal, method, side_effect=OSError("injected storage failure")):
                        with self.assertRaises(JournalError):
                            journal.append(self.state.trace[1])
                    self.assertTrue(journal.poisoned)
                    self.assertEqual(journal.entries, previous)
                    with self.assertRaisesRegex(JournalError, "POISONED"):
                        journal.append(self.state.trace[1])

    def test_actual_short_write_leaves_quarantined_tail_with_no_truncate(self):
        with Journal.create(self.path, self.binding) as journal:
            original = journal._write
            def partial(data):
                return original(data[:len(data) // 2])
            with patch.object(journal, "_write", side_effect=partial):
                with self.assertRaisesRegex(JournalError, "SHORT_JOURNAL_WRITE"):
                    journal.append(self.state.trace[1])
            self.assertTrue(journal.poisoned)
        damaged = self.path.read_bytes()
        with self.assertRaises(JournalError):
            load_entries(self.path)
        self.assertEqual(self.path.read_bytes(), damaged)

    def test_complete_but_failed_fsync_recovery_retains_unknown_obligation(self):
        self.write(count=3)  # start/propose/approve; reserve is the faulted append.
        with Journal.open(self.path) as journal:
            previous = journal.entries
            with patch.object(journal, "_fsync", side_effect=OSError("unknown commit result")):
                with self.assertRaises(JournalError):
                    journal.append(self.state.trace[-1])
            self.assertEqual(journal.entries, previous)
        # A full frame can be visible after failed fsync; this is NOT proof of
        # physical power-loss durability. Recovery must conservatively retain it.
        restored = recover(replay(load_entries(self.path)))
        self.assertEqual(restored.get(self.intent.client_intent_id).phase, Phase.UNKNOWN)
        self.assertEqual(restored.ledger.unknown_risk, Decimal("27.50"))
        self.assertEqual(restored.requests, ())

    def test_fault_hook_order_and_after_fsync_exception_are_fail_closed(self):
        labels = []
        def hook(label, journal):
            labels.append(label)
            if len(journal.entries) and label == "after_fsync":
                raise OSError("response after fsync lost")
        with Journal.create(self.path, self.binding, fault_hook=hook) as journal:
            self.assertEqual(labels, ["before_write", "after_write", "before_flush",
                                      "after_flush", "before_fsync", "after_fsync"])
            previous = journal.entries
            with self.assertRaises(JournalError):
                journal.append(self.state.trace[1])
            self.assertTrue(journal.poisoned)
            self.assertEqual(journal.entries, previous)

    def test_interrupted_write_poisoning_prevents_caught_interrupt_from_resuming_writer(self):
        with Journal.create(self.path, self.binding) as journal:
            def interrupt(label, unused_journal):
                if label == "after_write":
                    raise KeyboardInterrupt()
            journal.fault_hook = interrupt
            previous = journal.entries
            with self.assertRaises(KeyboardInterrupt):
                journal.append(self.state.trace[1])
            self.assertTrue(journal.poisoned)
            self.assertEqual(journal.entries, previous)
            journal.fault_hook = None
            with self.assertRaisesRegex(JournalError, "POISONED"):
                journal.append(self.state.trace[1])


if __name__ == "__main__":
    unittest.main()
