"""V5 crash-window and integrity tests with embedded SYNTHETIC M15 only.

No MetaEditor, Eplanet DEMO runtime, teacher interpretation or trades involved.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from artin_mt5_durable_outbox_v5 import (
    ObserverBlocked, SCHEMA, RECEIPT_SCHEMA, atomic_write, pack, run,
    sha, state_lock, _receipt_for,
)
from test_artin_mt5_incremental_observer_v4 import fixture, source


class SimulatedCrash(RuntimeError): pass


class DurableObserverV5(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.csv = self.root / 'broker.csv'
        self.state = self.root / 'progress.json'
        self.outbox = self.root / 'evidence'
        self.lines = fixture()
        self.first = source(self.lines, 5)
        self.next = source(self.lines, 8)
        self.csv.write_bytes(self.first)

    def cmd(self, **kw):
        return run(self.csv, self.state, self.outbox, **kw)

    def receipts(self):
        return sorted(self.outbox.glob('batch_*.json'))

    def state_obj(self):
        return json.loads(self.state.read_bytes())

    def test_commits_receipt_then_progress(self):
        result = self.cmd()
        self.assertEqual(result['new_closed_bars'], 5)
        self.assertEqual(result['status'], 'DURABLE_NEW_CLOSED_BARS')
        self.assertEqual(len(self.receipts()), 1)
        env = self.state_obj()
        self.assertEqual(env['schema'], SCHEMA)
        self.assertEqual(env['sequence'], 1)
        self.assertEqual(env['checkpoint']['rows_seen'], 5)
        self.assertEqual(env['last_receipt']['sha256'], sha(self.receipts()[0].read_bytes()))

    def test_report_is_immutable_exact_hash(self):
        self.cmd()
        receipt = self.receipts()[0]
        d, h = _receipt_for(receipt, 1)
        self.assertEqual(h, sha(receipt.read_bytes()))
        self.assertEqual(d['schema'], RECEIPT_SCHEMA)
        self.assertEqual(d['report']['new_closed_bars_processed'], 5)
        self.assertEqual(len(d['report']['route_states']), 13)
        self.assertTrue(all(not x['broker_order_permitted'] for x in d['report']['route_states']))

    def test_no_new_bars_does_not_duplicate(self):
        self.cmd()
        state = self.state.read_bytes()
        receipt = self.receipts()[0].read_bytes()
        again = self.cmd()
        self.assertEqual(again['status'], 'NO_NEW_BARS')
        self.assertEqual(again['new_closed_bars'], 0)
        self.assertEqual(self.state.read_bytes(), state)
        self.assertEqual(len(self.receipts()), 1)
        self.assertEqual(self.receipts()[0].read_bytes(), receipt)

    def test_two_batches_sequenced_with_exact_counts(self):
        self.cmd()
        self.csv.write_bytes(self.next)
        result = self.cmd()
        self.assertEqual(result['new_closed_bars'], 3)
        self.assertEqual(self.state_obj()['sequence'], 2)
        self.assertEqual(self.state_obj()['checkpoint']['rows_seen'], 8)
        self.assertEqual(len(self.receipts()), 2)
        self.assertEqual(_receipt_for(self.receipts()[1], 2)[0]['report']['new_closed_bars_processed'], 3)

    def test_crash_after_receipt_before_checkpoint_recovers(self):
        def crash(_): raise SimulatedCrash('forced termination')
        with self.assertRaises(SimulatedCrash): self.cmd(on_receipt_committed=crash)
        self.assertFalse(self.state.exists())
        old_report = self.receipts()[0].read_bytes()
        recovery = self.cmd()
        self.assertEqual(recovery['recovered_uncommitted_receipts'], 1)
        self.assertEqual(recovery['status'], 'NO_NEW_BARS')
        self.assertEqual(self.state_obj()['checkpoint']['rows_seen'], 5)
        self.assertEqual(self.receipts()[0].read_bytes(), old_report)

    def test_crash_after_first_checkpoint_before_next_commit(self):
        self.cmd()
        prior = self.state.read_bytes()
        self.csv.write_bytes(self.next)
        with self.assertRaises(SimulatedCrash):
            self.cmd(on_receipt_committed=lambda _: (_ for _ in ()).throw(SimulatedCrash()))
        self.assertEqual(self.state.read_bytes(), prior)
        self.assertEqual(len(self.receipts()), 2)
        recovery = self.cmd()
        self.assertEqual(recovery['recovered_uncommitted_receipts'], 1)
        self.assertEqual(self.state_obj()['sequence'], 2)
        self.assertEqual(self.state_obj()['checkpoint']['rows_seen'], 8)
        self.assertEqual(len(self.receipts()), 2)

    def test_crash_then_csv_appends_before_recovery(self):
        with self.assertRaises(SimulatedCrash):
            self.cmd(on_receipt_committed=lambda _: (_ for _ in ()).throw(SimulatedCrash()))
        self.csv.write_bytes(self.next)
        result = self.cmd()
        self.assertEqual(result['recovered_uncommitted_receipts'], 1)
        self.assertEqual(result['new_closed_bars'], 3)
        self.assertEqual(self.state_obj()['checkpoint']['rows_seen'], 8)
        self.assertEqual(len(self.receipts()), 2)
        self.assertEqual([_receipt_for(p, n)[0]['report']['new_closed_bars_processed'] for n,p in enumerate(self.receipts(),1)], [5,3])

    def test_recovery_rejects_changed_old_csv_history(self):
        with self.assertRaises(SimulatedCrash):
            self.cmd(on_receipt_committed=lambda _: (_ for _ in ()).throw(SimulatedCrash()))
        original = self.csv.read_bytes()
        self.csv.write_bytes(original.replace(b'3000.0,3002.0', b'3000.1,3002.0', 1))
        with self.assertRaisesRegex(ObserverBlocked, 'ORPHAN_CSV_PREFIX_MISMATCH'):
            self.cmd()
        self.assertFalse(self.state.exists())

    def test_recovery_rejects_rehashed_forged_report(self):
        with self.assertRaises(SimulatedCrash):
            self.cmd(on_receipt_committed=lambda _: (_ for _ in ()).throw(SimulatedCrash()))
        p=self.receipts()[0]; d=json.loads(p.read_bytes())
        d['report']['raw_market_observations_not_teacher_signals'][0]['body_size']=999.0
        raw=pack(d)
        replacement=p.with_name('batch_000001_'+sha(raw)[:16]+'.json')
        p.unlink(); replacement.write_bytes(raw)
        with self.assertRaisesRegex(ObserverBlocked,'ORPHAN_REPORT_NOT_REPRODUCIBLE'):
            self.cmd()
        self.assertFalse(self.state.exists())

    def test_recovery_rejects_forged_semantic_pass(self):
        with self.assertRaises(SimulatedCrash):
            self.cmd(on_receipt_committed=lambda _: (_ for _ in ()).throw(SimulatedCrash()))
        p=self.receipts()[0]; d=json.loads(p.read_bytes())
        d['report']['route_states'][0]['broker_order_permitted']=True
        raw=pack(d); p.unlink()
        (self.outbox/('batch_000001_'+sha(raw)[:16]+'.json')).write_bytes(raw)
        with self.assertRaisesRegex(ObserverBlocked,'RECEIPT_ROUTES_NOT_ALL_BLOCKED'):
            self.cmd()

    def test_receipt_tamper_after_checkpoint_fails(self):
        self.cmd(); p=self.receipts()[0]
        p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ObserverBlocked, 'RECEIPT_SHA_FILENAME_MISMATCH'):
            self.cmd()

    def test_deleted_receipt_fails_closed(self):
        self.cmd(); self.receipts()[0].unlink()
        with self.assertRaisesRegex(ObserverBlocked,'MISSING_OR_OVERSIZED_EVIDENCE_FILE|FileNotFound'):
            self.cmd()

    def test_modified_history_after_checkpoint_fails(self):
        self.cmd(); state=self.state.read_bytes()
        self.csv.write_bytes(self.next.replace(b'3000.0,3002.0', b'3000.1,3002.0', 1))
        with self.assertRaisesRegex(ObserverBlocked,'SOURCE_HISTORY_REWRITTEN'):
            self.cmd()
        self.assertEqual(self.state.read_bytes(),state)

    def test_truncation_after_checkpoint_fails(self):
        self.csv.write_bytes(self.next); self.cmd()
        self.csv.write_bytes(self.first)
        with self.assertRaisesRegex(ObserverBlocked,'SOURCE_TRUNCATED'):
            self.cmd()

    def test_partial_append_fails_preserving_all_receipts(self):
        self.cmd(); saved=self.state.read_bytes()
        self.csv.write_bytes(self.next[:-5])
        with self.assertRaisesRegex(ObserverBlocked,'PARTIAL_ROW'):
            self.cmd()
        self.assertEqual(self.state.read_bytes(),saved)
        self.assertEqual(len(self.receipts()),1)

    def test_state_corrupted_no_progress(self):
        self.cmd(); self.state.write_text('{')
        with self.assertRaisesRegex(ObserverBlocked,'MALFORMED_EVIDENCE_JSON'):
            self.cmd()

    def test_output_aliases_refused(self):
        with self.assertRaisesRegex(ObserverBlocked,'OUTPUT_PATH_ALIASES_INPUT'):
            run(self.csv,self.csv,self.outbox)

    def test_concurrent_lock_refused(self):
        path=self.state.with_suffix('.json.lock')
        with state_lock(path):
            with self.assertRaisesRegex(ObserverBlocked, 'CONCURRENT_OBSERVER_PROCESS'):
                self.cmd()
        self.assertFalse(self.state.exists())

    def test_immutable_receipt_cannot_be_rewritten(self):
        target=self.root/'receipt.json'
        atomic_write(target,b'fixed',immutable=True)
        with self.assertRaisesRegex(ObserverBlocked,'EXISTING_OUTBOX_RECEIPT_DIFFERS'):
            atomic_write(target,b'changed',immutable=True)
        self.assertEqual(target.read_bytes(),b'fixed')

    def test_state_write_failure_keeps_report_and_is_recoverable(self):
        from artin_mt5_durable_outbox_v5 import atomic_write as real_write
        def failure(path, data, **kw):
            if Path(path)==self.state: raise OSError('simulated state write failure')
            return real_write(path,data,**kw)
        with mock.patch('artin_mt5_durable_outbox_v5.atomic_write', side_effect=failure):
            with self.assertRaises(OSError): self.cmd()
        self.assertFalse(self.state.exists())
        self.assertEqual(len(self.receipts()),1)
        self.assertEqual(self.cmd()['recovered_uncommitted_receipts'],1)

    def test_receipt_write_failure_keeps_checkpoint_unmoved(self):
        from artin_mt5_durable_outbox_v5 import atomic_write as real_write
        def failure(path,data,**kw):
            if kw.get('immutable'): raise OSError('simulated report write failure')
            return real_write(path,data,**kw)
        with mock.patch('artin_mt5_durable_outbox_v5.atomic_write', side_effect=failure):
            with self.assertRaises(OSError): self.cmd()
        self.assertFalse(self.state.exists())
        self.assertEqual(len(self.receipts()),0)

    def test_snapshot_is_never_changed(self):
        before=self.csv.read_bytes()
        self.cmd()
        self.assertEqual(self.csv.read_bytes(), before)

    def test_no_trade_order_broker_or_teacher_claim(self):
        r=self.cmd(); receipt=json.loads(self.receipts()[0].read_bytes())
        self.assertEqual(r['orders_sent'], 0)
        self.assertFalse(r['teacher_semantics_certified'])
        self.assertTrue(r['source_claim_not_authenticated'])
        self.assertEqual(receipt['report']['trades_backtested'], 0)
        self.assertFalse(receipt['checkpoint_after']['trading_authorized'])

    def test_receipt_sequence_is_stable_not_timestamp_based(self):
        first=self.cmd(); self.csv.write_bytes(self.next); second=self.cmd()
        self.assertTrue(first['last_receipt'].startswith('batch_000001_'))
        self.assertTrue(second['last_receipt'].startswith('batch_000002_'))


if __name__=='__main__': unittest.main(verbosity=2)