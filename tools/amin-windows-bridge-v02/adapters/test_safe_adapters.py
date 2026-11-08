import json
from pathlib import Path
import tempfile
import unittest
from safe_adapters import ReadOnlyMarketAdapter, RobotObserver, PolicyError, JsonlAuditSink


class MemorySink:
    def emit(self, code):
        pass


class Proxy:
    def __init__(self, mode='DEMO', broker='Eplanet', symbol='XAUUSD.st', fail=False):
        self.mode, self.broker, self.symbol, self.fail = mode, broker, symbol, fail
        self.calls = []
    def account_info(self):
        self.calls.append('account_info')
        if self.fail:
            raise RuntimeError('SECRET account 123 PRIVATE/path')
        return {'mode': self.mode, 'broker': self.broker, 'login': 'PRIVATE'}
    def symbol_info(self, name):
        self.calls.append('symbol_info')
        return {'name': self.symbol}
    def copy_rates_from_pos(self, *args):
        self.calls.append(('market', args))
        return [{'time': i * 900, 'open': 100, 'high': 101, 'low': 99, 'close': 100} for i in range(args[-1])]


def market(proxy=None, **kwargs):
    return ReadOnlyMarketAdapter(proxy or Proxy(), handshake_ok=True, session_consent=True, audit_sink=kwargs.pop('audit_sink', MemorySink()), **kwargs)


class AdapterTests(unittest.TestCase):
    def test_authorization_blocks_all_calls(self):
        p = Proxy()
        self.assertEqual(ReadOnlyMarketAdapter(p).inspect()['error'], 'AUTH_REQUIRED')
        self.assertEqual(p.calls, [])
    def test_real_blocks_market(self):
        p = Proxy(mode='REAL')
        self.assertEqual(market(p).inspect()['error'], 'DEMO_REQUIRED')
        self.assertEqual(p.calls, ['account_info'])
    def test_broker_blocks_market(self):
        p = Proxy(broker='Other')
        self.assertEqual(market(p).inspect()['error'], 'BROKER_DENIED')
        self.assertEqual(p.calls, ['account_info'])
    def test_symbol_blocks_before_sdk(self):
        p = Proxy()
        self.assertEqual(market(p).inspect(symbol='XAUUSD')['error'], 'SYMBOL_DENIED')
        self.assertEqual(p.calls, [])
    def test_actual_symbol_blocks_market(self):
        p = Proxy(symbol='XAUUSD')
        self.assertEqual(market(p).inspect()['error'], 'SYMBOL_DENIED')
        self.assertNotIn('market', str(p.calls))
    def test_counts(self):
        for value in (0, 101, True, 1.5, '100'):
            p = Proxy()
            self.assertEqual(market(p).inspect(count=value)['error'], 'COUNT_DENIED')
            self.assertEqual(p.calls, [])
    def test_safe_result_and_closed_bars(self):
        p = Proxy(); out = market(p).inspect()
        self.assertEqual(out, {'ok': True, 'symbol': 'XAUUSD.st', 'count': 100, 'error': 'OK'})
        self.assertEqual(p.calls[-1][1], ('XAUUSD.st', 'M15', 1, 100))
    def test_unknown_api(self):
        for name in ('order_send', 'order_check', 'login', 'initialize', 'shutdown', 'unknown', 'copy_rates_from_pos'):
            with self.assertRaises(PolicyError):
                market().request_api(name)
    def test_error_containment(self):
        self.assertEqual(market(Proxy(fail=True)).inspect()['error'], 'SDK_ERROR')
        self.assertNotIn('PRIVATE', json.dumps(market(Proxy(fail=True)).inspect()))
    def test_audit_codes_do_not_capture_arguments_or_exceptions(self):
        a = market(Proxy(fail=True)); a.inspect()
        self.assertEqual(a.audit_events, ('ACCOUNT_GUARD', 'SDK_ERROR'))
        with self.assertRaises(PolicyError):
            a.request_api('PRIVATE_FORBIDDEN')
        self.assertEqual(a.audit_events[-1], 'API_DENIED')
        self.assertNotIn('PRIVATE', json.dumps(a.audit_events))
    def test_missing_or_failed_audit_blocks_market(self):
        class Broken:
            def emit(self, code):
                raise OSError('PRIVATE/path')
        for sink in (None, Broken()):
            p = Proxy(); out = market(p, audit_sink=sink).inspect()
            self.assertEqual(out['error'], 'AUDIT_UNAVAILABLE')
            self.assertEqual(p.calls, [])
    def test_audit_failure_before_market(self):
        class FailsOnMarket:
            def emit(self, code):
                if code == 'MARKET_READ':
                    raise OSError('SECRET')
        p = Proxy()
        self.assertEqual(market(p, audit_sink=FailsOnMarket()).inspect()['error'], 'AUDIT_UNAVAILABLE')
        self.assertEqual(p.calls, ['account_info', 'symbol_info'])
    def test_empty_and_malformed_rows(self):
        from unittest.mock import patch
        for rows, expected in (([], 'HISTORY_UNAVAILABLE'), ([123], 'DATA_INVALID'), ([{'account':'PRIVATE'}], 'DATA_INVALID')):
            p = Proxy()
            with patch.object(p, 'copy_rates_from_pos', return_value=rows):
                self.assertEqual(market(p).inspect()['error'], expected)


class SinkTests(unittest.TestCase):
    def test_local_fixed_codes_no_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'audit.jsonl'
            a = market(Proxy(fail=True), audit_sink=JsonlAuditSink(p, approved=True))
            self.assertEqual(a.inspect()['error'], 'SDK_ERROR')
            self.assertEqual(p.read_text().splitlines(), ['{"event":"ACCOUNT_GUARD"}', '{"event":"SDK_ERROR"}'])
            with self.assertRaises(PolicyError):
                JsonlAuditSink(p, approved=True).emit('PRIVATE')
    def test_unapproved_and_full_sink(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'audit.jsonl'
            self.assertEqual(market(audit_sink=JsonlAuditSink(p)).inspect()['error'], 'AUDIT_UNAVAILABLE')
            p.write_bytes(b'x' * 128)
            self.assertEqual(market(audit_sink=JsonlAuditSink(p, approved=True, max_bytes=128)).inspect()['error'], 'AUDIT_UNAVAILABLE')
            self.assertEqual(p.stat().st_size, 128)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'status.json'
        self.write()
    def write(self, **changes):
        obj = {'schema': 1, 'status': 'running', 'heartbeat_epoch': 1000}
        obj.update(changes); self.path.write_text(json.dumps(obj))
    def observer(self, path=None):
        return RobotObserver(path or self.path, trusted_status=True)
    def test_no_approval(self):
        self.assertEqual(RobotObserver().observe(now=1010)['error'], 'PATH_APPROVAL_REQUIRED')
        self.assertEqual(RobotObserver(self.path).observe(now=1010)['status'], 'unknown')
    def test_explicit_running_stopped(self):
        for status in ('running', 'stopped'):
            self.write(status=status)
            self.assertEqual(self.observer().observe(now=1010), {'ok': True, 'status': status, 'error': 'OK'})
    def test_stale_future(self):
        for now in (900, 1061):
            self.assertEqual(self.observer().observe(now=now)['error'], 'STATUS_STALE')
    def test_unknown_keys_and_private_error(self):
        self.write(account='PRIVATE')
        self.assertEqual(self.observer().observe(now=1010)['error'], 'STATUS_INVALID')
        self.path.write_text('PRIVATE invalid content')
        self.assertEqual(self.observer().observe(now=1010)['error'], 'STATUS_READ_ERROR')
    def test_byte_limit(self):
        self.path.write_text('x' * 4097)
        self.assertEqual(self.observer().observe(now=1010)['error'], 'STATUS_TOO_LARGE')
    def test_path_escape(self):
        escaped = self.path.parent / '..' / self.path.parent.name / self.path.name
        self.assertEqual(self.observer(escaped).observe(now=1010)['error'], 'PATH_DENIED')
    def test_symlink_policy_mock(self):
        from unittest.mock import patch
        with patch.object(Path, 'is_symlink', return_value=True):
            self.assertEqual(self.observer().observe(now=1010)['error'], 'PATH_DENIED')
    def test_hardlink_rejected(self):
        import os
        alias = self.path.parent / 'alias.json'
        os.link(self.path, alias)
        self.assertEqual(self.observer().observe(now=1010)['error'], 'PATH_DENIED')
    def test_reparse_attribute_mock(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch('safe_adapters.os.fstat', return_value=SimpleNamespace(st_nlink=1, st_file_attributes=0x400)):
            self.assertEqual(self.observer().observe(now=1010)['error'], 'PATH_DENIED')
    def test_invalid_status_fields(self):
        for change in ({'status':'active'}, {'heartbeat_epoch':True}, {'schema':True}, {'heartbeat_epoch':float('nan')}):
            self.write(**change)
            self.assertEqual(self.observer().observe(now=1010)['error'], 'STATUS_INVALID')


if __name__ == '__main__':
    unittest.main(verbosity=2)
