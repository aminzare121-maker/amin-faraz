import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import candle_archive as ca
from path_registry import PATHS,evaluate_path

def bar(stamp=900, **changes):
    value=dict(time=stamp,open=2300,high=2302,low=2298,close=2301,tick_volume=100,spread=20,real_volume=0)
    value.update(changes);return value

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.a=ca.CandleArchive(self.root)
    def tearDown(self):self.tmp.cleanup()
    def ingest(self,rows,now=9000):return self.a.ingest(rows,current_bar_open=now)

    def test_incremental_restart_native_times_and_equivalent_decimal(self):
        first=self.ingest([bar(900),bar(1800)])
        second=ca.CandleArchive(self.root).ingest([bar(1800,open='2300.000'),bar(2700)],current_bar_open=9000)
        self.assertEqual((first['added'],second['added'],second['duplicates']),(2,1,1))
        self.assertEqual([x['time'] for x in self.a.read_bars()],[900,1800,2700])
        self.assertEqual(self.a.latest_time(),2700)
        self.assertFalse(second['orders_enabled'])

    def test_backfill_closes_unknown_gap_without_reordering_chain(self):
        self.ingest([bar(900),bar(3600)])
        before=self.a.verify();self.assertEqual(before['gaps'][0]['absent_grid_slots'],2)
        result=self.ingest([bar(2700),bar(1800)])
        self.assertEqual(result['backfilled'],2);self.assertTrue(result['out_of_order_input']);self.assertEqual(result['gaps'],[])
        self.assertEqual(self.a.verify(expected_head=before)['count'],4)
        times=[json.loads(x)['bar']['time'] for x in (self.root/'candles.jsonl').read_text().splitlines()]
        self.assertEqual(times,[900,3600,1800,2700])

    def test_weekend_sized_gap_remains_unresolved(self):
        result=self.ingest([bar(900),bar(900+900*200)],now=900+900*202)
        self.assertEqual(result['gaps'][0]['status'],'GAP_UNRESOLVED')
        self.assertEqual(result['gaps'][0]['absent_grid_slots'],199)

    def test_conflicting_same_time_fails_without_mutation(self):
        self.ingest([bar()]);before=(self.root/'candles.jsonl').read_bytes()
        with self.assertRaises(ca.ConflictingCandle):self.ingest([bar(close=2300)])
        self.assertEqual((self.root/'candles.jsonl').read_bytes(),before)
        with self.assertRaises(ca.ConflictingCandle):self.ingest([bar(1800),bar(1800,close=2300)])
        self.assertEqual(self.a.verify()['count'],1)

    def test_incomplete_nan_and_malformed_are_rejected_atomically(self):
        bad=[bar(high=2299),bar(close=float('nan')),bar(low=0),bar(time=900.0),bar(time=True),
             bar(tick_volume=-1),bar(spread=1.5),bar(9000),bar(8550),bar(open='Infinity')]
        missing=bar();del missing['real_volume'];bad.append(missing)
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ca.InvalidCandle):self.ingest([bar(1800),value])
                self.assertEqual(self.a.verify()['count'],0)

    def test_current_native_grid_not_epoch_conversion(self):
        result=self.ingest([bar(1234),bar(2134)],now=3034)
        self.assertEqual(result['added'],2)
        with self.assertRaises(ca.InvalidCandle):self.ingest([bar(2700)],now=3034)
        with self.assertRaises(ca.InvalidCandle):self.ingest([bar(2700)],now=9000)

    def test_wrong_scope_and_mixed_symbol_fail(self):
        with self.assertRaises(ca.InvalidCandle):self.a.ingest([bar()],current_bar_open=9000,symbol='EURUSD')
        with self.assertRaises(ca.InvalidCandle):self.a.ingest([bar()],current_bar_open=9000,timeframe='M1')
        self.ingest([bar()])
        with self.assertRaises(ca.InvalidCandle):self.a.ingest([bar(1800)],current_bar_open=9000,symbol='XAUUSD.other')

    def test_record_tamper_and_middle_deletion_detected(self):
        self.ingest([bar(900),bar(1800),bar(2700)])
        p=self.root/'candles.jsonl';original=p.read_bytes();lines=original.splitlines(keepends=True)
        item=json.loads(lines[0]);item['bar']['close']='2300';lines[0]=ca.canonical(item)+b'\n';p.write_bytes(b''.join(lines))
        with self.assertRaises(ca.IntegrityError):self.a.verify()
        p.write_bytes(original.splitlines(keepends=True)[0]+original.splitlines(keepends=True)[2])
        with self.assertRaises(ca.IntegrityError):self.a.verify()

    def test_tail_truncation_and_missing_archive_detected(self):
        self.ingest([bar(900),bar(1800)])
        p=self.root/'candles.jsonl';original=p.read_bytes();p.write_bytes(original.splitlines(keepends=True)[0])
        with self.assertRaises(ca.IntegrityError):self.a.verify()
        with self.assertRaises(ca.IntegrityError):self.ingest([])
        p.unlink()
        with self.assertRaises(ca.IntegrityError):self.ingest([])

    def test_unjournaled_torn_append_never_silently_repaired(self):
        self.ingest([bar()]);p=self.root/'candles.jsonl'
        with p.open('ab') as out:out.write(b'{"uncommitted":')
        before=p.read_bytes()
        with self.assertRaises(ca.IntegrityError):self.ingest([])
        self.assertEqual(p.read_bytes(),before)

    def test_stale_checkpoint_without_pending_fails(self):
        self.ingest([bar()]);old=(self.root/'checkpoint.json').read_bytes();self.ingest([bar(1800)])
        (self.root/'checkpoint.json').write_bytes(old)
        with self.assertRaises(ca.IntegrityError):self.a.verify()

    def _crash_after_pending(self):
        self.ingest([bar()]);original=ca._atomic
        def atomic(path,value):
            original(path,value)
            if path.name=='pending.json':raise OSError('SIMULATED_PROCESS_STOP')
        with patch.object(ca,'_atomic',side_effect=atomic):
            with self.assertRaises(OSError):self.ingest([bar(1800),bar(2700)])
        return json.loads((self.root/'pending.json').read_bytes())['content']

    def test_recover_after_intent_before_append(self):
        self._crash_after_pending()
        with self.assertRaises(ca.IntegrityError):self.a.verify()
        result=self.ingest([])
        self.assertTrue(result['recovered_transaction']);self.assertEqual(self.a.verify()['count'],3)
        self.assertEqual(self.ingest([bar(1800),bar(2700)])['duplicates'],2)

    def test_recover_verified_partial_append(self):
        plan=self._crash_after_pending();append=bytes.fromhex(plan['append_hex'])
        with (self.root/'candles.jsonl').open('ab') as out:out.write(append[:len(append)//2])
        result=self.ingest([]);self.assertTrue(result['recovered_transaction']);self.assertEqual(self.a.verify()['count'],3)

    def test_torn_append_conflict_is_not_overwritten(self):
        self._crash_after_pending();p=self.root/'candles.jsonl'
        with p.open('ab') as out:out.write(b'INVALID')
        before=p.read_bytes()
        with self.assertRaises(ca.IntegrityError):self.ingest([])
        self.assertEqual(p.read_bytes(),before)

    def test_recover_after_checkpoint_before_anchor(self):
        self.ingest([bar()]);original=ca._atomic
        def atomic(path,value):
            if path.name=='anchor.json' and value['count']==2:raise OSError('SIMULATED_PROCESS_STOP')
            return original(path,value)
        with patch.object(ca,'_atomic',side_effect=atomic):
            with self.assertRaises(OSError):self.ingest([bar(1800)])
        self.assertTrue(self.ingest([])['recovered_transaction']);self.assertEqual(self.a.verify()['count'],2)

    def test_advanced_anchor_prevents_crash_recovery_masking_truncation(self):
        self.ingest([bar()]);original=ca._atomic
        def atomic(path,value):
            original(path,value)
            if path.name=='checkpoint.json' and value['count']==2:raise OSError('SIMULATED_PROCESS_STOP')
        with patch.object(ca,'_atomic',side_effect=atomic):
            with self.assertRaises(OSError):self.ingest([bar(1800)])
        p=self.root/'candles.jsonl';p.write_bytes(p.read_bytes().splitlines(keepends=True)[0])
        with self.assertRaises(ca.IntegrityError):self.ingest([])

    def test_external_head_pin_detects_coordinated_rollback(self):
        self.ingest([bar()]);saved={name:(self.root/name).read_bytes() for name in ('candles.jsonl','checkpoint.json','anchor.json')}
        self.ingest([bar(1800)]);pin=self.a.verify()
        for name,data in saved.items():(self.root/name).write_bytes(data)
        self.assertEqual(self.a.verify()['count'],1) # honest limitation: no external pin
        with self.assertRaises(ca.IntegrityError):self.a.verify(expected_head=pin)

    def test_writer_lock_prevents_second_writer(self):
        self.ingest([bar()])
        with ca.writer_lock(self.root):
            with self.assertRaises(ca.WriterBusy):self.ingest([bar(1800)])

    def test_os_lock_releases_after_real_process_termination(self):
        self.ingest([bar()])
        module_dir=str(Path(ca.__file__).parent)
        code="import sys,time;sys.path.insert(0,sys.argv[1]);from candle_archive import writer_lock;\nwith writer_lock(__import__('pathlib').Path(sys.argv[2])):\n print('LOCKED',flush=True);time.sleep(60)"
        child=subprocess.Popen([sys.executable,'-c',code,module_dir,str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(),'LOCKED')
            with self.assertRaises(ca.WriterBusy):self.ingest([bar(1800)])
            child.terminate();child.wait(timeout=10)
            self.assertEqual(self.ingest([bar(1800)])['added'],1)
        finally:
            if child.poll() is None:child.kill();child.wait(timeout=10)
            child.stdout.close();child.stderr.close()

    def test_thirteen_path_slots_never_approve(self):
        self.assertEqual(len(PATHS),13)
        for slot in PATHS:
            self.assertFalse(slot['semantic_verified']);self.assertFalse(slot['execution_enabled'])
            self.assertEqual(evaluate_path(slot['id'])['decision'],'NEEDS_EVIDENCE')
        with self.assertRaises(ValueError):evaluate_path('UNKNOWN')

if __name__=='__main__':unittest.main(verbosity=2)
