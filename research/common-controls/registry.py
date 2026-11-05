"""Extend the existing research ledger, never replace the active trading database."""
import hashlib,json,time
from vendor.research_ledger import ResearchLedger

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
REQUIRED={'code_sha256','datasets','settings','costs','protocol_sha256','environment','metrics_version','split','seed'}

def identity(spec):
    if set(spec)!=REQUIRED:raise ValueError('EXACT_DEPENDENCY_SCHEMA_REQUIRED')
    for key in ('code_sha256','protocol_sha256'):
        if not isinstance(spec[key],str) or len(spec[key])!=64 or any(c not in '0123456789abcdef' for c in spec[key]):raise ValueError('HASH_REQUIRED')
    if not isinstance(spec['datasets'],dict) or not spec['datasets']:raise ValueError('DATASET_DEPENDENCIES')
    for name,sha in spec['datasets'].items():
        if not name or not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('DATA_HASH_REQUIRED')
    return digest(spec)

class Registry(ResearchLedger):
    def __init__(self,path):
        super().__init__(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,sha TEXT NOT NULL,metadata TEXT NOT NULL,valid INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS reusable_runs(id TEXT PRIMARY KEY,spec TEXT NOT NULL,state TEXT NOT NULL,created INTEGER NOT NULL,result TEXT,result_sha TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS run_dependencies(run_id TEXT,artifact_id TEXT,sha TEXT,PRIMARY KEY(run_id,artifact_id))')
            db.execute('CREATE TABLE IF NOT EXISTS indicator_catalog(id TEXT PRIMARY KEY,version TEXT NOT NULL,definition_sha TEXT NOT NULL,status TEXT NOT NULL,evidence TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS invalidations(id INTEGER PRIMARY KEY,artifact_id TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL)')
    def artifact(self,name,sha,metadata,valid=False):
        if not name or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('ARTIFACT_ID_HASH')
        with self.connect() as db:
            prior=db.execute('SELECT sha FROM artifacts WHERE id=?',(name,)).fetchone()
            if prior and prior[0]!=sha:raise ValueError('IMMUTABLE_ARTIFACT_ID_USE_NEW_VERSION')
            db.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?)',(name,sha,canonical(metadata),int(valid)))
    def invalidate(self,name,reason):
        if not reason:raise ValueError('REASON_REQUIRED')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM artifacts WHERE id=?',(name,)).fetchone():raise ValueError('UNKNOWN_ARTIFACT')
            db.execute('INSERT INTO invalidations(artifact_id,reason,created) VALUES(?,?,?)',(name,reason,int(time.time()*1000)))
            db.execute('UPDATE artifacts SET valid=0 WHERE id=?',(name,))
            db.execute("UPDATE reusable_runs SET state='INVALIDATED' WHERE id IN (SELECT run_id FROM run_dependencies WHERE artifact_id=?)",(name,))
    def start(self,spec):
        key=identity(spec)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for name,sha in spec['datasets'].items():
                row=db.execute('SELECT sha,valid FROM artifacts WHERE id=?',(name,)).fetchone()
                if row!=(sha,1):raise ValueError('DATA_NOT_VALIDATED')
            prior=db.execute('SELECT state,result,result_sha FROM reusable_runs WHERE id=?',(key,)).fetchone()
            if prior:
                if prior[0]=='VALID' and prior[1] is not None:
                    result=json.loads(prior[1])
                    if digest(result)!=prior[2]:raise ValueError('RESULT_TAMPER')
                    return {'action':'REUSE','id':key,'result':result}
                return {'action':'BLOCKED_'+prior[0],'id':key}
            db.execute('INSERT INTO reusable_runs VALUES(?,?,?,?,NULL,NULL)',(key,canonical(spec),'RUNNING',int(time.time()*1000)))
            for name,sha in spec['datasets'].items():db.execute('INSERT INTO run_dependencies VALUES(?,?,?)',(key,name,sha))
            return {'action':'EXECUTE','id':key}
    def finish_run(self,key,result,valid):
        text=canonical(result)
        with self.connect() as db:
            changed=db.execute("UPDATE reusable_runs SET state=?,result=?,result_sha=? WHERE id=? AND state='RUNNING'",('VALID' if valid else 'FAILED',text,digest(result),key)).rowcount
            if changed!=1:raise ValueError('RUN_NOT_PENDING')
    def indicator(self,name,version,definition_sha,status,evidence):
        if status not in ('UNREVIEWED','IMPLEMENTED_UNVALIDATED','TESTED') or not evidence or not name or not version or len(definition_sha)!=64 or any(c not in '0123456789abcdef' for c in definition_sha):raise ValueError('INDICATOR_SCHEMA')
        with self.connect() as db:db.execute('INSERT INTO indicator_catalog VALUES(?,?,?,?,?)',(name,version,definition_sha,status,canonical(evidence)))
