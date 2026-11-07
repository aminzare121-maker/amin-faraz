"""Read-only inventory and transactional migration into the existing guard.
Local receipts detect mismatches, not a privileged owner's coordinated rollback.
"""
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from registry import digest

def inventory(paths):
    records=[]
    for path in map(Path,paths):
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'reusable_runs' not in tables:continue
            for run,spec,state,created,result,result_sha in db.execute('SELECT id,spec,state,created,result,result_sha FROM reusable_runs'):
                spec=json.loads(spec);result=json.loads(result) if result else None
                intact=result is not None and digest(result)==result_sha
                # A FAILED run may have consumed prices before failure: never call it fresh.
                split=(result or {}).get('split',spec.get('split'))
                records.append(dict(run=run,bank_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    datasets=spec.get('datasets'),protocol_hash=spec.get('protocol_sha256'),
                    timezone='UNKNOWN',declared_scope=spec.get('settings',{}).get('scope'),
                    symbol='UNKNOWN',split=split,registered_at_ms=created,
                    exposure_time='UNKNOWN',result_intact=intact,state=state,
                    status='NEEDS_REVIEW',reason='Full UTC exposure interval and exposure instant not attested; never infer from filename or run creation'))
    unique={}
    for r in records:unique.setdefault(r['run'],r)
    return dict(schema=1,rows=records,unique_runs=len(unique),bank_rows=len(records),
                recovered_verified=0,ambiguous=len(unique),coverage='ONLY_ENUMERATED_BANKS',
                financial_gate='BLOCKED',rollback='ROLLBACK_PROTECTION_UNVERIFIED')

def plan(records):
    if not records:raise ValueError('EMPTY_HISTORY_NOT_FRESH')
    normalized=[]
    for r in records:
        if r.get('status')!='VERIFIED' or r.get('timezone')!='UTC' or not r.get('provenance'):
            raise ValueError('HISTORY_NEEDS_REVIEW')
        if not all(type(r.get(k)) is int for k in ('start','end','exposed_at')) or r['start']>=r['end']:
            raise ValueError('INTERVAL')
        if len(r.get('run',''))!=64 or len(r.get('dataset_hash',''))!=64:raise ValueError('IDENTITY')
        normalized.append(r)
    normalized.sort(key=lambda r:r['run'])
    if len({r['run'] for r in normalized})!=len(normalized):raise ValueError('DUPLICATE_RUN')
    body=dict(schema=1,records=normalized)
    return dict(body=body,sha=digest(body),financial_gate='BLOCKED',rollback='ROLLBACK_PROTECTION_UNVERIFIED')

def apply(path,manifest,backup,*,fail_before_commit=False):
    """Existing guard schema only. SQLite transaction gives all-or-nothing rows.
    Backup is a separate SQLite snapshot; checkpoints are explicitly not trusted anchors.
    """
    if digest(manifest['body'])!=manifest['sha'] or plan(manifest['body']['records'])!=manifest:
        raise ValueError('MANIFEST_MISMATCH')
    path=Path(path);backup=Path(backup)
    with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=10)) as db:
        if db.execute('PRAGMA user_version').fetchone()[0]!=1:raise ValueError('SCHEMA')
        # Separate connection creates a consistent snapshot; never overwrite prior backup.
        with backup.open('xb'):pass
        with closing(sqlite3.connect(backup)) as out:db.backup(out)
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS migration(version INTEGER PRIMARY KEY,sha TEXT UNIQUE,body TEXT,previous TEXT)')
            old=db.execute('SELECT version,sha FROM migration ORDER BY version DESC LIMIT 1').fetchone()
            if old and old[1]==manifest['sha']:return dict(action='REUSE',version=old[0],sha=old[1])
            for r in manifest['body']['records']:
                prior=db.execute('SELECT start,end FROM exposure WHERE run=?',(r['run'],)).fetchone()
                if prior and prior!=(r['start'],r['end']):raise ValueError('LEDGER_MISMATCH')
                db.execute('INSERT OR IGNORE INTO exposure VALUES(?,?,?)',(r['run'],r['start'],r['end']))
            version=1 if old is None else old[0]+1
            previous=None if old is None else old[1]
            db.execute('INSERT INTO migration VALUES(?,?,?,?)',(version,manifest['sha'],json.dumps(manifest['body'],sort_keys=True),previous))
            if fail_before_commit:raise RuntimeError('SIMULATED_INTERRUPTION')
        return checkpoint(path)

def checkpoint(path):
    with closing(sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True)) as db:
        rows=db.execute('SELECT run,start,end FROM exposure ORDER BY run').fetchall()
        migrations=db.execute('SELECT version,sha,body,previous FROM migration ORDER BY version').fetchall()
        previous=None
        for version,sha,body,parent in migrations:
            if parent!=previous or digest(json.loads(body))!=sha:raise ValueError('CHAIN_MISMATCH')
            previous=sha
    return dict(schema=1,version=len(migrations),head=previous,rows_sha=digest(rows),
                rollback='ROLLBACK_PROTECTION_UNVERIFIED',financial_gate='BLOCKED')

def verify(path,anchor):
    if checkpoint(path)!=anchor:raise ValueError('ROLLBACK_OR_TAMPER')
    return {'local_consistency':True,'rollback':'ROLLBACK_PROTECTION_UNVERIFIED','financial_gate':'BLOCKED'}
