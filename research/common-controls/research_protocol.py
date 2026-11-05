"""Pre-registered trial budget and holdout exposure on the existing ledger DB."""
import json
from registry import digest,canonical

def initialize(bank):
    with bank.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS protocols(id TEXT PRIMARY KEY,sha TEXT NOT NULL,body TEXT NOT NULL,holdout_seen INTEGER NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS protocol_trials(protocol_id TEXT,trial_hash TEXT,PRIMARY KEY(protocol_id,trial_hash))')
        db.execute('CREATE TABLE IF NOT EXISTS exposed_holdouts(fingerprint TEXT PRIMARY KEY)')

def freeze(bank,name,protocol):
    initialize(bank)
    if protocol.get('schema')!='faraz-protocol-v2' or protocol.get('max_trials')!=12 or protocol.get('seeds')!=[1729,2718,31415,42017,65537]:raise ValueError('PREDECLARED_PROTOCOL_REQUIRED')
    bounds=protocol.get('split')
    if not isinstance(bounds,dict) or set(bounds)!= {'train','validation','holdout'}:raise ValueError('SPLIT')
    last=-1
    for part in ('train','validation','holdout'):
        a,b=bounds[part]
        if type(a) is not int or type(b) is not int or not last<a<b:raise ValueError('SPLIT_OVERLAP')
        last=b
    sha=digest(protocol)
    with bank.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT sha FROM protocols WHERE id=?',(name,)).fetchone()
        if prior and prior[0]!=sha:raise ValueError('IMMUTABLE_PROTOCOL_NEW_HOLDOUT_REQUIRED')
        key=protocol.get('holdout_fingerprint')
        if not isinstance(key,str) or len(key)!=64:raise ValueError('HOLDOUT_FINGERPRINT_REQUIRED')
        if not prior and db.execute('SELECT 1 FROM exposed_holdouts WHERE fingerprint=?',(key,)).fetchone():raise ValueError('RENAMED_EXPOSED_HOLDOUT')
        db.execute('INSERT OR IGNORE INTO protocols VALUES(?,?,?,0)',(name,sha,canonical(protocol)))
    return sha

def reserve_trial(bank,name,configuration):
    initialize(bank);trial=digest(configuration)
    with bank.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body,holdout_seen FROM protocols WHERE id=?',(name,)).fetchone()
        if row is None:raise ValueError('PROTOCOL_NOT_FROZEN')
        existing=db.execute('SELECT 1 FROM protocol_trials WHERE protocol_id=? AND trial_hash=?',(name,trial)).fetchone()
        if existing:return {'action':'EXISTING_TRIAL_CHECK_RESULT_CACHE','trial_hash':trial}
        if row[1]:raise ValueError('HOLDOUT_ALREADY_SEEN_NO_NEW_TRIAL')
        count=db.execute('SELECT COUNT(*) FROM protocol_trials WHERE protocol_id=?',(name,)).fetchone()[0]
        if count>=json.loads(row[0])['max_trials']:raise ValueError('TRIAL_BUDGET_EXHAUSTED')
        db.execute('INSERT INTO protocol_trials VALUES(?,?)',(name,trial))
    return {'action':'RESERVED','trial_hash':trial}

def expose_holdout(bank,name):
    with bank.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT body FROM protocols WHERE id=?',(name,)).fetchone()
        if row is None:raise ValueError('PROTOCOL_NOT_FROZEN')
        db.execute('INSERT OR IGNORE INTO exposed_holdouts VALUES(?)',(json.loads(row[0])['holdout_fingerprint'],))
        changed=db.execute('UPDATE protocols SET holdout_seen=1 WHERE id=?',(name,)).rowcount
        if changed!=1:raise ValueError('PROTOCOL_NOT_FROZEN')
