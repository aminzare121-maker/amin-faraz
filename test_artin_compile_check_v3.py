"""Offline synthetic-only tests, NEVER an actual MetaEditor compilation."""
import hashlib
import json
import unittest
from pathlib import Path
from artin_compile_receipt_verifier import check_receipt, SOURCE_SHA, SOURCE_NAME

ROOT=Path(__file__).parent


def example():
    # GitHub transport previously omitted ONE final LF; preserve exact bundle bytes.
    source=(ROOT/SOURCE_NAME).read_bytes()
    if not source.endswith(b'\n'): source += b'\n'
    log=b'Result: 0 errors, 0 warnings\n'
    ex5=b'SYNTHETIC_BYTES_NOT_EXECUTABLE'
    digest=lambda b:hashlib.sha256(b).hexdigest()
    receipt={'schema':'artin_mt5_metaeditor_compile_receipt_v3',
       'status':'COMPILE_CONFIRMED_LOCAL_METAEDITOR_ONLY','source_sha256_verified':True,
       'source_sha256_expected':SOURCE_SHA,'ex5_sha256':digest(ex5),
       'log_sha256':digest(log),'log_reports_zero_errors':True,
       'log_reports_errors':False,'demo_runtime_tested':False,
       'mt5_orders_sent':0,'teacher_semantics_certified':False}
    return receipt, source, log, ex5

class CompileOnlyContract(unittest.TestCase):
    def test_actual_unmodified_v2_source_pin(self):
        source=(ROOT/SOURCE_NAME).read_bytes()
        # GitHub's legacy V2 blob differs only by its missing final newline.
        self.assertEqual(hashlib.sha256(source if source.endswith(b'\n') else source+b'\n').hexdigest(),SOURCE_SHA)
    def test_public_example_is_synthetic_never_metaeditor_claim(self):
        r=check_receipt(*example())
        self.assertTrue(r['passed'],r)
        self.assertFalse(r['mt5_demo_runtime_tested'])
    def test_block_uncompiled_report(self):
        receipt,*rest=example();receipt['status']='BLOCKED_NOT_COMPILED'
        self.assertFalse(check_receipt(receipt,*rest)['passed'])
    def test_block_changed_original_source(self):
        receipt,src,log,ex5=example();self.assertIn('SOURCE_MISMATCH',check_receipt(receipt,src+b'!',log,ex5)['reasons'])
    def test_block_changed_ex5(self):
        receipt,src,log,ex5=example();self.assertIn('EX5_MISSING_OR_HASH_MISMATCH',check_receipt(receipt,src,log,ex5+b'x')['reasons'])
    def test_block_missing_ex5(self):
        receipt,src,log,_=example();self.assertFalse(check_receipt(receipt,src,log,b'')['passed'])
    def test_block_changed_compiler_log(self):
        receipt,src,log,ex5=example();self.assertIn('COMPILER_LOG_MISSING_OR_HASH_MISMATCH',check_receipt(receipt,src,log+b'1 error',ex5)['reasons'])
    def test_block_log_with_ten_errors_despite_zero_errors(self):
        receipt,src,_,ex5=example();log=b'Result: 10 errors, 0 warnings; previous: 0 errors\n';receipt['log_sha256']=hashlib.sha256(log).hexdigest()
        self.assertIn('COMPILER_ERRORS_REPORTED',check_receipt(receipt,src,log,ex5)['reasons'])
    def test_block_no_zero_errors_summary(self):
        receipt,src,_,ex5=example();log=b'No compilation summary\n';receipt['log_sha256']=hashlib.sha256(log).hexdigest()
        self.assertIn('ZERO_ERROR_LINE_MISSING',check_receipt(receipt,src,log,ex5)['reasons'])
    def test_block_claimed_live_trade(self):
        receipt,*rest=example();receipt['mt5_orders_sent']=1
        self.assertIn('UNJUSTIFIED_RUNTIME_OR_SEMANTIC_CLAIM',check_receipt(receipt,*rest)['reasons'])
    def test_block_claimed_semantic_verified(self):
        receipt,*rest=example();receipt['teacher_semantics_certified']=True
        self.assertFalse(check_receipt(receipt,*rest)['passed'])
    def test_reject_unverified_source_receipt(self):
        receipt,*rest=example();receipt['source_sha256_verified']=False
        self.assertIn('SOURCE_UNVERIFIED',check_receipt(receipt,*rest)['reasons'])
    def test_powershell_only_compiles_and_requires_exact_hash(self):
        script=(ROOT/'compile_artin_v13_shadow.ps1').read_text()
        for token in ('/compile:', '/log','Get-FileHash', 'SOURCE_SHA256_MISMATCH',
                      'COMPILER_LOG_DID_NOT_CONFIRM_ZERO_ERRORS','EX5_NOT_CREATED',
                      'COMPILE_CONFIRMED_LOCAL_METAEDITOR_ONLY','demo_runtime_tested = $false',
                      'Start-Process','WaitForExit(120000)', 'Explicit path is strict'):
            with self.subTest(token=token):self.assertIn(token,script)
        for forbidden in ('OrderSend(', 'OrderSendAsync(', 'WebRequest(',
                          'Invoke-Expression','-Verb RunAs', 'MQL5\\Experts', 'TERMINAL_DATA_PATH'):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,script)
    def test_v2_mql_is_no_order_collector(self):
        script=(ROOT/SOURCE_NAME).read_text()
        for term in ('ACCOUNT_TRADE_MODE_DEMO','CopyRates(','FileWrite(', 'OnTick(){}'):
            self.assertIn(term,script)
        for forbidden in ('OrderSend(', 'OrderSendAsync(', 'CTrade(', 'PositionOpen(', 'WebRequest('):
            self.assertNotIn(forbidden,script)
    def test_manifest_declares_no_compilation(self):
        m=json.loads((ROOT/'MANIFEST.json').read_text())
        self.assertEqual(m['source_sha256'],SOURCE_SHA)
        self.assertIs(m['compilation_performed_in_current_environment'],False)
        self.assertIs(m['mt5_demo_runtime_tested'],False)

if __name__=='__main__':unittest.main(verbosity=2)