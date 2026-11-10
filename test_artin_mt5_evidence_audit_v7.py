"""Tests use synthetic candles and receipts. No MT5, MetaEditor, broker, or orders."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from artin_mt5_durable_outbox_v5 import ObserverBlocked, pack, sha
from artin_mt5_local_observer_launcher import poll_once, state_paths
from artin_mt5_evidence_audit_v7 import AuditBlocked, audit_chain, observe, main
from test_artin_mt5_incremental_observer_v4 import fixture, source


class V7EvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.output = self.root / 'V5'
        self.csv = self.root / 'artin_v13_demo_TestServer_123_XAUUSD_M15_recovery_v2.csv'
        self.rows = fixture()
        self.csv.write_bytes(source(self.rows, 5))
        self.state, self.outbox, self.source_id = state_paths(self.csv, self.output)

    def poll(self):
        return poll_once(self.csv, self.output, settle_seconds=0)

    def test_missing_v5_checkpoint_is_blocked(self):
        with self.assertRaisesRegex(AuditBlocked, 'V5_CHECKPOINT_NOT_FOUND'):
            audit_chain(self.csv, self.state, self.outbox)
        self.assertFalse(self.output.exists())

    def test_first_receipt_replayed_not_broker_authenticated(self):
        self.poll()
        report = audit_chain(self.csv, self.state, self.outbox)
        self.assertEqual(report['verified_receipts'], 1)
        self.assertEqual(report['verified_closed_bars'], 5)
        self.assertEqual(report['orders_sent'], 0)
        self.assertTrue(report['all_13_trade_routes_blocked'])
        self.assertFalse(report['broker_session_authenticated'])
        self.assertFalse(report['mt5_demo_chart_attachment_verified'])

    def test_two_receipts_replayed_and_prior_witness_advances(self):
        self.poll()
        first = observe(self.csv, self.output)
        self.assertEqual(first['local_file_progress_since_prior_v7_check'], 'FIRST_LOCAL_FILE_OBSERVATION')
        self.assertIsNone(first['new_closed_bars_since_prior_v7_check'])
        unchanged = observe(self.csv, self.output)
        self.assertEqual(unchanged['local_file_progress_since_prior_v7_check'], 'UNCHANGED_LOCAL_FILES')
        self.csv.write_bytes(source(self.rows, 8))
        newer = observe(self.csv, self.output, capture_new=True, settle_seconds=0)
        self.assertEqual(newer['verified_receipts'], 2)
        self.assertEqual(newer['verified_closed_bars'], 8)
        self.assertEqual(newer['new_closed_bars_since_prior_v7_check'], 3)
        self.assertEqual(newer['local_file_progress_since_prior_v7_check'], 'ADDITIONAL_CLOSED_BARS_IN_LOCAL_FILES')
        self.assertEqual(newer['orders_sent'], 0)

    def test_old_receipt_tamper_detected_even_when_latest_good(self):
        self.poll()
        self.csv.write_bytes(source(self.rows, 8))
        self.poll()
        receipts = sorted(self.outbox.glob('batch_*.json'))
        old = receipts[0]
        old.write_bytes(old.read_bytes() + b' ')
        with self.assertRaisesRegex(ObserverBlocked, 'RECEIPT_SHA_FILENAME_MISMATCH'):
            audit_chain(self.csv, self.state, self.outbox)

    def test_old_receipt_report_rehashed_still_rejected(self):
        self.poll()
        self.csv.write_bytes(source(self.rows, 8))
        self.poll()
        old = sorted(self.outbox.glob('batch_*.json'))[0]
        d = json.loads(old.read_bytes())
        d['report']['raw_market_observations_not_teacher_signals'][0]['body_size'] = 999
        raw = pack(d)
        renamed = old.with_name('batch_000001_' + sha(raw)[:16] + '.json')
        old.unlink(); renamed.write_bytes(raw)
        with self.assertRaisesRegex(AuditBlocked, 'V5_RECEIPT_REPORT_NOT_REPRODUCIBLE'):
            audit_chain(self.csv, self.state, self.outbox)

    def test_missing_prior_receipt_fails_closed(self):
        self.poll(); self.csv.write_bytes(source(self.rows,8)); self.poll()
        sorted(self.outbox.glob('batch_*.json'))[0].unlink()
        with self.assertRaisesRegex(AuditBlocked, 'V5_RECEIPT_CHAIN_LENGTH_MISMATCH'):
            audit_chain(self.csv, self.state, self.outbox)

    def test_csv_unprocessed_suffix_blocks_observation(self):
        self.poll()
        self.csv.write_bytes(source(self.rows, 8))
        r = audit_chain(self.csv, self.state, self.outbox)
        self.assertGreater(r['unprocessed_csv_bytes_after_checkpoint'], 0)
        with self.assertRaisesRegex(AuditBlocked, 'V5_CHECKPOINT_TRAILS_EXISTING_SOURCE_CSV'):
            observe(self.csv, self.output)
        self.assertFalse((self.state.parent / 'v7_file_witness.json').exists())

    def test_no_new_bars_capture_is_idempotent(self):
        first = observe(self.csv, self.output, capture_new=True, settle_seconds=0)
        second = observe(self.csv, self.output, capture_new=True, settle_seconds=0)
        self.assertEqual(first['verified_receipts'], second['verified_receipts'])
        self.assertEqual(second['new_closed_bars_since_prior_v7_check'], 0)
        self.assertEqual(len(list(self.outbox.glob('batch_*.json'))), 1)

    def test_witness_bad_json_blocks_and_preserves_v5(self):
        self.poll(); observe(self.csv,self.output)
        checkpoint_before = self.state.read_bytes()
        (self.state.parent/'v7_file_witness.json').write_text('{')
        with self.assertRaisesRegex(AuditBlocked, 'CORRUPT_V7_WITNESS'):
            observe(self.csv,self.output)
        self.assertEqual(self.state.read_bytes(), checkpoint_before)

    def test_witness_same_count_wrong_hash_blocks(self):
        self.poll(); observe(self.csv,self.output)
        w = self.state.parent/'v7_file_witness.json'
        x=json.loads(w.read_bytes()); x['sha256']='f'*64; w.write_text(json.dumps(x))
        with self.assertRaisesRegex(AuditBlocked, 'V7_SAME_ROW_COUNT_DIFFERENT_SOURCE'):
            observe(self.csv,self.output)

    def test_witness_other_source_blocks(self):
        self.poll(); observe(self.csv,self.output)
        w=self.state.parent/'v7_file_witness.json'
        x=json.loads(w.read_bytes());x['source_id']='another';w.write_text(json.dumps(x))
        with self.assertRaisesRegex(AuditBlocked, 'INVALID_V7_WITNESS_IDENTITY'):
            observe(self.csv,self.output)

    def test_capture_new_does_not_modify_csv(self):
        old = self.csv.read_bytes()
        observe(self.csv,self.output,capture_new=True,settle_seconds=0)
        self.assertEqual(self.csv.read_bytes(),old)

    def test_main_cli_captures_and_reports(self):
        self.assertEqual(main(['--csv',str(self.csv),'--output-root',str(self.output),
                               '--capture-new','--settle-seconds','0']), 0)

    def test_main_cli_rejects_missing_input_without_writing(self):
        self.csv.unlink()
        self.assertEqual(main(['--csv',str(self.csv),'--output-root',str(self.output)]), 2)
        self.assertFalse(self.output.exists())

    def test_malformed_witness_cannot_advance_state(self):
        self.poll()
        with patch('artin_mt5_evidence_audit_v7.atomic_write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):observe(self.csv,self.output)
        self.assertEqual(json.loads(self.state.read_text())['sequence'],1)

if __name__ == '__main__':
    unittest.main()