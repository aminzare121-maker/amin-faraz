"""Local SQLite snapshot/restore. Never overwrites a database; hash is checked first."""
import hashlib,json,sqlite3
from contextlib import closing
from pathlib import Path
from registry import Registry,digest

def snapshot(source,destination):
    source=Path(source);destination=Path(destination)
    if destination.exists():raise ValueError('DESTINATION_EXISTS')
    if not source.is_file():raise ValueError('SOURCE_MISSING')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(destination)) as dst:src.backup(dst)
    receipt={'schema':1,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'source_name':source.name}
    destination.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    return receipt

def restore(snapshot_path,destination):
    source=Path(snapshot_path);destination=Path(destination)
    if destination.exists():raise ValueError('RESTORE_MUST_BE_NEW')
    receipt=json.loads(source.with_suffix('.receipt.json').read_text(encoding='utf8'))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('SNAPSHOT_HASH_MISMATCH')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLITE_INTEGRITY')
        with closing(sqlite3.connect(destination)) as dst:src.backup(dst)
    return history(Registry(destination))

def history(bank):
    with bank.connect() as db:rows=db.execute('SELECT id,state,result,result_sha FROM reusable_runs ORDER BY created,id').fetchall()
    out=[]
    for ident,state,raw,sha in rows:
        result=json.loads(raw) if raw else None
        intact=result is not None and digest(result)==sha
        out.append(dict(id=ident,state=state if intact or result is None else 'TAMPERED',recoverable_result=state=='VALID' and intact,
            scenario_nominee=result.get('scenario_nominee') if intact and state=='VALID' else None,
            failure=result.get('reason',result.get('error_type')) if intact and state=='FAILED' else None))
    return out
