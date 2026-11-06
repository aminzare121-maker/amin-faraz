"""Optional owner-operated hidden local entry; NEVER run through chat/stdin pipes."""
import getpass
import json
import sys
import local_once_host as host

CODE_SHA='869aeb5bd469223d2b58502ecc4ebd2b17441708476df29ee574f5639fec72b6'
LAUNCHER_SHA='cde1247a6f5f8cfe79878877d3ead0c951dc8e4e1c206304f718fd93f34105f2'

def main():
    if not sys.stdin.isatty():
        print('LOCAL_INTERACTIVE_CONSOLE_REQUIRED: no secret read.');return 2
    print('Owner-operated ONE SHOT: approved isolated workspace; Issue38 status only.')
    print('Use an expiring GitHub token restricted to aminzare121-maker/amin-faraz, Issues read/write.')
    print('Do not paste it in ChatGPT or GitHub comments. Input below stays hidden and is not saved.')
    if input('Proceed with this one local authentication and status request? Type YES: ').strip()!='YES':
        return 2
    credential=getpass.getpass('Local GitHub token (hidden): ').strip()
    if not credential:
        print('NO_CREDENTIAL: nothing executed.');return 2
    previous=host.cached_auth
    host.cached_auth=lambda:credential
    try:
        result=host.run_once(CODE_SHA,LAUNCHER_SHA)
        print(json.dumps(result,sort_keys=True))
        print('Check the actual AMIN-WIN-RESULT-v1 comment in Issue38. No service remains running.')
        return 0 if result.get('returncode')==0 else 1
    finally:
        host.cached_auth=previous
        credential=None

if __name__=='__main__':
    raise SystemExit(main())
