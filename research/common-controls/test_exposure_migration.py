import copy,json,sqlite3,tempfile,unittest,shutil
from pathlib import Path
from contextlib import closing
from exposure_migration import plan,apply,verify,checkpoint
from holdout_guard import provision

def record(key='a',start=0):return dict(run=key*64,dataset_hash='c'*64,start=start,end=start+100,exposed_at=1000,timezone='UTC',provenance='synthetic fixture',status='VERIFIED')

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'authority';provision(self.db)
    def write(self,records=None,**kwargs):
        return apply(self.db,plan(records or [record()]),self.root/('backup'+str(len(list(self.root.glob('backup*'))))),**kwargs)
    def test_idempotent(self):
        a=self.write();b=self.write();self.assertEqual(b['action'],'REUSE');self.assertEqual(checkpoint(self.db),a)
    def test_interruption_rolls_back_then_retry(self):
        with self.assertRaisesRegex(RuntimeError,'INTERRUPTION'):self.write(fail_before_commit=True)
        with closing(sqlite3.connect(self.db)) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM exposure').fetchone()[0],0)
        self.assertEqual(self.write()['version'],1)
    def test_old_snapshot_detected(self):
        old=self.write();shutil.copy2(self.db,self.root/'old')
        head=self.write([record(),record('b',200)])
        shutil.copy2(self.root/'old',self.db)
        with self.assertRaisesRegex(ValueError,'ROLLBACK'):verify(self.db,head)
        self.assertEqual(verify(self.db,old)['rollback'],'ROLLBACK_PROTECTION_UNVERIFIED')
    def test_manifest_tamper(self):
        m=plan([record()]);m['body']['records'][0]['end']=999
        with self.assertRaisesRegex(ValueError,'MISMATCH'):apply(self.db,m,self.root/'b')
    def test_conflicting_same_run(self):
        self.write()
        with self.assertRaisesRegex(ValueError,'LEDGER_MISMATCH'):self.write([record(start=1)])
    def test_unknown_timezone_and_empty(self):
        for rows in ([],[dict(record(),timezone='server')],[dict(record(),status='UNKNOWN')]):
            with self.assertRaises(ValueError):plan(rows)
    def test_duplicates_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):plan([record(),record()])
    def test_mutated_ledger_detected(self):
        anchor=self.write()
        with closing(sqlite3.connect(self.db)) as db,db:db.execute('UPDATE exposure SET end=99')
        with self.assertRaisesRegex(ValueError,'ROLLBACK'):verify(self.db,anchor)
    def test_missing_not_created(self):
        self.db.unlink()
        with self.assertRaises(sqlite3.Error):self.write()
        self.assertFalse(self.db.exists())
    def test_two_writers_same_manifest(self):
        from concurrent.futures import ThreadPoolExecutor
        def run(i):return apply(self.db,plan([record()]),self.root/str(i))
        with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(run,[1,2]))
        self.assertEqual(checkpoint(self.db)['version'],1)
        self.assertEqual(sum(x.get('action')=='REUSE' for x in r),1)

if __name__=='__main__':unittest.main()
