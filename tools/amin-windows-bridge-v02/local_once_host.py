"""Trusted local supervisor. Never import this module into GitHub task dispatch.

Credentials stay in process memory and a one-shot child environment, never files,
command arguments, tool output or bridge results. No interactive login is started.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import re
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT/'approved-workspace'
BRIDGE=ROOT/'hardened'/'bridge_agent.py'
LAUNCHER=ROOT/'hardened'/'START_ONCE_WINDOWS.bat'

def safe_child_diagnostic(returncode, stderr):
    """Return only fixed classifications; never reflect raw output/credentials."""
    if returncode == 0:
        return 'PROCESS_EXITED_ZERO_NOT_HANDSHAKE_VERIFIED'
    text = stderr.decode('utf-8', errors='replace') if isinstance(stderr, bytes) else str(stderr or '')
    if '[WinError 10013]' in text:
        return 'LOCAL_NETWORK_PERMISSION_DENIED'
    found = re.search(r'HTTP Error (\d{3})(?:\D|$)', text)
    if found:
        return 'HTTP_STATUS_' + found.group(1)
    if 'getaddrinfo failed' in text or 'NameResolutionError' in text:
        return 'NETWORK_NAME_RESOLUTION_FAILED'
    if 'LOCAL_AUTH_MISSING' in text:
        return 'LOCAL_AUTH_MISSING'
    if 'TimeoutError' in text or 'timed out' in text:
        return 'LOCAL_NETWORK_OR_CHILD_TIMEOUT'
    if 'INFLIGHT_NEEDS_LOCAL_RECONCILIATION' in text:
        return 'INFLIGHT_NEEDS_LOCAL_RECONCILIATION'
    return 'CHILD_ERROR_CLASS_UNAVAILABLE'

def record_safe_diagnostic(code, classification):
    # This is a diagnostic, never an AMIN-WIN-RESULT or evidence of connectivity.
    payload = {'utc':datetime.now(timezone.utc).isoformat(), 'returncode':code,
        'classification':classification, 'handshake_verified':False,
        'raw_stderr_saved':False, 'credential_saved':False}
    try:
        temporary = ROOT/'LAST_RUN_DIAGNOSTIC.json.partial'
        temporary.write_text(json.dumps(payload, sort_keys=True)+'\n', encoding='utf-8')
        os.replace(temporary, ROOT/'LAST_RUN_DIAGNOSTIC.json')
    except OSError:
        pass

def cached_auth():
    git=shutil.which('git')
    if not git:
        return None
    env=dict(os.environ)
    for key in ('GIT_ASKPASS','SSH_ASKPASS'):
        env.pop(key,None)
    env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='0',GCM_GUI_PROMPT='0',
               GIT_TRACE='0',GIT_TRACE_CURL='0',GIT_CURL_VERBOSE='0',GCM_TRACE='0',
               GCM_TRACE_SECRETS='0',GCM_TRACE_MSAUTH='0',GCM_DEBUG='0')
    command=[git,'-c','credential.helper=','-c','credential.helper=manager',
             '-c','credential.interactive=false','-c','credential.trace=false',
             '-c','credential.traceSecrets=false','-c','credential.traceMsAuth=false',
             'credential','fill']
    try:
        completed=subprocess.run(command,input='protocol=https\nhost=github.com\npath=aminzare121-maker/amin-faraz.git\n\n',
            capture_output=True,text=True,timeout=15,env=env,cwd=ROOT,shell=False)
        if completed.returncode or len(completed.stdout)>65536:
            return None
        fields=dict(line.split('=',1) for line in completed.stdout.splitlines() if '=' in line)
        credential=fields.get('password')
        return credential if credential and '\r' not in credential and '\n' not in credential else None
    except Exception:
        return None

def run_once(expected_bridge_sha256,expected_launcher_sha256=None):
    """Called only after human workspace consent and frozen code review."""
    if not WORKSPACE.is_dir() or not BRIDGE.is_file():
        return {'status':'BLOCKED_LOCAL_PATH','live_bridge_executed':False}
    actual=hashlib.sha256(BRIDGE.read_bytes()).hexdigest()
    if actual!=expected_bridge_sha256:
        return {'status':'BLOCKED_CODE_CHANGED','live_bridge_executed':False}
    if not LAUNCHER.is_file() or not expected_launcher_sha256 or hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()!=expected_launcher_sha256:
        return {'status':'BLOCKED_LAUNCHER_CHANGED','live_bridge_executed':False}
    credential=cached_auth()
    if credential is None:
        return {'status':'BLOCKED_LOCAL_AUTH','live_bridge_executed':False}
    env=dict(os.environ)
    env['AMIN_BRIDGE_GH_TOKEN']=credential
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONIOENCODING']='utf-8'
    env['AMIN_BRIDGE_PYTHON']=sys.executable
    try:
        # Both paths are fixed trusted local files, never supplied by the queue.
        command_interpreter=str(Path(os.environ.get('SYSTEMROOT','C:/Windows'))/'System32'/'cmd.exe')
        completed=subprocess.run([command_interpreter,'/d','/c',str(LAUNCHER),str(WORKSPACE)],
            cwd=BRIDGE.parent,env=env,stdin=subprocess.DEVNULL,capture_output=True,
            timeout=90,shell=False)
        # Do not forward raw child stdout/stderr, even if it unexpectedly fails.
        classification = safe_child_diagnostic(completed.returncode, completed.stderr)
        record_safe_diagnostic(completed.returncode, classification)
        return {'status':'CHILD_EXITED','live_bridge_executed':True,'returncode':completed.returncode,
                'handshake_verified_by_host':False,'verification':'READ_ISSUE38_RESULT_SEPARATELY'}
    except subprocess.TimeoutExpired:
        return {'status':'LOCAL_CHILD_TIMEOUT','live_bridge_executed':True,'handshake_verified_by_host':False}
    except Exception:
        return {'status':'LOCAL_LAUNCH_ERROR','live_bridge_executed':False}
    finally:
        env.pop('AMIN_BRIDGE_GH_TOKEN',None)
        credential=None

if __name__=='__main__':
    if len(sys.argv)!=3 or any(len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in sys.argv[1:]):
        print(json.dumps({'status':'EXPECTED_REVIEWED_CODE_AND_LAUNCHER_SHAS_REQUIRED'}));raise SystemExit(2)
    print(json.dumps(run_once(sys.argv[1],sys.argv[2]),sort_keys=True))

