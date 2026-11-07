import tempfile,unittest,json
from pathlib import Path
from registry import Registry,digest
from research_recovery import snapshot,restore,history
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.bank=Registry(self.root/'bank.sqlite')
        self.bank.artifact('x','a'*64,{},True)
        spec=dict(code_sha256='b'*64,datasets={'x':'a'*64},settings={},costs={},protocol_sha256='c'*64,environment={},metrics_version='1',split={},seed=1)
        r=self.bank.start(spec);self.ident=r['id'];self.bank.finish_run(self.ident,{'scenario_nominee':None,'net':-1},True)
    def tearDown(self):self.tmp.cleanup()
    def test_snapshot_restore_after_disconnect(self):
        snapshot(self.root/'bank.sqlite',self.root/'snapshot.sqlite')
        recovered=restore(self.root/'snapshot.sqlite',self.root/'restored.sqlite')
        self.assertEqual(history(self.bank),recovered)
    def test_corrupt_snapshot_rejected(self):
        p=self.root/'snapshot.sqlite';snapshot(self.root/'bank.sqlite',p);p.write_bytes(p.read_bytes()+b'corrupt')
        with self.assertRaisesRegex(ValueError,'HASH'):restore(p,self.root/'restored.sqlite')
    def test_restore_never_overwrites(self):
        p=self.root/'snapshot.sqlite';snapshot(self.root/'bank.sqlite',p)
        with self.assertRaisesRegex(ValueError,'NEW'):restore(p,self.root/'bank.sqlite')
    def test_tampered_result_not_valid(self):
        with self.bank.connect() as db:db.execute('UPDATE reusable_runs SET result=? WHERE id=?',(json.dumps({'net':999}),self.ident))
        self.assertFalse(history(self.bank)[0]['recoverable_result']);self.assertEqual(history(self.bank)[0]['state'],'TAMPERED')
if __name__=='__main__':unittest.main()
