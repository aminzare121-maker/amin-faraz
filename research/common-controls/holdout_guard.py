"""Shared local exposure journal. Missing journal fails closed; not tamper-proof.

Intervals are half-open UTC seconds, independent of filenames, price values,
dataset IDs, and the per-experiment ResearchLedger. All current synthetic
experiments share one conservative domain. Financial research stays blocked.
"""
import sqlite3
from contextlib import closing
from pathlib import Path

AUTHORITY = Path('C:/Users/Pixel/Documents/Codex/research-governance/private-holdout-authority.sqlite')

def check(research_start, research_end):
    """Reject previously exposed periods before training consumes any prices."""
    if type(research_start) is not int or type(research_end) is not int or research_start >= research_end:
        raise ValueError('INVALID_EXPOSURE_INTERVAL')
    try:
        with closing(sqlite3.connect(AUTHORITY.as_uri()+'?mode=rw', uri=True)) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise ValueError('EXPOSURE_JOURNAL_VERSION')
            if db.execute('SELECT 1 FROM exposure WHERE start < ? AND end > ? LIMIT 1',
                          (research_end,research_start)).fetchone():
                raise ValueError('GLOBAL_HOLDOUT_ALREADY_EXPOSED')
    except sqlite3.Error as exc:
        raise ValueError('EXPOSURE_JOURNAL_UNAVAILABLE') from exc

def provision(path):
    """Explicit creation only; never called automatically by evaluation."""
    path = Path(path)
    with path.open('xb'):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE exposure(run TEXT PRIMARY KEY, start INTEGER, end INTEGER)')
        db.execute('PRAGMA user_version=1')

def seal(run, research_start, research_end, holdout_start, holdout_end):
    values = (research_start, research_end, holdout_start, holdout_end)
    if any(type(v) is not int for v in values) or not research_start <= holdout_start < holdout_end <= research_end:
        raise ValueError('INVALID_EXPOSURE_INTERVAL')
    if not isinstance(run,str) or len(run)!=64:
        raise ValueError('RUN_ID_REQUIRED')
    # mode=rw refuses to silently create a new journal after deletion/move.
    try:
        with closing(sqlite3.connect(AUTHORITY.as_uri()+'?mode=rw', uri=True, timeout=10)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise ValueError('EXPOSURE_JOURNAL_VERSION')
            if db.execute('SELECT 1 FROM exposure WHERE start < ? AND end > ? LIMIT 1',
                          (research_end, research_start)).fetchone():
                raise ValueError('GLOBAL_HOLDOUT_ALREADY_EXPOSED')
            db.execute('INSERT INTO exposure VALUES(?,?,?)',(run,holdout_start,holdout_end))
    except sqlite3.Error as exc:
        raise ValueError('EXPOSURE_JOURNAL_UNAVAILABLE') from exc
