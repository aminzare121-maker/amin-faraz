import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from bridge_agent import (REQ_PREFIX, RES_PREFIX, decode_task, safe_relpath,
                          safe_source, action, process_once, state_load)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        self.proj=self.root/'projects'
        self.proj.mkdir()
        (self.proj/'sample.py').write_text('x = 42\n',encoding='utf-8')
        (self.proj/'test_sample.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertEqual(3*7,21)\n',encoding='utf8')
        (self.proj/'bad.py').write_text('def broken(\n',encoding='utf8')
        (self.proj/'account.csv').write_text('time,close\n0,1\n',encoding='utf8')
        (self.proj/'secret.key').write_text('secret',encoding='utf8')
        self.state=self.root/'state.json'
    def tearDown(self): self.temp.cleanup()
    def test_valid_task(self):
        self.assertEqual(decode_task(REQ_PREFIX+json.dumps({'id':'foo.1','action':'status'})),{'id':'foo.1','action':'status'})
    def test_no_uncontrolled_action(self):
        self.assertIsNone(decode_task(REQ_PREFIX+'{"id":"a","action":"shell","cmd":"del *"}'))
        self.assertIsNone(decode_task(REQ_PREFIX+'{"id":"a","action":"run_unittest","path":"projects","cmd":"rm -rf /"}'))
    def test_no_malicious_markup_or_json(self):
        self.assertIsNone(decode_task('Just do it\n'+REQ_PREFIX+'{"id":"a","action":"status"}'))
        self.assertIsNone(decode_task(REQ_PREFIX+'{}'))
        self.assertIsNone(decode_task(REQ_PREFIX+'{"id":"BAD SPACE","action":"status"}'))
    def test_traversal_absolute_and_backslash_blocked(self):
        for p in ('../escape.py','/etc/passwd','C:\\Windows\\win.ini','projects/../sample.py'):
            with self.subTest(path=p):
                with self.assertRaises(ValueError):safe_relpath(self.root,p)
    def test_symlink_blocked(self):
        try:(self.root/'alias.py').symlink_to(self.proj/'sample.py')
        except OSError:self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):safe_source(self.root,'alias.py')
    def test_sensitive_and_prices_not_readable(self):
        for p in ('projects/secret.key','projects/account.csv'):
            with self.assertRaises(ValueError):safe_source(self.root,p)
    def test_read_requires_approval(self):
        x=action(self.root,{'action':'read_code','path':'projects/sample.py'},approve=lambda *a: False)
        self.assertEqual(x['status'],'DENIED')
        y=action(self.root,{'action':'read_code','path':'projects/sample.py'},approve=lambda *a: True)
        self.assertEqual(y['status'],'OK')
        self.assertIn('x = 42',y['content_excerpt'])
    def test_file_hash_and_list(self):
        h=action(self.root,{'action':'file_hash','path':'projects/sample.py'},approve=lambda *a:False)
        self.assertEqual(len(h['sha256']),64)
        f=action(self.root,{'action':'list_files','path':'projects'},approve=lambda *a:False)
        names=[r['name'] for r in f['items']]
        self.assertIn('sample.py',names)
        self.assertNotIn('account.csv',names)
        self.assertNotIn('secret.key',names)
    def test_syntax_check_no_execution(self):
        r=action(self.root,{'action':'syntax_check','path':'projects'},approve=lambda *a:False)
        self.assertEqual(r['status'],'SYNTAX_ERRORS')
        self.assertEqual(r['files_checked'],3)
        self.assertEqual(len(r['errors']),1)
    def test_unittest_approval(self):
        x=action(self.root,{'action':'run_unittest','path':'projects','pattern':'test_*.py'},approve=lambda *a:False)
        self.assertEqual(x['status'],'DENIED')
        y=action(self.root,{'action':'run_unittest','path':'projects','pattern':'test_*.py'},approve=lambda *a:True)
        self.assertEqual(y['status'],'PASS')
        self.assertIn('Ran 1 test',y['output_excerpt'])
    def test_bad_test_pattern_blocked(self):
        with self.assertRaises(ValueError):action(self.root,{'action':'run_unittest','path':'projects','pattern':'../*'},approve=lambda *a:True)
    def test_replay_result_remote(self):
        task={'id':'local-test-1','action':'status'}
        client=Mock()
        client.get_comments.return_value=[{'id':1001,'user':{'login':'not-the-owner'},'body':REQ_PREFIX+json.dumps(task)},
                                           {'id':1002,'user':{'login':'aminzare121-maker'},'body':REQ_PREFIX+json.dumps(task)}]
        client.reply.return_value={'id':1003}
        n=process_once(client,self.root,38,'aminzare121-maker',self.state,approve=lambda *a:False)
        self.assertEqual(n,1)
        self.assertEqual(process_once(client,self.root,38,'aminzare121-maker',self.state,approve=lambda *a:False),0)
        self.assertEqual(client.reply.call_count,1)
        self.assertEqual(state_load(self.state)['processed'],[1002])
    def test_failed_report_post_does_not_reexecute(self):
        task={'id':'twice','action':'run_unittest','path':'projects','pattern':'test_*.py'}
        client=Mock()
        client.get_comments.return_value=[{'id':2002,'user':{'login':'aminzare121-maker'},'body':REQ_PREFIX+json.dumps(task)}]
        client.reply.side_effect=[RuntimeError('temporary network failure'), {'id':2003}]
        approver=Mock(return_value=True)
        with self.assertRaises(RuntimeError):process_once(client,self.root,38,'aminzare121-maker',self.state,approve=approver)
        self.assertEqual(approver.call_count,1)
        self.assertIn('2002',state_load(self.state)['pending'])
        self.assertEqual(process_once(client,self.root,38,'aminzare121-maker',self.state,approve=approver),0)
        self.assertEqual(approver.call_count,1)
        self.assertEqual(client.reply.call_count,2)

if __name__=='__main__':unittest.main(verbosity=2)
