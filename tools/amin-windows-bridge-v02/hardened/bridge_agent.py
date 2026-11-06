#!/usr/bin/env python3
"""Amin bridge0.2: offline-tested guards; live CLI permits status handshake only.

Not a sandbox. File/test actions remain offline library functions; live generic
dispatch is disabled. No startup/service, credentials prompt or credential search.
"""
from __future__ import annotations
import argparse,ast,hashlib,json,os,re,stat,subprocess,sys,tempfile
from pathlib import Path
from urllib import request,error,parse

REQ_PREFIX='AMIN-WIN-REQ-v1\n';RES_PREFIX='AMIN-WIN-RESULT-v1\n'
PINNED_REPO='aminzare121-maker/amin-faraz';PINNED_ISSUE=38;PINNED_OWNER='aminzare121-maker'
HANDSHAKE_ID='amin-bridge-first-handshake-20261106'
HANDSHAKE_COMMENT_ID=6688143796
SAFE_ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')
SAFE_PATTERN=re.compile(r'^test_[a-zA-Z0-9_*.-]*\.py$')
ALLOWED_EXT={'.py','.md','.txt','.json','.toml','.yml','.yaml','.bat','.ps1'}
DENIED_NAME=re.compile(r'(^\.|^id_rsa$|\.env|key|credential|password|token|secret|wallet|account|login|private|\.pem|\.pfx)',re.I)
SENSITIVE_TEXT=re.compile(r'(?i)(bearer\s+[A-Za-z0-9._-]+|(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\r\n,}]+)')
TASK_ACTIONS={'status','list_files','file_hash','read_code','syntax_check','run_unittest'}
MANUAL={'read_code','run_unittest'}
MAX_FILE=100000;MAX_ENTRIES=1000;MAX_DIRS=128;MAX_DEPTH=8;MAX_RESPONSE=2*1024*1024;MAX_STATE=2*1024*1024
REPARSE=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)

def _reparse(p):
    s=p.lstat()
    return p.is_symlink() or bool(getattr(s,'st_file_attributes',0)&REPARSE)

def _chain(path,stop=None):
    for p in (path,*path.parents):
        if p.exists() or p.is_symlink():
            if _reparse(p):raise ValueError('reparse/symlink path blocked')
        if stop is not None and p==stop:break

def _root(root):
    root=Path(root).absolute();_chain(root)
    root=root.resolve(strict=True)
    if not root.is_dir() or root.parent==root:raise ValueError('approved workspace must be a bounded directory')
    return root

def safe_relpath(root,rel,must_be_file=False):
    root=_root(root)
    if not isinstance(rel,str) or not rel or len(rel)>250 or '\\' in rel or ':' in rel or any(ord(c)<32 for c in rel):raise ValueError('invalid relative path')
    parts=rel.split('/')
    if any(p in ('','.','..') or p.endswith((' ','.')) or DENIED_NAME.search(p) for p in parts):raise ValueError('restricted relative path')
    if Path(rel).is_absolute():raise ValueError('absolute path blocked')
    target=root.joinpath(*parts);_chain(target,root)
    resolved=target.resolve(strict=True)
    if not resolved.is_relative_to(root):raise ValueError('outside approved workspace')
    s=resolved.stat()
    if resolved.is_file() and s.st_nlink!=1:raise ValueError('hardlinked source blocked')
    if must_be_file and not stat.S_ISREG(s.st_mode):raise ValueError('not a regular file')
    return resolved

def safe_source(root,rel):
    p=safe_relpath(root,rel,True)
    if p.suffix.lower() not in ALLOWED_EXT or p.stat().st_size>MAX_FILE:raise ValueError('file type or size blocked')
    return p

def read_source(root,rel):
    p=safe_source(root,rel);before=p.stat()
    fd=os.open(p,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    try:
        current=os.fstat(fd)
        if (current.st_dev,current.st_ino)!=(before.st_dev,before.st_ino) or current.st_nlink!=1 or not stat.S_ISREG(current.st_mode):raise ValueError('file identity changed')
        chunks=[];total=0
        while True:
            block=os.read(fd,min(8192,MAX_FILE+1-total))
            if not block:break
            chunks.append(block);total+=len(block)
            if total>MAX_FILE:raise ValueError('file grew past limit')
        after=safe_source(root,rel).stat()
        if (after.st_dev,after.st_ino)!=(current.st_dev,current.st_ino):raise ValueError('file identity changed')
        return b''.join(chunks)
    finally:os.close(fd)

def redact(s,limit=5000):
    s=SENSITIVE_TEXT.sub('[REDACTED]',str(s))
    s=re.sub(r'(?i)[a-z]:[\\/]users[\\/][^\\/\s]+[\\/]', '[LOCAL_USER_PATH]/',s)
    return s[:limit]

def decode_task(body):
    if not isinstance(body,str) or not body.startswith(REQ_PREFIX) or len(body)>4000:return None
    try:d=json.loads(body[len(REQ_PREFIX):])
    except (ValueError,TypeError):return None
    if not isinstance(d,dict):return None
    if not isinstance(d.get('id'),str) or not SAFE_ID.fullmatch(d['id']):return None
    if not isinstance(d.get('action'),str) or d['action'] not in TASK_ACTIONS:return None
    if set(d)-{'id','action','path','pattern'}:return None
    if 'path'in d and (not isinstance(d['path'],str) or len(d['path'])>250):return None
    if 'pattern'in d and (not isinstance(d['pattern'],str) or not SAFE_PATTERN.fullmatch(d['pattern'])):return None
    if d['action'] not in ('status','list_files','syntax_check') and not isinstance(d.get('path'),str):return None
    return d

def bounded_sources(root,start):
    root=_root(root);queue=[(start,0)];paths=[];seen=0;dirs=0;limited=False
    while queue and len(paths)<75 and seen<MAX_ENTRIES and dirs<MAX_DIRS:
        folder,depth=queue.pop();dirs+=1
        if folder!=root:safe_relpath(root,folder.relative_to(root).as_posix())
        with os.scandir(folder) as entries:
            for entry in entries:
                seen+=1
                if seen>MAX_ENTRIES:limited=True;break
                rel=Path(entry.path).relative_to(root).as_posix()
                try:p=safe_relpath(root,rel)
                except (ValueError,OSError):continue
                if p.is_dir():
                    if depth<MAX_DEPTH and len(queue)<MAX_DIRS:queue.append((p,depth+1))
                    else:limited=True
                elif p.suffix.lower()=='.py':
                    try:safe_source(root,rel)
                    except (ValueError,OSError):continue
                    paths.append(rel)
                    if len(paths)>=75:limited=True;break
    return paths,{'entries_scanned':min(seen,MAX_ENTRIES),'directories_scanned':dirs,'truncated':limited or bool(queue),'file_limit':75,'entry_limit':MAX_ENTRIES,'depth_limit':MAX_DEPTH}

def action(root,d,*,approve):
    if not isinstance(d,dict) or not isinstance(d.get('action'),str) or d['action'] not in TASK_ACTIONS:raise ValueError('malformed action')
    root=_root(root);kind=d['action']
    if kind in MANUAL and not approve(kind,d.get('path','')):return {'status':'DENIED','message':'local user declined action'}
    if kind=='status':return {'status':'OK','bridge':'0.2','online':True,'supported':sorted(TASK_ACTIONS),'live_cli_mode':'status-handshake-only','sandbox':False}
    if kind=='list_files':
        folder=safe_relpath(root,d['path']) if d.get('path') else root
        if not folder.is_dir():raise ValueError('not a directory')
        rows=[];seen=0
        with os.scandir(folder) as entries:
            for entry in entries:
                seen+=1
                if seen>MAX_ENTRIES:break
                try:p=safe_relpath(root,Path(entry.path).relative_to(root).as_posix())
                except (ValueError,OSError):continue
                if p.is_file() and p.suffix.lower() in ALLOWED_EXT:rows.append({'name':p.name,'bytes':p.stat().st_size})
                elif p.is_dir():rows.append({'name':p.name,'directory':True})
                if len(rows)>=50:break
        return {'status':'OK','items':rows,'truncated_at':50,'entries_scanned':min(seen,MAX_ENTRIES)}
    if kind in ('file_hash','read_code'):
        raw=read_source(root,d['path']);out={'status':'OK','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
        if kind=='read_code':
            txt=raw.decode('utf-8');out.update(content_excerpt=redact(txt,4500),truncated=len(txt)>4500)
        return out
    if kind=='syntax_check':
        folder=safe_relpath(root,d['path']) if d.get('path') else root
        if not folder.is_dir():raise ValueError('not a directory')
        paths,bounds=bounded_sources(root,folder);errors=[]
        for rel in paths:
            try:ast.parse(read_source(root,rel).decode('utf-8'),filename=Path(rel).name)
            except (SyntaxError,UnicodeError,ValueError,OSError) as exc:errors.append({'file':rel,'error':redact(type(exc).__name__+': '+str(exc),350)})
        return {'status':'OK' if not errors else 'SYNTAX_ERRORS','files_checked':len(paths),'errors':errors[:10],**bounds}
    if kind=='run_unittest':
        folder=safe_relpath(root,d['path'])
        if not folder.is_dir():raise ValueError('not a directory')
        pattern=d.get('pattern','test_*.py')
        if not isinstance(pattern,str) or not SAFE_PATTERN.fullmatch(pattern):raise ValueError('invalid test pattern')
        # Manual/trusted-project execution is NOT a sandbox. Disabled in live CLI.
        env={k:os.environ.get(k,'') for k in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP')};env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
        try:
            done=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(folder),'-p',pattern,'-v'],env=env,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90,shell=False)
            return {'status':'PASS' if done.returncode==0 else 'TEST_FAILED','returncode':done.returncode,'output_excerpt':redact(done.stdout,4500),'truncated':len(done.stdout)>4500}
        except subprocess.TimeoutExpired:return {'status':'TIMEOUT','seconds':90}
    raise ValueError('action not allowed')

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('HTTP redirects disabled')

class Github:
    def __init__(self,repo,token):
        if repo!=PINNED_REPO:raise ValueError('repository not approved')
        if not isinstance(token,str) or not token or len(token)>1000 or any(ord(c)<=32 for c in token):raise ValueError('invalid local auth')
        self.repo=repo;self.token=token;self.opener=request.build_opener(NoRedirect())
    def _validate(self,method,url,payload):
        u=parse.urlsplit(url)
        if u.scheme!='https' or u.hostname!='api.github.com' or u.port not in (None,443) or u.username or u.password or u.fragment:raise ValueError('API origin blocked')
        if u.path!=f'/repos/{self.repo}/issues/{PINNED_ISSUE}/comments':raise ValueError('API endpoint blocked')
        q=parse.parse_qs(u.query,keep_blank_values=True)
        if method=='GET':
            if payload is not None or set(q)!={'per_page','page'} or q['per_page']!=['100'] or len(q['page'])!=1 or not q['page'][0].isdigit() or not 1<=int(q['page'][0])<=10:raise ValueError('GET parameters blocked')
        elif method=='POST':
            if q or not isinstance(payload,dict) or set(payload)!={'body'} or not isinstance(payload['body'],str) or not payload['body'].startswith(RES_PREFIX) or len(payload['body'])>10000:raise ValueError('POST body blocked')
        else:raise ValueError('HTTP method blocked')
    def call(self,method,url,payload=None):
        self._validate(method,url,payload)
        raw=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
        req=request.Request(url,data=raw,method=method,headers={'Accept':'application/vnd.github+json','Authorization':'Bearer '+self.token,'User-Agent':'amin-windows-bridge/0.2','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
        with self.opener.open(req,timeout=20) as resp:
            if resp.geturl()!=url:raise ValueError('unexpected response URL')
            length=resp.headers.get('Content-Length')
            if length is not None and (not length.isdigit() or int(length)>MAX_RESPONSE):raise ValueError('response size blocked')
            raw=resp.read(MAX_RESPONSE+1)
            if len(raw)>MAX_RESPONSE:raise ValueError('response too large')
            return json.loads(raw.decode('utf-8'))
    def get_comments(self,issue):
        if issue!=PINNED_ISSUE:raise ValueError('issue not approved')
        rows=[]
        for page in range(1,11):
            data=self.call('GET',f'https://api.github.com/repos/{self.repo}/issues/{issue}/comments?per_page=100&page={page}')
            if not isinstance(data,list) or len(data)>100:raise ValueError('invalid comment page')
            rows.extend(data)
            if len(data)<100:break
        return rows
    def reply(self,issue,message):
        if issue!=PINNED_ISSUE:raise ValueError('issue not approved')
        return self.call('POST',f'https://api.github.com/repos/{self.repo}/issues/{issue}/comments',{'body':RES_PREFIX+json.dumps(message,ensure_ascii=False,sort_keys=True)})

def get_token():
    # Root/local launcher may provide a preexisting credential ephemerally.
    # Never prompt, read credential stores, or invoke gh/git from queue processing.
    return os.environ.get('AMIN_BRIDGE_GH_TOKEN','')

def state_load(path):
    path=Path(path)
    if not path.exists():return {'schema':2,'processed':[],'pending':{},'request_ids':{}}
    if path.stat().st_size>MAX_STATE:raise ValueError('state too large')
    obj=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj,dict) or obj.get('schema')!=2 or not isinstance(obj.get('processed'),list) or not isinstance(obj.get('pending'),dict) or not isinstance(obj.get('request_ids'),dict):raise ValueError('state schema requires local reconciliation')
    if len(obj['processed'])>5000 or len(obj['request_ids'])>5000:raise ValueError('state capacity reached; no automatic pruning')
    return obj

def state_save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and (_reparse(path) or path.stat().st_nlink!=1):raise ValueError('unsafe state alias')
    _chain(path.parent)
    raw=json.dumps(obj,ensure_ascii=False,indent=2)
    if len(raw.encode('utf-8'))>MAX_STATE:raise ValueError('state too large')
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.bridge-',delete=False) as f:
            tmp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path);tmp=None
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()

def approval(kind,rel):
    print(f'LOCAL APPROVAL REQUIRED: {kind} on {rel}')
    if kind=='run_unittest':print('Tests execute trusted project code; NOT a sandbox.')
    try:return input('Approve this one action? Type YES: ').strip()=='YES'
    except EOFError:return False

def _process_once(client,root,issue,owner,state_path,approve=approval,*,handshake_only=False):
    root=_root(root);state_path=Path(state_path).absolute();_chain(state_path)
    if not state_path.resolve().is_relative_to(root):raise ValueError('state must stay under approved workspace')
    if state_path.exists() and state_path.stat().st_nlink!=1:raise ValueError('state hardlink blocked')
    repo=getattr(client,'repo',PINNED_REPO)
    if not isinstance(repo,str):repo=PINNED_REPO
    if repo!=PINNED_REPO or issue!=PINNED_ISSUE or owner.lower()!=PINNED_OWNER:raise ValueError('bridge scope blocked')
    if isinstance(client,Github) and not handshake_only:raise ValueError('live generic dispatch disabled')
    mode='live_status_handshake_v02' if handshake_only else 'offline_library_actions'
    scope=hashlib.sha256(json.dumps([repo,issue,owner.lower(),os.path.normcase(str(root)),mode]).encode()).hexdigest()
    data=state_load(state_path)
    if 'scope'in data and data['scope']!=scope:raise ValueError('state repo/workspace scope mismatch')
    data['scope']=scope
    if any(not isinstance(v,dict) or v.get('status')=='inflight' for v in data['request_ids'].values()):raise ValueError('INFLIGHT_NEEDS_LOCAL_RECONCILIATION; execution outcome unknown')
    for key,result in list(data['pending'].items()):
        if handshake_only and (result.get('id')!=HANDSHAKE_ID or result.get('action')!='status' or result.get('request_comment_id')!=HANDSHAKE_COMMENT_ID or result.get('result')!=action(root,{'action':'status'},approve=lambda *a:False)):
            raise ValueError('saved result not approved status handshake')
        client.reply(issue,result);data['processed'].append(int(key));del data['pending'][key]
        data['request_ids'][result['id']]['status']='done';state_save(state_path,data)
    comments=client.get_comments(issue);handled=0
    if not isinstance(comments,list) or len(comments)>1000:raise ValueError('comment batch blocked')
    for item in comments:
        if not isinstance(item,dict) or not isinstance(item.get('user'),dict):continue
        author=item['user'].get('login')
        if not isinstance(author,str) or author.lower()!=owner.lower():continue
        task=decode_task(item.get('body'));cid=item.get('id')
        if task is None or type(cid)is not int or cid<=0:continue
        if handshake_only and (task!={'id':HANDSHAKE_ID,'action':'status'} or cid!=HANDSHAKE_COMMENT_ID):continue
        if cid in data['processed'] or str(cid)in data['pending'] or task['id']in data['request_ids']:continue
        if len(data['request_ids'])>=5000:raise ValueError('state capacity reached; local reconciliation required')
        data['request_ids'][task['id']]={'comment_id':cid,'status':'inflight','task_digest':hashlib.sha256(json.dumps(task,sort_keys=True).encode()).hexdigest()}
        state_save(state_path,data) # Persist reservation BEFORE action. Crash => local reconciliation, never auto-reexecute.
        try:result=action(root,task,approve=approve)
        except Exception as exc:result={'status':'ERROR','message':redact(type(exc).__name__+': '+str(exc),300)}
        message={'request_comment_id':cid,'id':task['id'],'action':task['action'],'result':result}
        data['pending'][str(cid)]=message;data['request_ids'][task['id']]['status']='pending';state_save(state_path,data)
        client.reply(issue,message);data['processed'].append(cid);del data['pending'][str(cid)];data['request_ids'][task['id']]['status']='done';state_save(state_path,data);handled+=1
    return handled

def process_once(client,root,issue,owner,state_path,approve=approval,*,handshake_only=False):
    root=_root(root);state_path=Path(state_path).absolute();_chain(state_path)
    if not state_path.resolve().is_relative_to(root):raise ValueError('state must stay under approved workspace')
    state_path.parent.mkdir(parents=True,exist_ok=True)
    lock=state_path.with_name(state_path.name+'.lock')
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('LOCAL_STATE_LOCKED; reconcile stale/inflight state locally') from None
    try:
        os.write(fd,str(os.getpid()).encode('ascii'));os.fsync(fd)
        return _process_once(client,root,issue,owner,state_path,approve,handshake_only=handshake_only)
    finally:
        os.close(fd)
        if lock.exists():lock.unlink()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',default=PINNED_REPO);p.add_argument('--issue',type=int,default=PINNED_ISSUE);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--owner',default=PINNED_OWNER);p.add_argument('--state',type=Path)
    p.add_argument('--live-handshake',action='store_true');p.add_argument('--owner-approved-workspace',action='store_true')
    args=p.parse_args(argv);root=_root(args.workspace)
    if args.repo!=PINNED_REPO or args.issue!=PINNED_ISSUE or args.owner.lower()!=PINNED_OWNER:raise ValueError('fixed repository/issue/owner required')
    if not args.live_handshake:
        print('CONFIG_ONLY: no auth lookup, network, queue execution or service.');return 0
    if not args.owner_approved_workspace:raise ValueError('explicit local workspace approval required')
    token=get_token()
    if not token:raise SystemExit('LOCAL_AUTH_MISSING: no prompt or credential search; no connection attempted')
    state=args.state or root/'.amin_bridge_state'/'handshake-v02.json'
    client=Github(args.repo,token)
    count=process_once(client,root,args.issue,args.owner,state,handshake_only=True)
    print(f'ONE_SHOT_HANDSHAKE_ONLY: handled={count}; live generic actions disabled; no background service.')
    return 0

if __name__=='__main__':raise SystemExit(main())
