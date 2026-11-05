"""Persistent experiment registry: a reused/overlapping holdout cannot yield fresh approval."""
import json
from contextlib import contextmanager
import sqlite3
import time
from pathlib import Path


class ResearchLedger:
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY,holdout_start INTEGER,holdout_end INTEGER,created INTEGER,status TEXT,report TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS iran_observations(fingerprint TEXT PRIMARY KEY,metric TEXT,period TEXT,source TEXT,received INTEGER,payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS synthesis_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,created INTEGER NOT NULL,payload TEXT NOT NULL)')
            if 'scope' not in [r[1] for r in db.execute('PRAGMA table_info(synthesis_reports)')]:db.execute("ALTER TABLE synthesis_reports ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'")
            db.execute('CREATE TABLE IF NOT EXISTS discoveries(id TEXT PRIMARY KEY,received INTEGER,source TEXT,payload TEXT)')
    def reserve(self,identity,start,end):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            overlapping=db.execute('SELECT 1 FROM experiments WHERE holdout_start<=? AND holdout_end>=? LIMIT 1',(end,start)).fetchone()
            duplicate=db.execute('SELECT 1 FROM experiments WHERE id=?',(identity,)).fetchone()
            if duplicate:return False
            db.execute('INSERT INTO experiments VALUES(?,?,?,?,?,NULL)',(identity,start,end,int(time.time()*1000),'REUSED' if overlapping else 'SEALED'))
            return not overlapping
    def finish(self,identity,report):
        with self.connect() as db:db.execute('UPDATE experiments SET report=?,status=? WHERE id=? AND report IS NULL',(json.dumps(report,allow_nan=False),'DONE',identity))
    def discover(self,records):
        added=0
        with self.connect() as db:
            for r in records:added+=db.execute('INSERT OR IGNORE INTO discoveries VALUES(?,?,?,?)',(r['id'],r['received_ms'],r['source'],json.dumps(r))).rowcount
        return added
    def counts(self):
        with self.connect() as db:return {'experiments':db.execute('SELECT count(*) FROM experiments').fetchone()[0],'discoveries':db.execute('SELECT count(*) FROM discoveries').fetchone()[0]}

    def save_synthesis(self,report):
        payload=json.dumps(report,allow_nan=False)
        if len(payload)>100000 or report.get('can_execute') is not False or type(report.get('generated_ms')) is not int:raise ValueError('Invalid public research report')
        scope=report.get('scope','global')
        if scope not in ('global','iran-statistics-only'):raise ValueError('Invalid report scope')
        with self.connect() as db:db.execute('INSERT INTO synthesis_reports(created,payload,scope) VALUES(?,?,?)',(report['generated_ms'],payload,scope))
    def syntheses(self,limit=20,scope="global"):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM synthesis_reports WHERE scope=? ORDER BY id DESC LIMIT ?',(scope,max(1,min(int(limit),20))))]

    def register_iran(self,rows):
        import hashlib
        changes={'new':0,'revisions':0,'baseline':0}
        with self.connect() as db:
            initial=db.execute('SELECT 1 FROM iran_observations LIMIT 1').fetchone() is None
            for row in rows:
                raw=json.dumps({k:row.get(k) for k in ('metric','period','source_url','unit','value')},sort_keys=True,allow_nan=False)
                fingerprint=hashlib.sha256(raw.encode()).hexdigest()
                if db.execute('SELECT 1 FROM iran_observations WHERE fingerprint=?',(fingerprint,)).fetchone():continue
                revision=db.execute('SELECT 1 FROM iran_observations WHERE metric=? AND period=? AND source=? LIMIT 1',(row['metric'],row['period'],row['source_url'])).fetchone() is not None
                db.execute('INSERT INTO iran_observations VALUES(?,?,?,?,?,?)',(fingerprint,row['metric'],row['period'],row['source_url'],row['received_ms'],json.dumps(row,allow_nan=False)))
                changes['baseline' if initial else 'revisions' if revision else 'new']+=1
        return changes
