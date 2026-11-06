"""Independent I/O guard; leaves immutable v1 unchanged."""
import json,os,tempfile
from pathlib import Path

def reject_aliases(inputs,outputs):
    source=[Path(p).resolve() for p in inputs]
    target=[Path(p).resolve() for p in outputs]
    def same(a,b):
        return os.path.normcase(str(a))==os.path.normcase(str(b)) or (a.exists() and b.exists() and os.path.samefile(a,b))
    for i,a in enumerate(target):
        if any(same(a,b) for b in source):raise ValueError('Output aliases a protected input')
        if any(same(a,b) for b in target[:i]):raise ValueError('Outputs alias one another')

def write_json_atomic(path,value,protected_inputs=()):
    dest=Path(path).resolve();reject_aliases(protected_inputs,[dest]);dest.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=dest.parent,prefix='.audit-',suffix='.tmp',delete=False) as f:
            temporary=Path(f.name);f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(temporary,dest);temporary=None
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
