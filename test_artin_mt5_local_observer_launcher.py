"""Synthetic-only integration tests: local MT5 CSV path -> unchanged V5 outbox."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from artin_mt5_local_observer_launcher import (LaunchBlocked, common_files_root,
    main, poll_once, select_source, state_paths, verify_quiet_snapshot)
from test_artin_mt5_incremental_observer_v4 import fixture, source


class LocalObserverIntegrationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.common = self.base / 'MetaQuotes' / 'Terminal' / 'Common' / 'Files'
        self.common.mkdir(parents=True)
        self.csv = self.common / 'artin_v13_demo_TestServer_123_XAUUSD_M15_recovery_v2.csv'
        self.output = self.base / 'read-only-outbox'
        self.rows = fixture()
        self.csv.write_bytes(source(self.rows, 5))

    def test_common_path(self):
        self.assertEqual(common_files_root(str(self.base)), self.common)

    def test_autodiscovery_unique_valid_csv(self):
        self.assertEqual(select_source(common_dir=self.common), self.csv.resolve())

    def test_autodiscovery_ambiguous_never_picks_account(self):
        (self.common / 'artin_v13_demo_Another_123_XAUUSD_M15_recovery_v2.csv').write_bytes(b'raw')
        with self.assertRaisesRegex(LaunchBlocked, 'MULTIPLE'):
            select_source(common_dir=self.common)

    def test_invalid_filename_rejected(self):
        with self.assertRaisesRegex(LaunchBlocked, 'NOT_AN_ARTIN'):
            select_source(self.base / 'untrusted.csv')

    def test_no_existing_collector_fails(self):
        self.csv.unlink()
        with self.assertRaisesRegex(LaunchBlocked, 'NO_ARTIN'):
            select_source(common_dir=self.common)

    def test_unstable_csv_never_calls_v5(self):
        with patch('artin_mt5_local_observer_launcher.time.sleep', side_effect=lambda _: self.csv.write_bytes(source(self.rows, 8))):
            with self.assertRaisesRegex(LaunchBlocked, 'STILL_BEING_WRITTEN'):
                poll_once(self.csv, self.output, settle_seconds=0.01)
        self.assertFalse(self.output.exists())

    def test_first_batch_is_real_v5_receipt_not_launcher_claim(self):
        before = self.csv.read_bytes()
        result = poll_once(self.csv, self.output, settle_seconds=0)
        self.assertEqual(result['new_closed_bars'], 5)
        self.assertFalse(result['mt5_compiled_or_live_demo_attested'])
        self.assertEqual(result['orders_sent'], 0)
        state, outbox, _ = state_paths(self.csv, self.output)
        self.assertTrue(state.is_file())
        receipt = next(outbox.glob('batch_*.json'))
        body = json.loads(receipt.read_bytes())
        self.assertEqual(body['report']['route_count'], 13)
        self.assertTrue(all(not route['broker_order_permitted'] for route in body['report']['route_states']))
        self.assertEqual(self.csv.read_bytes(), before)

    def test_restart_appends_new_bars_without_duplicates(self):
        first = poll_once(self.csv, self.output, settle_seconds=0)
        second = poll_once(self.csv, self.output, settle_seconds=0)
        self.csv.write_bytes(source(self.rows, 8))
        third = poll_once(self.csv, self.output, settle_seconds=0)
        state, outbox, _ = state_paths(self.csv, self.output)
        self.assertEqual([first['new_closed_bars'], second['new_closed_bars'], third['new_closed_bars']], [5, 0, 3])
        self.assertEqual(len(list(outbox.glob('batch_*.json'))), 2)
        self.assertEqual(json.loads(state.read_bytes())['checkpoint']['rows_seen'], 8)

    def test_corrupt_history_fails_closed(self):
        poll_once(self.csv, self.output, settle_seconds=0)
        self.csv.write_bytes(source(self.rows, 8).replace(b'3000.0,3002.0', b'3000.1,3002.0', 1))
        from artin_mt5_durable_outbox_v5 import ObserverBlocked
        with self.assertRaisesRegex(ObserverBlocked, 'SOURCE_HISTORY_REWRITTEN'):
            poll_once(self.csv, self.output, settle_seconds=0)

    def test_partial_append_never_advances_checkpoint(self):
        poll_once(self.csv, self.output, settle_seconds=0)
        state, _, _ = state_paths(self.csv, self.output)
        old = state.read_bytes()
        self.csv.write_bytes(source(self.rows, 8)[:-4])
        from artin_mt5_durable_outbox_v5 import ObserverBlocked
        with self.assertRaisesRegex(ObserverBlocked, 'PARTIAL_ROW'):
            poll_once(self.csv, self.output, settle_seconds=0)
        self.assertEqual(state.read_bytes(), old)

    def test_different_mt5_sources_get_separate_state(self):
        other = self.common / 'artin_v13_demo_TestServer_999_XAUUSD_M15_recovery_v2.csv'
        self.assertNotEqual(state_paths(self.csv, self.output)[0], state_paths(other, self.output)[0])

    def test_cli_once_success(self):
        self.assertEqual(main(['--csv',str(self.csv),'--output-root',str(self.output),'--settle-seconds','0']),0)

    def test_cli_watch_bounded_uses_existing_data_only(self):
        self.assertEqual(main(['--csv',str(self.csv),'--output-root',str(self.output),'--settle-seconds','0',
            '--watch','--poll-seconds','0.1','--max-polls','2']),0)

    def test_cli_missing_csv_reports_blocked(self):
        self.csv.unlink()
        self.assertEqual(main(['--csv',str(self.csv),'--output-root',str(self.output)]),2)

    def test_no_source_file_creation_or_order_file(self):
        poll_once(self.csv, self.output, settle_seconds=0)
        self.assertEqual([p for p in self.common.iterdir()], [self.csv])
        self.assertFalse(any(p.suffix.lower() in ('.ex5','.mq5') for p in self.output.rglob('*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)