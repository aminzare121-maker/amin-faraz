"""Offline/mock-only counterexamples. Never opens GitHub or a credential store."""
import importlib.util,json,os,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from urllib import request
import bridge_agent as b

spec=importlib.util.spec_from_file_location('bridge_v01_baseline',Path(__file__).resolve().parents[1]/'pr39-original/bridge_agent.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

class Response:
    def __init__(self,url,raw=b'[]',headers=None):self.url=url;self.raw=raw;self.headers=headers or {};self.read=Mock(side_effect=lambda n:self.raw[:n])
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self,*a):pass

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.project=self.root/'project';self.project.mkdir();(self.project/'sample.py').write_text('x=1\n');self.state=self.root/'state.json'
    def tearDown(self):self.tmp.cleanup()
    def client(self,tasks):
        c=Mock();c.repo=b.PINNED_REPO;c.get_comments.return_value=[{'id':cid,'user':{'login':b.PINNED_OWNER},'body':b.REQ_PREFIX+json.dumps(task)} for cid,task in tasks];c.reply.return_value={'id':999};return c
    def test_malformed_action_before_after(self):
        body=b.REQ_PREFIX+json.dumps({'id':'bad','action':[]})
        with self.assertRaises(TypeError):old.decode_task(body)
        self.assertIsNone(b.decode_task(body));self.assertIsNone(b.decode_task(b.REQ_PREFIX+json.dumps({'id':12,'action':'status'})))
    def test_protocol_id_duplicate_before_after(self):
        tasks=[(1,{'id':'same','action':'status'}),(2,{'id':'same','action':'status'})]
        legacy=self.client(tasks);self.assertEqual(old.process_once(legacy,self.root,38,b.PINNED_OWNER,self.root/'old.json'),2)
        current=self.client(tasks);self.assertEqual(b.process_once(current,self.root,38,b.PINNED_OWNER,self.state),1);self.assertEqual(current.reply.call_count,1)
    def test_duplicate_id_with_changed_action_not_executed(self):
        c=self.client([(1,{'id':'same','action':'status'}),(2,{'id':'same','action':'run_unittest','path':'project'})]);approve=Mock(return_value=True)
        self.assertEqual(b.process_once(c,self.root,38,b.PINNED_OWNER,self.state,approve),1);approve.assert_not_called()
    def test_cross_host_redirect_before_after(self):
        req=request.Request('https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments?per_page=100&page=1',headers={'Authorization':'Bearer fixture-token'})
        forwarded=request.HTTPRedirectHandler().redirect_request(req,None,302,'Found',{},'https://other.example/collect')
        self.assertEqual(forwarded.get_header('Authorization'),'Bearer fixture-token')
        with self.assertRaises(ValueError):b.NoRedirect().redirect_request(req,None,302,'Found',{},'https://other.example/collect')
    def test_endpoint_method_repo_pin(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');c.opener=Mock()
        for method,url in [('GET','https://api.github.com.evil.example/x'),('GET','https://api.github.com/repos/other/repo/issues/38/comments?per_page=100&page=1'),('DELETE','https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments'),('GET','https://api.github.com/repos/'+b.PINNED_REPO+'/issues/39/comments?per_page=100&page=1')]:
            with self.subTest(url=url),self.assertRaises(ValueError):c.call(method,url)
        c.opener.open.assert_not_called()
    def test_query_and_payload_bounds(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');c.opener=Mock();url='https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments'
        for bad in ('?per_page=100&page=11','?per_page=100&page=1&other=x','?per_page=100&page=1&page=2'):
            with self.assertRaises(ValueError):c.call('GET',url+bad)
        with self.assertRaises(ValueError):c.call('POST',url,{'body':b.RES_PREFIX+'x'*10001})
        c.opener.open.assert_not_called()
    def test_response_byte_bound(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');url='https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments?per_page=100&page=1';r=Response(url,b'x'*(b.MAX_RESPONSE+1));c.opener=Mock();c.opener.open.return_value=r
        with self.assertRaises(ValueError):c.call('GET',url)
        r.read.assert_called_once_with(b.MAX_RESPONSE+1)
    def test_declared_oversized_response_not_read(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');url='https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments?per_page=100&page=1';r=Response(url,headers={'Content-Length':str(b.MAX_RESPONSE+1)});c.opener=Mock();c.opener.open.return_value=r
        with self.assertRaises(ValueError):c.call('GET',url)
        r.read.assert_not_called()
    def test_response_url_change_rejected(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');url='https://api.github.com/repos/'+b.PINNED_REPO+'/issues/38/comments?per_page=100&page=1';r=Response('https://other.example/x');c.opener=Mock();c.opener.open.return_value=r
        with self.assertRaises(ValueError):c.call('GET',url)
        r.read.assert_not_called()
    def test_hardlinked_file_hash_and_syntax_blocked(self):
        outside=self.root/'outside.txt';outside.write_text('secret outside');alias=self.project/'alias.py';os.link(outside,alias)
        with self.assertRaises(ValueError):b.safe_source(self.root,'project/alias.py')
        r=b.action(self.root,{'action':'syntax_check','path':'project'},approve=lambda *a:False)
        self.assertEqual(r['files_checked'],1)
    def test_reparse_parent_checked_for_every_file(self):
        junction=self.project/'linked';junction.mkdir();(junction/'bad.py').write_text('def broken(')
        original=b._reparse
        with patch.object(b,'_reparse',side_effect=lambda p:p==junction or original(p)):
            with self.assertRaises(ValueError):b.safe_source(self.root,'project/linked/bad.py')
            r=b.action(self.root,{'action':'syntax_check','path':'project'},approve=lambda *a:False)
        self.assertEqual(r['files_checked'],1);self.assertEqual(r['errors'],[])
    def test_bounded_walk_does_not_sort_whole_tree(self):
        yielded=[]
        class Scan:
            def __enter__(s):return s
            def __exit__(s,*a):pass
            def __iter__(s):
                for i in range(5000):yielded.append(i);yield types.SimpleNamespace(path=str(self.project/f'absent{i}.py'))
        with patch.object(b.os,'scandir',return_value=Scan()):paths,info=b.bounded_sources(self.root,self.project)
        self.assertLessEqual(len(yielded),b.MAX_ENTRIES+1);self.assertTrue(info['truncated']);self.assertEqual(paths,[])
    def test_file_identity_change_fails_closed(self):
        original=b.os.fstat
        def changed(fd):
            s=original(fd);return types.SimpleNamespace(st_dev=s.st_dev,st_ino=s.st_ino+1,st_nlink=s.st_nlink,st_mode=s.st_mode)
        with patch.object(b.os,'fstat',side_effect=changed),self.assertRaises(ValueError):b.read_source(self.root,'project/sample.py')
    def test_inflight_crash_requires_reconciliation(self):
        c=self.client([(1,{'id':'crash','action':'status'})])
        with patch.object(b,'action',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):b.process_once(c,self.root,38,b.PINNED_OWNER,self.state)
        self.assertEqual(b.state_load(self.state)['request_ids']['crash']['status'],'inflight')
        with patch.object(b,'action') as a,self.assertRaises(ValueError):b.process_once(c,self.root,38,b.PINNED_OWNER,self.state)
        a.assert_not_called();c.reply.assert_not_called()
    def test_scope_cannot_move_to_other_workspace(self):
        c=self.client([(1,{'id':'a','action':'status'})]);b.process_once(c,self.root,38,b.PINNED_OWNER,self.state)
        other=self.root/'other';other.mkdir();copied=other/'state.json';copied.write_bytes(self.state.read_bytes())
        with self.assertRaises(ValueError):b.process_once(c,other,38,b.PINNED_OWNER,copied)
    def test_exclusive_lock_prevents_second_worker(self):
        self.state.with_name(self.state.name+'.lock').write_text('existing worker')
        c=self.client([])
        with self.assertRaises(ValueError):b.process_once(c,self.root,38,b.PINNED_OWNER,self.state)
        c.get_comments.assert_not_called()
    def test_handshake_only_exact_existing_request(self):
        tasks=[(1,{'id':b.HANDSHAKE_ID,'action':'status'}),(b.HANDSHAKE_COMMENT_ID,{'id':b.HANDSHAKE_ID,'action':'status'}),(3,{'id':'generic','action':'file_hash','path':'project/sample.py'})]
        c=self.client(tasks);self.assertEqual(b.process_once(c,self.root,38,b.PINNED_OWNER,self.state,handshake_only=True),1);self.assertEqual(c.reply.call_args.args[1]['request_comment_id'],b.HANDSHAKE_COMMENT_ID)
    def test_live_generic_client_refused_before_network(self):
        c=b.Github(b.PINNED_REPO,'fixture-token');c.get_comments=Mock()
        with self.assertRaises(ValueError):b.process_once(c,self.root,38,b.PINNED_OWNER,self.state)
        c.get_comments.assert_not_called()
    def test_handshake_saved_arbitrary_result_not_posted(self):
        d={'schema':2,'processed':[],'pending':{'1':{'id':b.HANDSHAKE_ID,'action':'read_code','request_comment_id':1,'result':{'secret':'x'}}},'request_ids':{b.HANDSHAKE_ID:{'status':'pending'}}};b.state_save(self.state,d);c=self.client([])
        with self.assertRaises(ValueError):b.process_once(c,self.root,38,b.PINNED_OWNER,self.state,handshake_only=True)
        c.reply.assert_not_called()
    def test_config_only_never_looks_up_auth_or_network(self):
        with patch.object(b,'get_token') as token,patch.object(b,'Github') as gh:
            self.assertEqual(b.main(['--workspace',str(self.root)]),0)
        token.assert_not_called();gh.assert_not_called()
    def test_live_requires_owner_workspace_flag_before_auth(self):
        with patch.object(b,'get_token') as token,self.assertRaises(ValueError):b.main(['--workspace',str(self.root),'--live-handshake'])
        token.assert_not_called()
    def test_token_lookup_env_only_no_processes(self):
        with patch.dict(b.os.environ,{},clear=True),patch.object(b.subprocess,'run') as run:self.assertEqual(b.get_token(),'')
        run.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
