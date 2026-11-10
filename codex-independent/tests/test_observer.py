"""SDK observation tests use an injected fake module, never a real terminal."""
import ast
import contextlib
import copy
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import observe_demo

FENCE=18034
EXPECTED_DATA=Path('C:/TEST_ONLY/ePlanet/Data')
TERMINAL=Path('C:/TEST_ONLY/ePlanet/terminal64.exe')

def rate(stamp):
    return dict(time=stamp,open=2300.5,high=2302.75,low=2299.25,close=2301.5,
                tick_volume=100,spread=22,real_volume=0)

def fake_mt():
    account=types.SimpleNamespace(login=12345,trade_mode=0,server='ePlanet-MT5',company='ePlanet Brokers')
    terminal=types.SimpleNamespace(data_path=str(EXPECTED_DATA),connected=True)
    fake=types.ModuleType('MetaTrader5')
    fake.ACCOUNT_TRADE_MODE_DEMO=0;fake.TIMEFRAME_M15=15
    fake.initialize=Mock(return_value=True)
    fake.shutdown=Mock()
    fake.account_info=Mock(side_effect=[copy.copy(account),copy.copy(account)])
    fake.terminal_info=Mock(side_effect=[copy.copy(terminal),copy.copy(terminal)])
    fake.copy_rates_from_pos=Mock(side_effect=[ [rate(FENCE)],
        [rate(FENCE-1800),rate(FENCE-900)], [rate(FENCE)] ])
    return fake,account,terminal

class ObserverTests(unittest.TestCase):
    def setUp(self):self.mt,self.account,self.terminal=fake_mt()
    def capture(self,count=2,latest=None,backfill_from=None):
        with patch.dict(sys.modules,{'MetaTrader5':self.mt}):
            return observe_demo.capture(count,TERMINAL,EXPECTED_DATA,latest,backfill_from)

    def assert_identity_rejected_before_history(self,error):
        with self.assertRaisesRegex(RuntimeError,error):self.capture()
        self.mt.copy_rates_from_pos.assert_not_called();self.mt.shutdown.assert_called_once()

    def test_live_account_fails_before_any_rates_request(self):
        self.account.trade_mode=2;self.mt.account_info.side_effect=[self.account]
        self.assert_identity_rejected_before_history('EPLANET_DEMO_REQUIRED')

    def test_wrong_server_fails_before_any_rates_request(self):
        self.account.server='Another-Demo';self.mt.account_info.side_effect=[self.account]
        self.assert_identity_rejected_before_history('EPLANET_DEMO_REQUIRED')

    def test_wrong_company_fails_before_any_rates_request(self):
        self.account.company='Unrelated company';self.mt.account_info.side_effect=[self.account]
        self.assert_identity_rejected_before_history('TERMINAL_IDENTITY_MISMATCH')

    def test_wrong_terminal_data_path_fails_before_any_rates_request(self):
        self.terminal.data_path='C:/TEST_ONLY/OtherTerminal';self.mt.terminal_info.side_effect=[self.terminal]
        self.assert_identity_rejected_before_history('TERMINAL_IDENTITY_MISMATCH')

    def test_disconnected_fails_before_any_rates_request(self):
        self.terminal.connected=False;self.mt.terminal_info.side_effect=[self.terminal]
        self.assert_identity_rejected_before_history('DEMO_DISCONNECTED')

    def test_identity_unavailable_fails_before_any_rates_request(self):
        self.mt.account_info.side_effect=[None]
        self.assert_identity_rejected_before_history('IDENTITY_UNAVAILABLE')

    def test_closed_history_starts_at_position_one_and_preserves_native_seconds(self):
        doc=self.capture()
        self.assertEqual(self.mt.copy_rates_from_pos.call_args_list[0].args,('XAUUSD.st',15,0,1))
        self.assertEqual(self.mt.copy_rates_from_pos.call_args_list[1].args,('XAUUSD.st',15,1,2))
        self.assertEqual(self.mt.copy_rates_from_pos.call_args_list[2].args,('XAUUSD.st',15,0,1))
        self.assertEqual([b['time'] for b in doc['bars']],[FENCE-1800,FENCE-900])
        self.assertEqual(doc['current_bar_open_native'],FENCE)
        self.assertTrue(doc['native_time_preserved']);self.assertFalse(doc['time_conversion_applied'])
        self.assertFalse(doc['orders_enabled']);self.mt.shutdown.assert_called_once()
        # Account identifiers are not included in capture output.
        self.assertNotIn('12345',json.dumps(doc))

    def test_backfill_window_covers_latest_native_watermark_plus_overlap(self):
        latest=FENCE-900*20
        self.mt.copy_rates_from_pos.side_effect=[[rate(FENCE)],
            [rate(latest),rate(FENCE-900)],[rate(FENCE)]]
        doc=self.capture(count=2,latest=latest)
        self.assertEqual(doc['requested'],24)
        self.assertEqual(self.mt.copy_rates_from_pos.call_args_list[1].args,('XAUUSD.st',15,1,24))

    def test_huge_backfill_fails_bounded_before_history_request(self):
        self.mt.copy_rates_from_pos.side_effect=[[rate(900*60000)]]
        with self.assertRaisesRegex(RuntimeError,'BOUNDED_BACKFILL_WINDOW_EXCEEDED'):
            self.capture(latest=900)
        self.assertEqual(self.mt.copy_rates_from_pos.call_count,1);self.mt.shutdown.assert_called_once()

    def test_insufficient_overlap_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'HISTORY_OVERLAP_UNAVAILABLE'):
            self.capture(latest=FENCE-900*3)
        self.mt.shutdown.assert_called_once()

    def test_native_fence_change_requires_retry_not_archive(self):
        self.mt.copy_rates_from_pos.side_effect=[[rate(FENCE)],[rate(FENCE-900)],[rate(FENCE+900)]]
        with self.assertRaisesRegex(RuntimeError,'BAR_BOUNDARY_CHANGED_RETRY'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_current_bar_unavailable_prevents_history(self):
        self.mt.copy_rates_from_pos.side_effect=[None]
        with self.assertRaisesRegex(RuntimeError,'CURRENT_BAR_UNAVAILABLE'):self.capture()
        self.assertEqual(self.mt.copy_rates_from_pos.call_count,1);self.mt.shutdown.assert_called_once()

    def test_empty_history_rejected_with_shutdown(self):
        self.mt.copy_rates_from_pos.side_effect=[[rate(FENCE)],[]]
        with self.assertRaisesRegex(RuntimeError,'CLOSED_HISTORY_UNAVAILABLE'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_changed_account_identity_rejected_after_read(self):
        after=copy.copy(self.account);after.login=67890
        self.mt.account_info.side_effect=[self.account,after]
        with self.assertRaisesRegex(RuntimeError,'IDENTITY_CHANGED_DURING_READ'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_switched_to_live_after_read_rejected(self):
        after=copy.copy(self.account);after.trade_mode=2
        self.mt.account_info.side_effect=[self.account,after]
        with self.assertRaisesRegex(RuntimeError,'IDENTITY_CHANGED_DURING_READ'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_company_switch_after_read_is_rejected(self):
        after=copy.copy(self.account);after.company='Other company'
        self.mt.account_info.side_effect=[self.account,after]
        with self.assertRaisesRegex(RuntimeError,'IDENTITY_CHANGED_DURING_READ'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_direct_capture_count_range_and_bool_fail_before_sdk_attach(self):
        for count in (0,50001,True,False,1.0):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError,'COUNT_OUT_OF_RANGE'):self.capture(count=count)
        self.mt.initialize.assert_not_called();self.mt.copy_rates_from_pos.assert_not_called()

    def test_latest_at_or_after_native_fence_is_rejected(self):
        for latest in (FENCE,FENCE+900,True,1.0):
            with self.subTest(latest=latest):
                self.mt,self.account,self.terminal=fake_mt()
                with self.assertRaisesRegex(RuntimeError,'INVALID_LATEST_WATERMARK'):self.capture(latest=latest)
                self.assertEqual(self.mt.copy_rates_from_pos.call_count,1);self.mt.shutdown.assert_called_once()

    def test_backfill_from_extends_window_older_than_latest(self):
        latest=FENCE-1800;earlier=FENCE-900*20
        self.mt.copy_rates_from_pos.side_effect=[[rate(FENCE)],
            [rate(earlier),rate(latest),rate(FENCE-900)],[rate(FENCE)]]
        result=self.capture(latest=latest,backfill_from=earlier)
        self.assertEqual(result['requested'],24)
        self.assertEqual(self.mt.copy_rates_from_pos.call_args_list[1].args,('XAUUSD.st',15,1,24))

    def test_session_gap_history_before_backfill_floor_does_not_expand_archive(self):
        # CopyRates can return actual bars from much earlier sessions while its
        # requested count came from elapsed wall-clock intervals.
        fence=900*100+34;floor=fence-900*4;latest=fence-900
        returned=[rate(fence-900*n) for n in (12,11,10,9,8,4,2,1)]
        def setup_cycle():
            self.mt,self.account,self.terminal=fake_mt()
            self.mt.copy_rates_from_pos.side_effect=[[rate(fence)],returned,[rate(fence)]]
        setup_cycle();doc=self.capture(latest=latest,backfill_from=floor)
        self.assertEqual(doc['native_rows_returned'],8)
        self.assertEqual(doc['received'],3)
        self.assertEqual(doc['requested'],8)
        self.assertFalse(doc['partial_history']) # count concerns native response, not filtered rows
        self.assertEqual([b['time'] for b in doc['bars']],[floor,fence-1800,latest])
        with tempfile.TemporaryDirectory() as tmp:
            archive=observe_demo.CandleArchive(tmp)
            archive.ingest([rate(floor),rate(latest)],current_bar_open=fence)
            first=archive.ingest(doc['bars'],current_bar_open=fence)
            self.assertEqual(first['added'],1)
            self.assertEqual(min(b['time'] for b in archive.read_bars()),floor)
            setup_cycle();again=self.capture(latest=latest,backfill_from=floor)
            second=archive.ingest(again['bars'],current_bar_open=fence)
            self.assertEqual(second['added'],0);self.assertEqual(second['duplicates'],3)
            self.assertEqual(archive.verify()['count'],3)
            self.assertEqual(min(b['time'] for b in archive.read_bars()),floor)

    def test_backfill_response_entirely_before_floor_fails_with_shutdown(self):
        floor=FENCE-1800
        self.mt.copy_rates_from_pos.side_effect=[[rate(FENCE)],
            [rate(floor-1800),rate(floor-900)],[rate(FENCE)]]
        with self.assertRaisesRegex(RuntimeError,'BACKFILL_RANGE_UNAVAILABLE'):
            self.capture(latest=FENCE-900,backfill_from=floor)
        self.mt.shutdown.assert_called_once()

    def test_oversized_interior_backfill_is_bounded_before_history(self):
        self.mt.copy_rates_from_pos.side_effect=[[rate(900*60000)]]
        with self.assertRaisesRegex(RuntimeError,'BOUNDED_BACKFILL_WINDOW_EXCEEDED'):
            self.capture(latest=900*59999,backfill_from=900)
        self.assertEqual(self.mt.copy_rates_from_pos.call_count,1);self.mt.shutdown.assert_called_once()

    def test_invalid_backfill_at_fence_or_noninteger_is_rejected(self):
        for watermark in (FENCE,FENCE+900,True,1.0):
            with self.subTest(watermark=watermark):
                self.mt,self.account,self.terminal=fake_mt()
                with self.assertRaisesRegex(RuntimeError,'INVALID_BACKFILL_WATERMARK'):
                    self.capture(latest=FENCE-900,backfill_from=watermark)
                self.assertEqual(self.mt.copy_rates_from_pos.call_count,1);self.mt.shutdown.assert_called_once()

    def test_cli_revisits_oldest_eligible_interior_gap_and_reports_deferred_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'checkpoint.json').write_text('{}')
            latest=900*100000
            archive=Mock();archive.verify.return_value={'latest_time':latest,'gaps':[
                {'after':latest-900*100},{'after':latest-900*60000},{'after':latest-900*200}]}
            archive.ingest.return_value={'added':1,'duplicates':0,'orders_enabled':False}
            capture_doc=dict(bars=[rate(latest)],current_bar_open_native=latest+900,
                receive_seconds=.1,attach_and_capture_seconds=.2)
            args=['observe_demo.py','--archive',str(root),'--snapshot',str(root/'snapshot.json'),
                '--report',str(root/'report.json'),'--count','2','--terminal',str(TERMINAL),
                '--expected-data',str(EXPECTED_DATA)]
            with patch.object(sys,'argv',args),patch.object(observe_demo,'CandleArchive',return_value=archive),\
                 patch.object(observe_demo,'capture',return_value=capture_doc) as capture,\
                 contextlib.redirect_stdout(io.StringIO()):
                observe_demo.main()
            self.assertEqual(capture.call_args.args,(2,TERMINAL,EXPECTED_DATA,latest,latest-900*200))
            result=json.loads((root/'report.json').read_text())
            self.assertEqual(result['older_gap_ranges_deferred'],1)
            self.assertEqual(result['interior_gap_revisit_from_native'],latest-900*200)
            self.assertEqual(result['orders_submitted'],0)
            archive.ingest.assert_called_once_with(capture_doc['bars'],current_bar_open=latest+900)
            self.mt.initialize.assert_not_called()

    def test_changed_server_or_datapath_or_connection_after_read_rejected(self):
        for change in ('server','path','connection'):
            with self.subTest(change=change):
                self.mt,self.account,self.terminal=fake_mt()
                after=copy.copy(self.account);end=copy.copy(self.terminal)
                if change=='server':after.server='AnotherServer'
                elif change=='path':end.data_path='C:/TEST_ONLY/Other'
                else:end.connected=False
                self.mt.account_info.side_effect=[self.account,after];self.mt.terminal_info.side_effect=[self.terminal,end]
                with self.assertRaisesRegex(RuntimeError,'IDENTITY_CHANGED_DURING_READ'):self.capture()
                self.mt.shutdown.assert_called_once()

    def test_shutdown_finally_on_sdk_exception(self):
        self.mt.copy_rates_from_pos.side_effect=RuntimeError('FAKE_READ_FAILURE')
        with self.assertRaisesRegex(RuntimeError,'FAKE_READ_FAILURE'):self.capture()
        self.mt.shutdown.assert_called_once()

    def test_failed_attach_never_reads_identity_or_history(self):
        self.mt.initialize.return_value=False
        with self.assertRaisesRegex(RuntimeError,'EXISTING_DEMO_ATTACH_FAILED'):self.capture()
        self.mt.account_info.assert_not_called();self.mt.copy_rates_from_pos.assert_not_called()

    def test_main_requires_explicit_terminal_and_data_identity(self):
        args=['observe_demo.py','--archive','unused','--report','unused','--snapshot','unused']
        with patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:observe_demo.main()
        self.assertEqual(error.exception.code,2);self.mt.initialize.assert_not_called()

    def test_source_has_no_trading_or_login_api(self):
        tree=ast.parse(Path(observe_demo.__file__).read_text(encoding='utf-8-sig'))
        forbidden={'order_send','order_check','login','positions_get','orders_get'}
        called={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
        self.assertFalse(called & forbidden)

if __name__=='__main__':unittest.main(verbosity=2)
