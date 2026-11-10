"""SYNTHETIC receipt and EX5 fixtures; never assert real MetaEditor compiled."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from artin_compile_receipt_verifier import SOURCE_NAME, SOURCE_SHA, LOG_NAME, EX5_NAME
from artin_mt5_demo_stage_v6 import StageBlocked, stage_compiled_collector, select_terminal, terminal_roots, main


def sha(b):
    return hashlib.sha256(b).hexdigest()

class StageTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.bundle=self.root/'bundle'; self.bundle.mkdir()
        self.comp=self.root/'comp'; self.comp.mkdir()
        self.app=self.root/'app'; self.app.mkdir()
        original=Path(__file__).parent/SOURCE_NAME
        source=original.read_bytes()
        assert sha(source)==SOURCE_SHA, 'real source bytes changed; update source separately, never fixture hash'
        (self.bundle/SOURCE_NAME).write_bytes(source)
        self.ex5=b'NOT-A-REAL-EX5-SYNTHETIC-TEST-ONLY'
        self.log=b'not a real compile\n0 errors, 0 warnings\n'
        (self.comp/EX5_NAME).write_bytes(self.ex5)
        (self.comp/LOG_NAME).write_bytes(self.log)
        self.receipt={
            'schema':'artin_mt5_metaeditor_compile_receipt_v3',
            'status':'COMPILE_CONFIRMED_LOCAL_METAEDITOR_ONLY',
            'source_sha256_verified':True,
            'source_sha256_expected':SOURCE_SHA,
            'ex5_sha256':sha(self.ex5), 'log_sha256':sha(self.log),
            'log_reports_zero_errors':True, 'log_reports_errors':False,
            'demo_runtime_tested':False,'mt5_orders_sent':0,'teacher_semantics_certified':False,
            'compiler_exit_code':0,
        }
        self.save_receipt()
        self.t1=self.add_terminal('abc')
    def save_receipt(self):
        (self.comp/'artin_v13_metaeditor_compile_receipt.json').write_text(json.dumps(self.receipt))
    def add_terminal(self,name):
        p=self.app/'MetaQuotes'/'Terminal'/name
        (p/'MQL5'/'Experts').mkdir(parents=True)
        return p
    def stage(self,**kw):
        return stage_compiled_collector(self.bundle,self.comp,self.app,**kw)
    def target(self,term=None):
        return (term or self.t1)/'MQL5'/'Experts'/'ArtinV13_ReadOnly'/EX5_NAME
    def test_discovers_single_terminal(self):
        self.assertEqual(terminal_roots(self.app),[self.t1])
        self.assertEqual(select_terminal(self.app),self.t1)
    def test_stages_only_ex5_and_claims_no_runtime(self):
        r=self.stage()
        self.assertEqual(r['status'],'NEW_EX5_STAGED_NOT_ATTACHED')
        self.assertEqual(self.target().read_bytes(),self.ex5)
        self.assertEqual(r['orders_sent'],0)
        self.assertFalse(r['mt5_demo_account_confirmed'])
        self.assertFalse(r['mt5_chart_attached'])
        self.assertFalse(r['teacher_semantics_certified'])
        self.assertEqual(sorted(f.name for f in self.target().parent.iterdir()),[EX5_NAME])
    def test_repeated_identical_staging_idempotent(self):
        self.stage(); self.assertEqual(self.stage()['status'],'ALREADY_PRESENT_SAME_HASH')
    def test_different_existing_ex5_not_overwritten(self):
        self.stage(); self.target().write_bytes(b'preexisting foreign EX5')
        with self.assertRaisesRegex(StageBlocked,'REFUSE_OVERWRITE'):self.stage()
        self.assertEqual(self.target().read_bytes(),b'preexisting foreign EX5')
    def test_multiple_terminals_blocked(self):
        other=self.add_terminal('def')
        with self.assertRaisesRegex(StageBlocked,'MULTIPLE_MT5'):self.stage()
        self.assertFalse(self.target().exists())
        self.assertFalse(self.target(other).exists())
    def test_explicit_selection_with_multiple_terminals(self):
        self.add_terminal('def')
        self.stage(terminal_data=self.t1)
        self.assertTrue(self.target().exists())
    def test_missing_terminal_blocks_without_writes(self):
        shutil.rmtree(self.t1)
        with self.assertRaisesRegex(StageBlocked,'NO_MT5'):self.stage()
    def test_bad_terminal_root_blocks(self):
        with self.assertRaisesRegex(StageBlocked,'EXPLICIT_TERMINAL'):self.stage(terminal_data=self.root)
    def test_tampered_source_blocks(self):
        (self.bundle/SOURCE_NAME).write_bytes(b'changed')
        with self.assertRaisesRegex(StageBlocked,'V2_ORIGINAL_SOURCE'):self.stage()
        self.assertFalse(self.target().exists())
    def test_compiler_log_hash_tamper_blocks(self):
        (self.comp/LOG_NAME).write_bytes(b'1 error')
        with self.assertRaisesRegex(StageBlocked,'COMPILE_RECEIPT_NOT_VERIFIED'):self.stage()
        self.assertFalse(self.target().exists())
    def test_invalid_ex5_digest_blocks(self):
        (self.comp/EX5_NAME).write_bytes(b'changed')
        with self.assertRaisesRegex(StageBlocked,'COMPILE_RECEIPT_NOT_VERIFIED'):self.stage()
    def test_no_compile_receipt_blocks(self):
        (self.comp/'artin_v13_metaeditor_compile_receipt.json').unlink()
        with self.assertRaisesRegex(StageBlocked,'MISSING_COMPILE_RECEIPT'):self.stage()
    def test_compiler_nonzero_exit_fails_closed(self):
        self.receipt['compiler_exit_code']=1;self.save_receipt()
        with self.assertRaisesRegex(StageBlocked,'COMPILER_EXIT_CODE'):self.stage()
    def test_unsupported_teacher_claim_blocks(self):
        self.receipt['teacher_semantics_certified']=True;self.save_receipt()
        with self.assertRaisesRegex(StageBlocked,'COMPILE_RECEIPT_NOT_VERIFIED'):self.stage()
    def test_no_symlink_redirection_into_other_folder(self):
        target=self.t1/'MQL5'/'Experts'/'ArtinV13_ReadOnly'
        outside=self.root/'outside';outside.mkdir()
        try:target.symlink_to(outside,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlink privileges unavailable')
        with self.assertRaisesRegex(StageBlocked,'SYMLINK_STAGE_FOLDER'):self.stage()
        self.assertEqual(list(outside.iterdir()),[])
    def test_redacted_receipt_uses_hash_not_account_number(self):
        p=self.root/'v6-receipt.json'
        r=self.stage(report_path=p)
        self.assertEqual(json.loads(p.read_text()),r)
        self.assertNotIn(str(self.t1),p.read_text())
        self.assertNotIn('abc',json.dumps(r))
    def test_report_cannot_be_silently_overwritten(self):
        p=self.root/'v6-receipt.json'
        self.stage(report_path=p)
        with self.assertRaises(FileExistsError): self.stage(report_path=p)
    def test_cli_file_only_success(self):
        self.assertEqual(main(['--bundle',str(self.bundle),'--compile-root',str(self.comp),
                               '--appdata',str(self.app),'--localappdata',str(self.root)]),0)
    def test_cli_blocked_with_missing_appdata(self):
        with patch.dict('os.environ', {'APPDATA':'','LOCALAPPDATA':''}):
            self.assertEqual(main(['--bundle',str(self.bundle),'--compile-root',str(self.comp)]),2)

if __name__=='__main__':unittest.main(verbosity=2)