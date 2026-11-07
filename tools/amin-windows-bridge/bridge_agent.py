#!/usr/bin/env python3
"""Amin Windows Bridge v0.1: an opt-in, scoped GitHub-issue task runner.

Python standard library only. It is NOT a remote desktop, shell, or a sandbox.
Never handles broker orders, trades, installers, or system changes.
"""
from __future__ import annotations

import argparse
import ast
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib import request, error

REQ_PREFIX = "AMIN-WIN-REQ-v1\n"
RES_PREFIX = "AMIN-WIN-RESULT-v1\n"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
SAFE_PATTERN = re.compile(r"^test_[a-zA-Z0-9_*.-]*\.py$")
ALLOWED_EXT = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".bat", ".ps1"}
DENIED_NAME = re.compile(r"(^\.|^id_rsa$|\.env|key|credential|password|token|secret|wallet|account|login|private|\.pem|\.pfx)", re.I)
SENSITIVE_TEXT = re.compile(r"(?i)(bearer\s+[A-Za-z0-9._-]+|(?:password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[^\r\n,}]+)")
TASK_ACTIONS = {"status", "list_files", "file_hash", "read_code", "syntax_check", "run_unittest"}
MANUAL = {"read_code", "run_unittest"}


def safe_relpath(root: Path, rel: str, must_be_file: bool = False) -> Path:
    if not isinstance(rel, str) or not rel or len(rel) > 250 or "\\" in rel or "\x00" in rel:
        raise ValueError("invalid relative path")
    p = Path(rel)
    if p.is_absolute() or any(part in ("..", ".") for part in p.parts):
        raise ValueError("path traversal blocked")
    target = root.joinpath(p)
    if any(x.is_symlink() for x in (target, *list(target.parents)[:len(p.parts)])):
        raise ValueError("symlink path blocked")
    resolved = target.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("outside approved workspace")
    if not resolved.exists():
        raise ValueError("path does not exist")
    if must_be_file and not resolved.is_file():
        raise ValueError("not a file")
    if any(DENIED_NAME.search(part) for part in p.parts):
        raise ValueError("restricted path")
    return resolved


def safe_source(root: Path, rel: str) -> Path:
    p = safe_relpath(root, rel, must_be_file=True)
    if p.suffix.lower() not in ALLOWED_EXT or p.stat().st_size > 100_000:
        raise ValueError("file type or size not allowed")
    return p


def redact(s: str, limit: int = 5000) -> str:
    s = SENSITIVE_TEXT.sub("[REDACTED]", s)
    s = re.sub(r"(?i)[a-z]:\\users\\[^\\\s]+\\", "[LOCAL_USER_PATH]\\\\", s)
    return s[:limit]


def decode_task(body: str) -> dict | None:
    if not isinstance(body, str) or not body.startswith(REQ_PREFIX) or len(body) > 4000:
        return None
    try:
        d = json.loads(body[len(REQ_PREFIX):])
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or not SAFE_ID.fullmatch(str(d.get("id", ""))) or d.get("action") not in TASK_ACTIONS:
        return None
    allowed = {"id", "action", "path", "pattern"}
    if set(d) - allowed:
        return None
    if d["action"] not in ("status", "list_files", "syntax_check") and not isinstance(d.get("path"), str):
        return None
    return d


def action(root: Path, d: dict, *, approve) -> dict:
    kind = d["action"]
    if kind in MANUAL and not approve(kind, d.get("path", "")):
        return {"status": "DENIED", "message": "local user declined action"}
    if kind == "status":
        return {"status": "OK", "bridge": "0.1", "online": True, "supported": sorted(TASK_ACTIONS), "mode": "opt-in local Python process"}
    if kind == "list_files":
        folder = safe_relpath(root, d.get("path") or "src") if d.get("path") else root
        if not folder.is_dir():
            raise ValueError("not a directory")
        rows=[]
        for p in sorted(folder.iterdir(), key=lambda v:v.name.lower()):
            if p.is_symlink() or DENIED_NAME.search(p.name) or p.name.startswith("."):
                continue
            if p.is_file() and p.suffix.lower() in ALLOWED_EXT:
                rows.append({"name":p.name,"bytes":p.stat().st_size})
            elif p.is_dir():
                rows.append({"name":p.name,"directory":True})
            if len(rows)>=50:break
        return {"status":"OK","items":rows,"truncated_at":50}
    if kind == "file_hash":
        p=safe_source(root,d["path"])
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        return {"status":"OK","sha256":h,"bytes":p.stat().st_size}
    if kind == "read_code":
        p=safe_source(root,d["path"])
        txt=p.read_text(encoding="utf-8")
        # Explicitly do not return a partial file silently as complete.
        return {"status":"OK","content_excerpt":redact(txt,4500),"truncated":len(txt)>4500,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    if kind == "syntax_check":
        rel=d.get("path") or ""
        folder=safe_relpath(root,rel) if rel else root
        if not folder.is_dir():raise ValueError("not a directory")
        paths=[]
        for p in sorted(folder.rglob("*.py")):
            if p.is_symlink() or any(DENIED_NAME.search(x) for x in p.relative_to(root).parts):continue
            if p.stat().st_size>100_000:continue
            paths.append(p)
            if len(paths)>=75:break
        errors=[]
        for p in paths:
            try:ast.parse(p.read_text(encoding="utf-8"),filename=p.name)
            except (SyntaxError,UnicodeError) as exc:
                errors.append({"file":p.relative_to(root).as_posix(),"error":redact(str(exc),350)})
        return {"status":"OK" if not errors else "SYNTAX_ERRORS","files_checked":len(paths),"errors":errors[:10]}
    if kind == "run_unittest":
        rel=d.get("path") or ""
        folder=safe_relpath(root,rel) if rel else root
        if not folder.is_dir():raise ValueError("not a directory")
        pattern=d.get("pattern","test_*.py")
        if not isinstance(pattern,str) or not SAFE_PATTERN.fullmatch(pattern):
            raise ValueError("invalid test pattern")
        # Explicit approval required. The selected Python tests may execute code.
        env={"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT",""),"WINDIR":os.environ.get("WINDIR",""),"TEMP":os.environ.get("TEMP",""),"TMP":os.environ.get("TMP",""),"PYTHONDONTWRITEBYTECODE":"1","PYTHONIOENCODING":"utf-8"}
        cmd=[sys.executable,"-m","unittest","discover","-s",str(folder),"-p",pattern,"-v"]
        try:
            done=subprocess.run(cmd,env=env,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90,shell=False)
            return {"status":"PASS" if done.returncode==0 else "TEST_FAILED","returncode":done.returncode,"output_excerpt":redact(done.stdout,4500),"truncated":len(done.stdout)>4500}
        except subprocess.TimeoutExpired:
            return {"status":"TIMEOUT","seconds":90}
    raise ValueError("action not allowed")


class Github:
    def __init__(self, repo:str, token:str):
        if not re.fullmatch(r"[\w.-]+/[\w.-]+",repo):raise ValueError("invalid repo")
        self.repo=repo
        self.token=token

    def call(self,method:str,url:str,payload=None):
        if not url.startswith("https://api.github.com/"):
            raise ValueError("API host blocked")
        raw=None if payload is None else json.dumps(payload,ensure_ascii=False).encode("utf-8")
        req=request.Request(url,data=raw,method=method,headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+self.token,"User-Agent":"amin-windows-bridge/0.1","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
        with request.urlopen(req,timeout=20) as resp:
            return json.load(resp)

    def get_comments(self,issue:int):
        all_comments=[]
        for page in range(1,11):
            data=self.call("GET",f"https://api.github.com/repos/{self.repo}/issues/{issue}/comments?per_page=100&page={page}")
            all_comments.extend(data)
            if len(data)<100:break
        return all_comments

    def reply(self, issue:int, message:dict):
        return self.call("POST",f"https://api.github.com/repos/{self.repo}/issues/{issue}/comments",{"body":RES_PREFIX+json.dumps(message,ensure_ascii=False,sort_keys=True)})


def get_token() -> str:
    token=os.environ.get("AMIN_BRIDGE_GH_TOKEN")
    if token:return token
    # Reuse existing locally authenticated GitHub CLI when available.
    try:
        got=subprocess.run(["gh","auth","token"],capture_output=True,text=True,timeout=8,check=True)
        if got.stdout.strip():return got.stdout.strip()
    except (FileNotFoundError,subprocess.SubprocessError):pass
    return getpass.getpass("GitHub fine-grained token (Issues read/write, only this repo): ").strip()


def state_load(path:Path) -> dict:
    if not path.exists():return {"processed":[],"pending":{}}
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict) or not isinstance(obj.get("processed"),list) or not isinstance(obj.get("pending"),dict):
        raise ValueError("invalid local state")
    return obj


def state_save(path:Path, obj:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)


def approval(kind:str,rel:str):
    print(f"\nLOCAL APPROVAL REQUIRED: {kind} on {rel or '(workspace)'}")
    if kind=="run_unittest":print("WARNING: Python unit tests execute project code. This is NOT a sandbox.")
    try:return input("Approve just this action? Type YES: ").strip()=="YES"
    except EOFError:return False


def process_once(client:Github,root:Path,issue:int,owner:str,state_path:Path,approve=approval):
    data=state_load(state_path)
    # First retry posting saved results; never re-execute a previously completed test.
    for key,result in list(data["pending"].items()):
        client.reply(issue,result)
        data["processed"].append(int(key)); del data["pending"][key]
        state_save(state_path,data)
    comments=client.get_comments(issue)
    handled=0
    for item in comments:
        if not isinstance(item,dict) or item.get("user",{}).get("login","").lower()!=owner.lower():continue
        task=decode_task(item.get("body",""))
        if task is None:continue
        cid=int(item["id"])
        if cid in data["processed"] or str(cid) in data["pending"]:continue
        try:
            result=action(root,task,approve=approve)
        except Exception as exc:
            result={"status":"ERROR","message":redact(type(exc).__name__+": "+str(exc),300)}
        message={"request_comment_id":cid,"id":task["id"],"action":task["action"],"result":result}
        data["pending"][str(cid)]=message
        state_save(state_path,data)
        # If GitHub posting fails, retry next time without executing same task twice.
        client.reply(issue,message)
        data["processed"].append(cid);del data["pending"][str(cid)]
        state_save(state_path,data)
        handled+=1
    return handled


def main(argv=None):
    p=argparse.ArgumentParser(description="Amin secure, limited Windows bridge via GitHub Issue comments")
    p.add_argument("--repo",default="aminzare121-maker/amin-faraz")
    p.add_argument("--issue",type=int,required=True)
    p.add_argument("--workspace",type=Path,required=True)
    p.add_argument("--owner",default="aminzare121-maker")
    p.add_argument("--watch",action="store_true",help="keep foreground terminal open; poll every 45 seconds")
    args=p.parse_args(argv)
    root=args.workspace.resolve(strict=True)
    if not root.is_dir():raise ValueError("workspace must be an existing folder")
    if args.issue<=0:raise ValueError("invalid issue")
    token=get_token()
    if not token:raise SystemExit("Missing GitHub token; no connection attempted")
    state=Path.home()/".amin_windows_bridge"/f"issue-{args.issue}-state.json"
    github=Github(args.repo,token)
    print("Bridge started. Allowed workspace set. No shell, MT5, installers, or trading actions.")
    while True:
        try:
            print("Processed new tasks:",process_once(github,root,args.issue,args.owner,state))
        except (error.URLError,TimeoutError,ValueError) as exc:
            print("Bridge connection/config error:",type(exc).__name__,str(exc)[:200])
        if not args.watch:break
        try:time.sleep(45)
        except KeyboardInterrupt:break

if __name__=="__main__":
    raise SystemExit(main())
