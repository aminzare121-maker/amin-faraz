import unittest
import tempfile
from pathlib import Path
from safe_export_guard import inspect_text, inspect_file

class TestGuard(unittest.TestCase):
    def test_ohlc(self):
        self.assertIn('ohlc_fields', inspect_text('{"open":1,"high":2,"low":0,"close":1}', '.json'))
    def test_secret(self):
        self.assertIn('sensitive_key', inspect_text('{"access_token":"x"}', '.json'))
    def test_nested_secret(self):
        self.assertIn('sensitive_key', inspect_text('{"a":[{"password":"x"}]}', '.json'))
    def test_aggregate(self):
        self.assertEqual([], inspect_text('{"trades":20,"net_usd":-3.5,"pf":0.8}', '.json'))
    def test_csv(self):
        self.assertIn('raw_or_binary_data_format', inspect_text('foo', '.csv'))
    def test_bad_json(self):
        self.assertIn('invalid_json', inspect_text('{', '.json'))
    def test_binary(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'x.bin'; p.write_bytes(b'\xff\xfe')
            self.assertIn('unreadable_or_binary', inspect_file(p))
    def test_missing(self):
        self.assertIn('not_regular_file', inspect_file('/definitely/no/such/file'))
    def test_large(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.txt'; p.write_text('a'*1000001)
            self.assertIn('too_large_for_review', inspect_file(p))
    def test_assignment(self):
        self.assertIn('credential_assignment', inspect_text('API_KEY = abc', '.txt'))

if __name__ == '__main__': unittest.main()
