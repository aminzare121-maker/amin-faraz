#!/usr/bin/env python3
"""Informational Artin semantic clarification inventory only.
No authority over trading engines, source extraction, or workflow continuation.
"""
import argparse,json,re,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REGISTRY=ROOT/'COURSE_REGISTRY.json'
AUDIT=ROOT/'SEMANTIC_AUDIT.json'
SHA=re.compile(r'^[a-f0-9]{64}$')

def audit(registry,audit_doc):
    sessions=registry['registered_sessions']
    items=audit_doc['sessions']
    assert len(items)<=len(sessions), 'Audit references lessons not yet registered'
    for session,entry in zip(sessions,items):
        assert entry['sequence']==session['sequence'], 'Audit session order mismatch'
        assert entry['source_sha256']==session['source_sha256'] and SHA.fullmatch(entry['source_sha256']), 'Audit original-video identity mismatch'
        assert entry['source_page']==session['source_page'], 'Audit video URL mismatch'
        assert entry['teacher_semantics_verified'] is False, 'Never assert teacher meaning without source-anchored independent evidence'
        assert entry['verified_executable_rules']==[], 'Unverified rule cannot be executable'
        assert entry['review_required'] is True, 'Unverified film must remain flagged for review'
    missing=sessions[len(items):]
    if missing:
        print('SEMANTIC_AUDIT_NEW_SESSIONS_REQUIRE_REVIEW='+','.join(str(x['sequence']) for x in missing))
    return len(items)

def main():
    parser=argparse.ArgumentParser()
    args=parser.parse_args()
    registry=json.loads(REGISTRY.read_text(encoding='utf-8'))
    doc=json.loads(AUDIT.read_text(encoding='utf-8'))
    n=audit(registry,doc)
    print(f'ARTIN_SEMANTIC_CLARIFICATION_INVENTORY={n}; INFORMATIONAL_ONLY=true')

if __name__=='__main__':main()
